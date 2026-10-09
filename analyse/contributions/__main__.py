"""Débuts de contributions des cahiers, repérés par règles (issue #5).

    uv run python -m contributions [--cahiers data/tirage/contributions.csv]
        [--versement data/versement] [--typage data/typage/departements]
        [--annotation data/annotation] [--ouvertures data/ouvertures/ouvertures.csv]
        [--sortie data/contributions]

Règles dans `contributions.regles`. Seules les pages dactylographiées sont
lues, hors pages de service et pages d'ouverture imprimées (sortie de
`python -m ouvertures`, si elle existe). Écrit :

- `debuts.csv` dans la sortie : une ligne par début de contribution (fichier,
  page, rang de la ligne dans la couche texte, cadre de la ligne en points
  PDF, règle) ;
- `cahiers.csv` dans la sortie : par cahier, ses pages lues, ses
  contributions et les règles qui s'y appliquent ;
- une liste à revoir par règle dans `listes/` du dossier d'annotation, à
  ouvrir avec `python -m annotation`.

La référence est le carnet de l'outil d'annotation : les notes « début de
contribution » des cahiers délimités en entier pour le tirage (tâche
« selection », dernière page vue). Affiche la précision et le rappel des
débuts sur leurs pages dactylographiées. Des positions et des comptes,
jamais de texte.
"""

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

import pymupdf

from annotation import listes
from annotation.carnet import Carnet
from annotation.corpus import Corpus
from contributions.regles import debuts, evaluer
from ouvertures.__main__ import lire as lire_ouvertures
from panel.panel import lire_typage
from selection.contribution import derniere_page

DACTYLOGRAPHIEE = "dactylographiée"
VIERGE = "vierge"
DEBUT = "début de contribution"
TACHE = "contributions"
SELECTION = "selection"
REGLES = {
    "courriel": "Courriels repérés",
    "gabarit": "Formulaires (gabarits) repérés",
}
# listes à revoir : (nom, préfixe de la règle, titre)
LISTES = [
    ("courriel", "courriel", "Courriels repérés"),
    ("gabarit", "gabarit", "Formulaires (gabarits) repérés"),
    (
        "gabarit-souple",
        "gabarit ",
        "Formulaires repérés à l'OCR près (en-tête abîmé, à vérifier)",
    ),
]


# la règle ne voit pas la numérotation manuscrite (#64)
SUITE = (
    " Une feuille de suite du même auteur (numérotation des demandes qui "
    "continue, numéro de feuille) n'ouvre pas de contribution : ne pas accepter."
)


def pages_lues(
    typage: list[Path],
    fichiers: set[str],
    ouvertures: set[tuple[str, int]] = frozenset(),
) -> dict[str, list[int]]:
    """Numéros des pages dactylographiées de chaque cahier, hors service et
    hors pages d'ouverture imprimées (`python -m ouvertures`)."""
    pages = defaultdict(list)
    for ligne in lire_typage(typage):
        if (
            ligne["fichier"] in fichiers
            and ligne["type_page"] == DACTYLOGRAPHIEE
            and ligne["page_de_service"] != "1"
            and (ligne["fichier"], int(ligne["page"])) not in ouvertures
        ):
            pages[ligne["fichier"]].append(int(ligne["page"]))
    return {f: sorted(p) for f, p in pages.items()}


def premieres_ecrites(
    typage: list[Path],
    fichiers: set[str],
    ouvertures: set[tuple[str, int]] = frozenset(),
) -> dict[str, int]:
    """Première page écrite de chaque cahier, quel qu'en soit le type : ni
    vierge, ni de service, ni page d'ouverture."""
    premieres = {}
    for ligne in lire_typage(typage):
        f, n = ligne["fichier"], int(ligne["page"])
        if (
            f in fichiers
            and ligne["type_page"] != VIERGE
            and ligne["page_de_service"] != "1"
            and (f, n) not in ouvertures
        ):
            premieres[f] = min(n, premieres.get(f, n))
    return premieres


def lignes(page: pymupdf.Page) -> list[tuple[str, pymupdf.Rect]]:
    """Lignes de la couche texte, avec leur cadre dans le repère affiché."""
    sortie = []
    for bloc in page.get_text("dict")["blocks"]:
        for ligne in bloc.get("lines", []):
            texte = "".join(span["text"] for span in ligne["spans"])
            sortie.append((texte, pymupdf.Rect(ligne["bbox"]) * page.rotation_matrix))
    return sortie


def ecrire_listes(dossier: Path, trouves: list[dict], resume: list[dict]):
    pages_par_cahier = {r["fichier"]: r["pages"] for r in resume}
    for nom, regle, titre in LISTES:
        par_page = defaultdict(list)
        for d in trouves:
            if d["regle"].startswith(regle):
                par_page[d["fichier"], d["page"]].append(
                    {k: d[k] for k in ("x0", "y0", "x1", "y1")}
                    | {"etiquette": d["regle"], "note": DEBUT}
                )
        debuts_par_cahier = Counter(f for f, _ in par_page)
        elements = [
            {
                "fichier": fichier,
                "page": page,
                "marques": marques,
                "commentaire": (
                    f"{debuts_par_cahier[fichier]} pages à débuts sur "
                    f"{pages_par_cahier[fichier]} pages lues"
                ),
            }
            for (fichier, page), marques in sorted(par_page.items())
        ]
        listes.ecrire(
            dossier,
            f"contributions-{nom}",
            titre,
            (
                "Chaque marque orange est un début de contribution trouvé par la "
                f"règle « {regle.strip()} ». Juste : « a » l'accepte comme note "
                f"« {DEBUT} ». Faux : ne rien accepter. Ajouter les débuts manqués, "
                "puis marquer la page vue (v)."
                + (SUITE if regle.startswith("gabarit") else "")
            ),
            elements,
            tache=TACHE,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--cahiers", type=Path, default=Path("data/tirage/contributions.csv")
    )
    parser.add_argument("--versement", type=Path, default=Path("data/versement"))
    parser.add_argument(
        "--typage", type=Path, nargs="+", default=[Path("data/typage/departements")]
    )
    parser.add_argument("--annotation", type=Path, default=Path("data/annotation"))
    parser.add_argument(
        "--ouvertures", type=Path, default=Path("data/ouvertures/ouvertures.csv")
    )
    parser.add_argument("--sortie", type=Path, default=Path("data/contributions"))
    args = parser.parse_args()

    with args.cahiers.open(encoding="utf-8", newline="") as f:
        fichiers = {ligne["fichier"] for ligne in csv.DictReader(f)}
    chemins = {p.name: p for p in args.versement.rglob("*.pdf") if p.name in fichiers}
    ouvertures = lire_ouvertures(args.ouvertures)
    lues = pages_lues(args.typage, fichiers, ouvertures)
    premieres = premieres_ecrites(args.typage, fichiers, ouvertures)

    trouves, resume = [], []
    for fichier in sorted(lues):
        numeros = lues[fichier]
        with pymupdf.open(chemins[fichier]) as doc:
            pages = [lignes(doc[n - 1]) for n in numeros]
        cahier = debuts(
            [[texte for texte, _ in page] for page in pages],
            debut_du_cahier=numeros[0] == premieres.get(fichier),
        )
        for p, i, regle in cahier:
            cadre = pages[p][i][1]
            trouves.append(
                {
                    "fichier": fichier,
                    "page": numeros[p],
                    "ligne": i,
                    "x0": round(cadre.x0, 1),
                    "y0": round(cadre.y0, 1),
                    "x1": round(cadre.x1, 1),
                    "y1": round(cadre.y1, 1),
                    "regle": regle,
                }
            )
        regles = Counter(regle for _, _, regle in cahier)
        resume.append(
            {
                "fichier": fichier,
                "pages": len(numeros),
                "contributions": len(cahier),
                "courriel": regles["courriel"],
                "gabarit": sum(n for r, n in regles.items() if r.startswith("gabarit")),
                "gabarit_souple": sum(
                    n for r, n in regles.items() if r.startswith("gabarit ")
                ),
            }
        )

    args.sortie.mkdir(parents=True, exist_ok=True)
    with (args.sortie / "debuts.csv").open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, list(trouves[0]))
        ecrivain.writeheader()
        ecrivain.writerows(trouves)
    with (args.sortie / "cahiers.csv").open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, list(resume[0]))
        ecrivain.writeheader()
        ecrivain.writerows(resume)
    ecrire_listes(args.annotation / "listes", trouves, resume)

    decoupes = {r["fichier"] for r in resume if r["courriel"] or r["gabarit"]}
    print(f"{len(resume)} cahiers lus, {sum(r['pages'] for r in resume)} pages")
    for regle in REGLES:
        n = sum(1 for r in resume if r[regle])
        print(f"  {regle} : {n} cahiers, {sum(r[regle] for r in resume)} débuts")
    print(f"  non découpés (aucune règle) : {len(resume) - len(decoupes)} cahiers")
    print(f"Listes à revoir écrites dans {args.annotation / 'listes'}")

    # la référence : les cahiers délimités en entier pour le tirage (tâche
    # « selection », dernière page vue), sur les pages que les règles lisent
    carnet = Carnet(args.annotation / "notes.jsonl")
    qualifications = carnet.qualifications(remarques=False)
    vues = {
        cle for cle, s in carnet.statuts(SELECTION, exacte=True).items() if s == "vue"
    }
    corpus = Corpus(args.versement, args.typage[0])
    delimites = {
        f
        for f in lues
        if (f, derniere_page(corpus.pages(f), f, qualifications)) in vues
    }
    if not delimites:
        print("Aucun cahier délimité dans l'outil d'annotation : pas de référence.")
        return
    lues_delimitees = {(f, n) for f in delimites for n in lues[f]}
    reference = [
        (n["fichier"], n["page"], min(n["y0"], n["y1"]))
        for n in carnet.positions()
        if n["etiquette"] == DEBUT and (n["fichier"], n["page"]) in lues_delimitees
    ]
    print(
        f"Référence : {len(delimites)} cahiers délimités, {len(reference)} débuts "
        f"sur {len(lues_delimitees)} pages dactylographiées"
    )
    vus = [d for d in trouves if (d["fichier"], d["page"]) in lues_delimitees]
    for titre, regle in (("toutes règles", None), *((r, r) for r in REGLES)):
        retenus = [d for d in vus if regle is None or d["regle"].startswith(regle)]
        # une règle se mesure sur les pages où elle a trouvé des débuts
        pages = (
            lues_delimitees
            if regle is None
            else {(d["fichier"], d["page"]) for d in retenus}
        )
        if not pages:
            print(f"  {titre} : aucun début trouvé dans les cahiers délimités")
            continue
        precision, rappel = evaluer(
            [(d["fichier"], d["page"], d["y0"]) for d in retenus],
            [r for r in reference if (r[0], r[1]) in pages],
        )
        print(
            f"  {titre} : {len(retenus)} débuts, précision {precision:.0%}, "
            f"rappel {rappel:.0%} (sur {len(pages)} pages)"
        )


if __name__ == "__main__":
    main()
