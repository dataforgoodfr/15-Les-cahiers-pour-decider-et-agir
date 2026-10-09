"""Outil local d'annotation des cahiers, pour la chaîne de traitement du texte.

    uv run python -m annotation [--versement data/versement]
        [--typage data/typage/departements] [--dossier data/annotation]
        [--port 8765]

Puis ouvrir http://127.0.0.1:8765. Le serveur n'écoute que sur la machine :
les pages, les notes et les listes ne la quittent pas.

Dans le dossier (hors git, comme tout `data/`) :

- `notes.jsonl` : le carnet des notes et des statuts (`annotation.carnet`) ;
- `listes/` : les listes de pages à revoir (`annotation.listes`), écrites par
  les modules d'analyse.

Le panneau de chaque page montre son typage et ce que les analyses y ont
détecté (`annotation.metadonnees`, lu dans `--donnees`).

Une page qu'`orientation` détecte tournée d'un quart de tour s'affiche
tournée de ROTATION_DETECTEE : à l'ouverture du cahier, la rotation entre au
carnet (l'ordre de lecture des notes en dépend, `selection` la relit), sauf
si la page a déjà une rotation, même remise à 0, ou des notes.
"""

import argparse
import json
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from annotation import listes
from annotation.carnet import PROBLEMES, TYPES, Carnet
from annotation.corpus import Corpus
from annotation.metadonnees import Metadonnees

STATIQUE = Path(__file__).parent / "statique"
TYPES_MIME = {".html": "text/html", ".js": "text/javascript", ".css": "text/css"}
# Étiquettes des notes posées sur la page, par groupe. Les données
# personnelles se marquent d'un rectangle : c'est la référence de
# l'anonymisation (#7). Le texte de la note ne doit pas recopier la donnée.
ETIQUETTES = {
    "Structure": ["début de contribution", "fin de contribution", "date", "signature"],
    "Données personnelles": [
        "nom",
        "prénom",
        "adresse",
        "courriel",
        "téléphone",
        "autre donnée identifiante",
        "bloc de coordonnées",
    ],
    "Autre": ["remarque"],
}


# `orientation` ne dit pas le sens du quart de tour ; à la main, 36 des 38
# pages détectées tournées l'ont été de 90° (sens horaire)
ROTATION_DETECTEE = 90


def tourner_les_pages_detectees(
    carnet: Carnet, fichier: str, metadonnees: Metadonnees
) -> None:
    """Pose ROTATION_DETECTEE sur les pages du fichier détectées tournées qui
    n'ont ni rotation au carnet ni note."""
    detectees = metadonnees.tournees.get(fichier, set())
    if not detectees:
        return
    qualifications = carnet.qualifications(remarques=False)
    notes, _ = carnet.etat()
    annotees = {n["page"] for n in notes.values() if n["fichier"] == fichier}
    for page in sorted(detectees - annotees):
        if "rotation" not in qualifications.get((fichier, page), {}):
            carnet.qualifier(fichier, page, "rotation", ROTATION_DETECTEE)


def application(
    corpus: Corpus, carnet: Carnet, dossier_listes: Path, metadonnees: Metadonnees
):
    class Requete(BaseHTTPRequestHandler):
        def log_message(self, *args):  # pas de noms de cahiers dans le terminal
            pass

        def envoyer(
            self, corps: bytes, type_: str, statut=HTTPStatus.OK, cache="no-store"
        ):
            self.send_response(statut)
            self.send_header("Content-Type", type_)
            self.send_header("Content-Length", str(len(corps)))
            self.send_header("Cache-Control", cache)
            self.end_headers()
            self.wfile.write(corps)

        def json(self, donnees, statut=HTTPStatus.OK):
            corps = json.dumps(donnees, ensure_ascii=False).encode()
            self.envoyer(corps, "application/json; charset=utf-8", statut)

        def erreur(self, statut, message: str):
            self.json({"erreur": message}, statut)

        def do_GET(self):
            url = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            try:
                self.route_get(url.path, q)
            except (KeyError, IndexError, ValueError) as e:
                self.erreur(HTTPStatus.NOT_FOUND, f"introuvable : {e}")

        def route_get(self, chemin: str, q: dict):
            if chemin in ("/", "/index.html"):
                chemin = "/statique/index.html"
            if chemin.startswith("/statique/"):
                fichier = STATIQUE / chemin.removeprefix("/statique/")
                if fichier.parent != STATIQUE or not fichier.is_file():
                    raise KeyError(chemin)
                type_ = TYPES_MIME.get(fichier.suffix, "application/octet-stream")
                self.envoyer(fichier.read_bytes(), f"{type_}; charset=utf-8")
            elif chemin == "/api/etiquettes":
                self.json(
                    {"etiquettes": ETIQUETTES, "problemes": PROBLEMES, "types": TYPES}
                )
            elif chemin == "/api/listes":
                self.json(listes.sommaire(dossier_listes))
            elif chemin == "/api/liste":
                self.json(listes.lire(dossier_listes, q["nom"]))
            elif chemin == "/api/cahiers":
                self.json(corpus.chercher(q.get("q", "")))
            elif chemin == "/api/cahier":
                fichier = q["fichier"]
                tourner_les_pages_detectees(carnet, fichier, metadonnees)
                notes, _ = carnet.etat()
                statuts = carnet.statuts(q.get("tache") or None)
                qualifications = carnet.qualifications()
                constats = metadonnees.pages(fichier)
                coches = metadonnees.problemes(fichier)
                pages = []
                for p in corpus.pages(fichier):
                    qualif = qualifications.get((fichier, p["page"]), {})
                    pages.append(
                        p
                        | {
                            "constats": constats.get(p["page"], []),
                            "problemes_auto": sorted(coches.get(p["page"], ())),
                            "problemes": qualif.get("problemes", {}),
                            "type_verifie": qualif.get("type"),
                            "rotation": qualif.get("rotation", 0),
                            "remarque": qualif.get("remarque", ""),
                        }
                    )
                self.json(
                    {
                        "fichier": fichier,
                        "constats": metadonnees.cahier(fichier),
                        "remarque": qualifications.get((fichier, 0), {}).get(
                            "remarque", ""
                        ),
                        "pages": pages,
                        "notes": [n for n in notes.values() if n["fichier"] == fichier],
                        "retablis": [
                            [p, ident]
                            for f, p, ident in carnet.retablis()
                            if f == fichier
                        ],
                        "statuts": {
                            p: s for (f, p), s in statuts.items() if f == fichier
                        },
                    }
                )
            elif chemin == "/api/statuts":
                statuts = carnet.statuts(q.get("tache") or None)
                self.json([[f, p, s] for (f, p), s in statuts.items()])
            elif chemin == "/api/lignes":
                self.json(corpus.lignes(q["fichier"], int(q["page"])))
            elif chemin == "/api/image":
                image = corpus.image(q["fichier"], int(q["page"]), int(q["largeur"]))
                # une page rendue ne change pas : le navigateur peut la garder,
                # ce qui permet de précharger les pages suivantes
                self.envoyer(image, "image/jpeg", cache="private, max-age=86400")
            else:
                raise KeyError(chemin)

        def do_POST(self):
            longueur = int(self.headers.get("Content-Length", 0))
            try:
                corps = json.loads(self.rfile.read(longueur) or b"{}")
                chemin = urlparse(self.path).path
                if chemin == "/api/notes":
                    corpus.chemin(corps["fichier"])
                    self.json(carnet.noter(corps))
                elif chemin == "/api/notes/modifier":
                    self.json(carnet.modifier(corps["id"], corps))
                elif chemin == "/api/notes/supprimer":
                    self.json(carnet.supprimer(corps["id"]))
                elif chemin == "/api/qualifier":
                    corpus.chemin(corps["fichier"])
                    self.json(
                        carnet.qualifier(
                            corps["fichier"],
                            corps["page"],
                            corps["champ"],
                            corps["valeur"],
                        )
                    )
                elif chemin == "/api/retablir":
                    corpus.chemin(corps["fichier"])
                    self.json(
                        carnet.retablir(
                            corps["fichier"],
                            corps["page"],
                            corps["marque"],
                            corps.get("retabli", True),
                        )
                    )
                elif chemin == "/api/statut":
                    corpus.chemin(corps["fichier"])
                    self.json(
                        carnet.marquer(
                            corps["fichier"],
                            corps["page"],
                            corps["statut"],
                            corps.get("tache"),
                        )
                    )
                else:
                    self.erreur(HTTPStatus.NOT_FOUND, chemin)
            except (KeyError, ValueError, json.JSONDecodeError) as e:
                self.erreur(HTTPStatus.BAD_REQUEST, f"requête invalide : {e}")

    return Requete


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--versement", type=Path, default=Path("data/versement"))
    parser.add_argument("--typage", type=Path, default=Path("data/typage/departements"))
    parser.add_argument("--dossier", type=Path, default=Path("data/annotation"))
    parser.add_argument(
        "--donnees", type=Path, default=Path("data"), help="sorties des analyses"
    )
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--sans-navigateur", action="store_true", help="ne pas ouvrir le navigateur"
    )
    args = parser.parse_args()

    corpus = Corpus(args.versement, args.typage)
    carnet = Carnet(args.dossier / "notes.jsonl")
    serveur = ThreadingHTTPServer(
        ("127.0.0.1", args.port),
        application(corpus, carnet, args.dossier / "listes", Metadonnees(args.donnees)),
    )
    adresse = f"http://127.0.0.1:{args.port}"
    print(
        f"{len(corpus.noms)} PDF indexés. Annotation sur {adresse} (Ctrl+C pour arrêter)"
    )
    if not args.sans_navigateur:
        webbrowser.open(adresse)
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
