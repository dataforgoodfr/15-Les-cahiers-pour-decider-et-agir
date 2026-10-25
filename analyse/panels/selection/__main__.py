"""Export des contributions tirées, caviardées (issues #21 et #7).

    uv run python -m panels.selection [--cahiers data/tirage/contributions.csv]
        [--versement data/versement] [--typage data/typage/departements]
        [--annotation data/annotation]
        [--reperes data/selection/reperes.csv] [--sortie data/selection]

Lit la liste « selection » de l'outil d'annotation : un cahier dont la
dernière page (hors pages vierges, que l'outil ne montre pas) est marquée vue
a tous ses débuts de contributions notés. La contribution tirée s'en déduit
(`panels.selection.contribution`). Écrit dans la sortie :

- `pdf/` : un PDF par contribution tirée, réduit à ses pages (les PDF des
  cahiers qui ne sont plus délimités sont retirés). Ce qui n'est pas
  la contribution (au-dessus de son début, en dessous de sa fin) est couvert
  de gris ; les données personnelles de noir. Le caviardage est une vraie
  rédaction : le texte et les pixels dessous disparaissent, et les
  métadonnées du PDF sont effacées. Une page tournée dans l'outil
  d'annotation sort tournée de même, dans le sens de lecture ; une double
  page se lit page de gauche puis page de droite (`panels.selection.contribution`) ;
  sur une page où la contribution a un contour tracé dans l'outil
  d'annotation, c'est le dehors du polygone qui est couvert de gris ;
- `panels.selection.csv` : une ligne par cahier tiré, sa commune, la contribution
  retenue (rang, pages) et le nombre de cadres caviardés, ou ce qui manque.
  Une contribution dont une page est qualifiée « à écarter » (contenu qu'on
  ne publie pas au nom de l'association, ou sans contenu) n'est pas
  exportée : la suivante la remplace (`ecartees` : combien ont été
  sautées). Un cahier n'est écarté que si toutes le sont.

Réordonne aussi la liste « selection » de l'outil d'annotation : d'abord les
cahiers à délimiter dont la région et la taille de commune manquent le plus,
pour que les cahiers délimités restent représentatifs (`panels.selection.ordre`),
puis les cahiers délimités.

À caviarder : les notes de données personnelles et de signature de ces pages,
et sur les pages dactylographiées les repérages de `anonymisation` que la
relecture n'a pas rétablis (dans le doute, on cache). Des pages, des cadres et
des comptes, jamais de texte.

Les repérages lus sont une copie figée, `reperes.csv` de la sortie : ceux
qu'on a relus dans les exports. `python -m anonymisation` réécrit les siens à
chaque passage (nouvelles sources, nouveaux modèles appris) ; ils n'entrent
dans les exports que si on les copie exprès, avant de relire ce qui change.
Chaque passage affiche les exports qui diffèrent du précédent.
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import pymupdf

from annotation import listes
from annotation.carnet import Carnet
from annotation.corpus import Corpus
from anonymisation.__main__ import PERSONNELLES
from anonymisation.masquage import CHAMPS, a_masquer, fusionner
from panels.selection.contribution import (
    Sens,
    coupure,
    delimites,
    doublons,
    ecartee,
    en_colonnes,
    hors_contribution,
    hors_polygone,
    tiree,
)
from panels.selection.ordre import reordonner

TACHE = "selection"
DEBUT = "début de contribution"
FIN = "fin de contribution"
DOUBLE = "double page"
A_CACHER = PERSONNELLES | {"signature"}
NOIR = (0, 0, 0)
GRIS = (0.82, 0.82, 0.82)


def point(n: dict, sens: Sens) -> tuple[int, float, float]:
    """(page, y, x) du coin haut gauche d'une note, dans le sens de lecture."""
    a = sens.vers_lecture(n["x0"], n["y0"])
    b = sens.vers_lecture(n["x1"], n["y1"])
    return n["page"], min(a[1], b[1]), min(a[0], b[0])


def lire_cahier(chemin: Path, fichier: str, notes: list[dict], qualifications: dict):
    """Le sens de lecture de chaque page, et les débuts et fins notés dans
    l'ordre de lecture (`en_colonnes`) ; rend aussi les coupures des doubles
    pages, et l'identifiant de la note de chaque début."""
    with pymupdf.open(chemin) as doc:
        sens = {
            n: Sens(
                qualifications.get((fichier, n), {}).get("rotation", 0),
                doc[n - 1].rect.width,
                doc[n - 1].rect.height,
            )
            for n in range(1, doc.page_count + 1)
        }
    notes_debut = [n for n in notes if n["etiquette"] == DEBUT]
    debuts = [point(n, sens[n["page"]]) for n in notes_debut]
    fins = [point(n, sens[n["page"]]) for n in notes if n["etiquette"] == FIN]
    coupures = {
        n: coupure(
            sens[n],
            [x for p, _, x in debuts if p == n],
            qualifications.get((fichier, n), {}).get("problemes", {}).get(DOUBLE),
        )
        for n in sens
    }
    debuts, fins = (
        [en_colonnes(p, coupures[p[0]], sens[p[0]].dimensions[1]) for p in points]
        for points in (debuts, fins)
    )
    ids = dict(zip(debuts, (n["id"] for n in notes_debut), strict=True))
    return sens, debuts, fins, coupures, ids


def changements(avant: list[dict], apres: list[dict]) -> list[tuple[str, list]]:
    """Les cahiers dont la ligne de `panels.selection.csv` a changé : leur commune et
    les colonnes qui diffèrent. Un cahier nouveau ou disparu compte aussi."""
    anciens = {x["fichier"]: x for x in avant}
    sortie = []
    for x in apres:
        a = anciens.pop(x["fichier"], None)
        if a is None:
            sortie.append((x["commune"], ["nouveau"]))
            continue
        champs = [k for k in x if str(x[k]) != a.get(k, "")]
        if champs:
            sortie.append((x["commune"], champs))
    sortie += [(a["commune"], ["disparu"]) for a in anciens.values()]
    return sortie


def cadre(n: dict) -> pymupdf.Rect:
    return pymupdf.Rect(
        min(n["x0"], n["x1"]),
        min(n["y0"], n["y1"]),
        max(n["x0"], n["x1"]),
        max(n["y0"], n["y1"]),
    )


def caviarder(
    chemin: Path,
    sortie: Path,
    t,
    noirs: dict[int, list],
    sens: dict[int, Sens],
    fichier: str,
    coupures: dict[int, float | None] | None = None,
    polygones: dict[int, list] | None = None,
) -> int:
    """Écrit le PDF de la contribution `t` ; rend le nombre de cadres noirs.
    `coupures` : l'abscisse lue entre les deux pages des doubles pages.
    `polygones` : les contours tracés dans l'outil d'annotation, par page ; le
    dehors en est couvert de gris, à la place des bandes."""
    total = 0
    with pymupdf.open(chemin) as doc:
        for n in t.pages:
            page = doc[n - 1]
            # les cadres sont dans le repère de la page affichée (rotation comprise)
            vers_pdf = page.derotation_matrix
            if n in (polygones or {}):
                # le polygone est dans le repère des notes
                for r in hors_polygone(polygones[n], page.rect.width, page.rect.height):
                    page.add_redact_annot(pymupdf.Rect(r) * vers_pdf, fill=GRIS)
            else:
                # au-dessus et en dessous de la contribution, dans le sens de lecture
                gris = hors_contribution(
                    t, n, *sens[n].dimensions, (coupures or {}).get(n)
                )
                for r in gris:
                    cadre_pdf = pymupdf.Rect(sens[n].cadre_pdf(*r))
                    page.add_redact_annot(cadre_pdf * vers_pdf, fill=GRIS)
            for r in noirs.get(n, []):
                # une donnée sur un pixel de bord reste cachée : marge d'un point
                page.add_redact_annot((r + (-1, -1, 1, 1)) * vers_pdf, fill=NOIR)
                total += 1
            page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_PIXELS)
            # la page sort dans le sens de lecture qualifié dans l'outil
            page.set_rotation((page.rotation + sens[n].rotation) % 360)
        doc.select([n - 1 for n in t.pages])
        doc.scrub()
        doc.set_metadata({"title": f"Contribution tirée de {fichier}"})
        doc.save(sortie, garbage=4, deflate=True)
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--cahiers", type=Path, default=Path("data/tirage/contributions.csv")
    )
    parser.add_argument("--versement", type=Path, default=Path("data/versement"))
    parser.add_argument("--typage", type=Path, default=Path("data/typage/departements"))
    parser.add_argument("--annotation", type=Path, default=Path("data/annotation"))
    parser.add_argument(
        "--reperes", type=Path, default=Path("data/selection/reperes.csv")
    )
    parser.add_argument("--sortie", type=Path, default=Path("data/selection"))
    args = parser.parse_args()

    with args.cahiers.open(encoding="utf-8", newline="") as f:
        tirage = list(csv.DictReader(f))
    fichiers = {t["fichier"] for t in tirage}
    chemins = {p.name: p for p in args.versement.rglob("*.pdf") if p.name in fichiers}
    carnet = Carnet(args.annotation / "notes.jsonl")
    qualifications = carnet.qualifications(remarques=False)
    vues = {cle for cle, s in carnet.statuts(TACHE, exacte=True).items() if s == "vue"}
    corpus = Corpus(args.versement, args.typage)
    vus = delimites(
        fichiers,
        {f: corpus.pages(f) for f in fichiers if f in chemins},
        vues,
        qualifications,
    )
    notes, _ = carnet.etat()
    contours = carnet.contours()
    par_cahier = defaultdict(list)
    for n in notes.values():
        if n.get("fichier") in fichiers:
            par_cahier[n["fichier"]].append(n)
    if not args.reperes.exists():
        raise SystemExit(
            f"Pas de repérages figés dans {args.reperes} : y copier le "
            "reperes.csv d'anonymisation qu'on va relire dans les exports."
        )
    with args.reperes.open(encoding="utf-8", newline="") as f:
        reperes = [
            {**r, "page": int(r["page"]), **{k: float(r[k]) for k in CHAMPS}}
            for r in csv.DictReader(f)
            if r["fichier"] in vus
        ]
    retablis = list(carnet.retablis().values())

    dossier = args.sortie / "pdf"
    dossier.mkdir(parents=True, exist_ok=True)
    lignes = []
    for t in tirage:
        fichier = t["fichier"]
        ligne = {
            "fichier": fichier,
            "commune": t["commune"],
            "departement": t["departement"],
            "position": t["position"],
            "statut": "à délimiter",
            "rang": "",
            "ecartees": "",
            "contributions": "",
            "page_debut": "",
            "page_fin": "",
            "fin": "",
            "caviardages": "",
            "pdf": "",
        }
        lignes.append(ligne)
        if fichier not in vus:
            continue
        ns = par_cahier[fichier]
        sens, debuts, fins, coupures, ids = lire_cahier(
            chemins[fichier], fichier, ns, qualifications
        )
        derniere = len(sens)
        repetes = doublons(debuts)[1]
        if repetes:
            # un début posé deux fois : un double clic manqué (une fin) ou non
            pages = ", ".join(str(p[0]) for p in repetes)
            ligne["statut"] = f"à vérifier : débuts en double p. {pages}"
            continue
        contribution = tiree(float(t["position"]), debuts, fins, derniere)
        if contribution is None:
            ligne["statut"] = "vu sans début noté"
            continue
        # une contribution à écarter laisse la place à la suivante
        for decalage in range(1, contribution.n):
            if not ecartee(fichier, contribution.pages, qualifications):
                break
            ligne["ecartees"] = decalage
            contribution = tiree(float(t["position"]), debuts, fins, derniere, decalage)
        if ecartee(fichier, contribution.pages, qualifications):
            ligne |= {
                "statut": "écarté",
                "rang": contribution.rang,
                "contributions": contribution.n,
            }
            continue
        pages = set(contribution.pages)
        # les contours tracés pour cette contribution, sur ses pages
        debut = ids[doublons(debuts)[0][contribution.rang - 1]]
        polygones = {
            n: points
            for (f, n, d), points in contours.items()
            if f == fichier and d == debut and n in pages
        }
        notes_a_cacher = [
            {**n, **{k: v for k, v in zip(CHAMPS, cadre(n))}}
            for n in ns
            if n["etiquette"] in A_CACHER and n["page"] in pages
        ]
        masques = a_masquer(
            fusionner(
                [r for r in reperes if r["fichier"] == fichier and r["page"] in pages]
            ),
            [r for r in retablis if r["fichier"] == fichier],
            notes_a_cacher,
        )
        noirs = defaultdict(list)
        for m in masques:
            noirs[m["page"]].append(cadre(m))
        nom = f"{Path(fichier).stem}.pdf"
        total = caviarder(
            chemins[fichier],
            dossier / nom,
            contribution,
            noirs,
            sens,
            fichier,
            coupures,
            polygones,
        )
        ligne |= {
            "statut": "exporté",
            "rang": contribution.rang,
            "contributions": contribution.n,
            "page_debut": contribution.page_debut,
            "page_fin": contribution.page_fin,
            "fin": "notée" if contribution.fin_notee else "déduite",
            "caviardages": total,
            "pdf": f"pdf/{nom}",
        }

    precedent = args.sortie / "selection.csv"
    avant = []
    if precedent.exists():
        with precedent.open(encoding="utf-8", newline="") as f:
            avant = list(csv.DictReader(f))
    with precedent.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, list(lignes[0]))
        ecrivain.writeheader()
        ecrivain.writerows(lignes)
    exportes = [x for x in lignes if x["statut"] == "exporté"]
    # un cahier qui n'est plus délimité ne garde pas son ancien PDF
    gardes = {Path(x["pdf"]).name for x in exportes}
    for ancien in dossier.glob("*.pdf"):
        if ancien.name not in gardes:
            ancien.unlink()
    print(f"{len(exportes)} contributions exportées sur {len(lignes)} cahiers tirés")
    print(f"  pages : {sum(x['page_fin'] - x['page_debut'] + 1 for x in exportes)}")
    print(f"  cadres caviardés : {sum(x['caviardages'] for x in exportes)}")
    print(f"  sans caviardage : {sum(1 for x in exportes if not x['caviardages'])}")
    a_verifier = [x for x in lignes if x["statut"].startswith("à vérifier")]
    print(f"  à vérifier (débuts en double) : {len(a_verifier)}")
    for statut in ("écarté", "vu sans début noté", "à délimiter"):
        print(f"  {statut} : {sum(1 for x in lignes if x['statut'] == statut)}")
    print(f"PDF dans {dossier}")
    modifies = changements(avant, lignes)
    if modifies:
        print("Exports modifiés depuis le passage précédent, à relire :")
        for commune, champs in modifies:
            print(f"  {commune} : {', '.join(champs)}")
    elif avant:
        print("Aucun export modifié depuis le passage précédent.")

    try:
        liste = listes.lire(args.annotation / "listes", TACHE)
    except KeyError:
        return
    liste = reordonner(liste, tirage, vus)
    listes.ecrire(
        args.annotation / "listes",
        TACHE,
        liste["titre"],
        liste["consigne"],
        liste["elements"],
        tache=liste.get("tache"),
        mode=liste.get("mode", "accepter"),
    )
    suivants = ", ".join(e["fichier"] for e in liste["elements"][:3])
    print(f"Liste {TACHE} réordonnée, à délimiter d'abord : {suivants}")


if __name__ == "__main__":
    main()
