"""Outil local d'annotation des cahiers, pour la chaîne de traitement du texte.

    uv run python -m annotation [--versement data/versement]
        [--typage data/typage/departements] [--dossier data/annotation]
        [--paires data/paires/paires.csv] [--themes data/themes/revue.csv]
        [--chabin ../data/cahiers_chabin-pdfs] [--port 8765]

Puis ouvrir http://127.0.0.1:8765, http://127.0.0.1:8765/paires pour
juger les paires de propositions (`annotation.paires`), ou
http://127.0.0.1:8765/themes pour cocher les sous-thèmes des propositions
(`annotation.themes`). Le serveur n'écoute que sur la machine :
les pages, les notes et les listes ne la quittent pas.

Dans le dossier (hors git, comme tout `data/`) :

- `notes.jsonl` : le carnet des notes et des statuts (`annotation.carnet`) ;
- `listes/` : les listes de pages à revoir (`annotation.listes`), écrites par
  les modules d'analyse ;
- `classement.paires.jsonl` : les jugements des paires de propositions ;
- `themes.jsonl` : les sous-thèmes cochés des propositions.

Le panneau de chaque page montre son typage et ce que les analyses y ont
détecté (`annotation.metadonnees`, lu dans `--donnees`).

Une page qu'`corpus.orientation` détecte tournée d'un quart de tour s'affiche
tournée de ROTATION_DETECTEE : à l'ouverture du cahier, la rotation entre au
carnet (l'ordre de lecture des notes en dépend, `panels.selection` la relit), sauf
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
from annotation.paires import ADJUGER, JUGEMENTS, JUGER, Journal, etat, lire_paires
from annotation.paires import litiges as litiges_
from annotation.themes import JournalThemes, grille, lire_revue
from annotation.themes import etat as etat_themes
from annotation.themes import image as image_chabin

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


# `corpus.orientation` ne dit pas le sens du quart de tour ; à la main, 36 des 38
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


def vue_paires(chemin: Path, journal: Journal, annotateur: str) -> dict:
    """Les paires, les jugements de l'annotateur et les litiges qu'il peut
    adjuger : ceux des autres, sans leurs noms."""
    jugements, adjudications = etat(journal.evenements())
    litiges = [
        {
            "paire": paire,
            "jugements": [j for _, j in deux],
            "adjudication": adjudications.get(paire, (None, None))[1],
        }
        for paire, deux in litiges_(jugements).items()
        if annotateur and annotateur not in dict(deux)
    ]
    return {
        "jugements_possibles": JUGEMENTS,
        "paires": lire_paires(chemin),
        "miens": {
            p: par[annotateur] for p, par in jugements.items() if annotateur in par
        },
        "litiges": litiges,
    }


def vue_themes(chemin: Path, journal: JournalThemes, annotateur: str) -> dict:
    """Les contributions à revoir, la grille, et ce que l'annotateur a coché
    dans chaque proposition, sans ce qu'ont coché les autres."""
    annotations = etat_themes(journal.evenements())
    return {
        "contributions": lire_revue(chemin),
        "grille": grille(),
        "miens": {
            p: {
                "sous_themes": sorted(par[annotateur]["sous_themes"]),
                "mal_coupee": par[annotateur]["mal_coupee"],
            }
            for p, par in annotations.items()
            if annotateur in par
        },
    }


def application(
    corpus: Corpus,
    carnet: Carnet,
    dossier_listes: Path,
    metadonnees: Metadonnees,
    paires: Path | None = None,
    journal: Journal | None = None,
    themes: Path | None = None,
    journal_themes: JournalThemes | None = None,
    pdf_chabin: Path | None = None,
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
            elif chemin == "/paires":
                chemin = "/statique/paires.html"
            elif chemin == "/themes":
                chemin = "/statique/themes.html"
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
            elif chemin == "/api/paires" and paires and journal:
                self.json(vue_paires(paires, journal, q.get("annotateur", "").strip()))
            elif chemin == "/api/themes" and themes and journal_themes:
                self.json(
                    vue_themes(themes, journal_themes, q.get("annotateur", "").strip())
                )
            elif chemin == "/api/themes/image" and themes and pdf_chabin:
                pdf = q["pdf"]
                if pdf not in {c["pdf"] for c in lire_revue(themes)}:
                    raise KeyError(pdf)
                largeur = max(400, min(2000, round(int(q["largeur"]) / 200) * 200))
                self.envoyer(
                    image_chabin(pdf_chabin / pdf, int(q["page"]), largeur),
                    "image/jpeg",
                    cache="private, max-age=86400",
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
                        "contours": [
                            {"page": p, "debut": d, "points": points}
                            for (f, p, d), points in carnet.contours().items()
                            if f == fichier
                        ],
                        "transcriptions": {
                            p: texte
                            for (f, p), texte in carnet.transcriptions().items()
                            if f == fichier
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
                elif chemin == "/api/contour":
                    corpus.chemin(corps["fichier"])
                    self.json(
                        carnet.contourner(
                            corps["fichier"],
                            corps["page"],
                            corps["debut"],
                            corps.get("points"),
                        )
                    )
                elif chemin == "/api/transcrire":
                    fichier = corps["fichier"]
                    page = int(corps["page"])
                    if not 1 <= page <= len(corpus.pages(fichier)):
                        raise ValueError(f"page inconnue : {page}")
                    self.json(carnet.transcrire(fichier, page, corps["texte"]))
                elif chemin == "/api/paires/juger" and paires and journal:
                    annotateur = corps["annotateur"].strip()
                    vue = vue_paires(paires, journal, annotateur)
                    if corps["paire"] not in {p["paire"] for p in vue["paires"]}:
                        raise KeyError(corps["paire"])
                    role = corps.get("role", JUGER)
                    if role == ADJUGER and corps["paire"] not in {
                        x["paire"] for x in vue["litiges"]
                    }:
                        raise ValueError("adjuger une paire sans litige, ou la sienne")
                    self.json(
                        journal.juger(
                            corps["paire"], annotateur, corps.get("jugement"), role
                        )
                    )
                elif chemin == "/api/themes/annoter" and themes and journal_themes:
                    if corps["proposition"] not in {
                        p["proposition"]
                        for c in lire_revue(themes)
                        for p in c["propositions"]
                    }:
                        raise KeyError(corps["proposition"])
                    self.json(
                        journal_themes.annoter(
                            corps["proposition"],
                            corps["annotateur"],
                            corps.get("sous_themes"),
                            corps.get("mal_coupee", False),
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
    parser.add_argument("--paires", type=Path, default=Path("data/paires/paires.csv"))
    parser.add_argument("--themes", type=Path, default=Path("data/themes/revue.csv"))
    parser.add_argument(
        "--chabin", type=Path, default=Path("../data/cahiers_chabin-pdfs")
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
        application(
            corpus,
            carnet,
            args.dossier / "listes",
            Metadonnees(args.donnees),
            args.paires,
            Journal(args.dossier / "paires.jsonl"),
            args.themes,
            JournalThemes(args.dossier / "themes.jsonl"),
            args.chabin,
        ),
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
