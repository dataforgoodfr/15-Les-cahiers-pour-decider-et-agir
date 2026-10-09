"""Référence de découpage : les cahiers de l'édition Chabin, relus à la main.

    uv run python -m chabin
        [--extraction ../data/cahiers_chabin-extraction.json]
        [--versement data/versement] [--typage data/typage/departements]
        [--annotation data/annotation] [--sortie data/chabin]
        [--ouvertures data/ouvertures/ouvertures.csv]

L'extraction vient de `extraction/chabin` (échantillon ou édition complète).
Écrit la liste « chabin » de l'outil d'annotation : un élément par scan BnF
des cahiers extraits. Le lecteur y délimite toutes les contributions, puis
marque la dernière page vue, comme pour la sélection.

Retrouve aussi, dans l'OCR des scans, le début de chaque contribution
dactylographiée ou imprimée d'une messagerie (`alignement.csv` dans la
sortie, voir `chabin.alignement`), et mesure sur cette référence les règles
de découpage (`contributions.regles`) : précision et rappel des débuts sur
les pages dactylographiées.

Compare enfin, pour chaque cahier délimité, ses débuts notés aux
contributions de l'édition (`comparaison.csv` dans la sortie). Des codes, des
noms de fichiers, des positions et des comptes, jamais de texte.
"""

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

import pymupdf

from annotation import listes
from annotation.carnet import Carnet
from annotation.corpus import Corpus
from chabin.alignement import IMPRIMEES, genre, localiser
from chabin.reference import cahiers, comparer, elements
from contributions.__main__ import lignes, pages_lues, premieres_ecrites
from contributions.regles import debuts, evaluer
from ouvertures.__main__ import lire as lire_ouvertures
from selection.contribution import derniere_page

TACHE = "chabin"
DEBUT = "début de contribution"


def scans(e: dict) -> list[str]:
    return [Path(f).name for f in e["pdf_files"]]


def aligner(extraction: list[dict | None], corpus: Corpus) -> list[dict]:
    """Une ligne par contribution des cahiers dont tous les scans sont au
    versement : pour une contribution imprimée, où elle commence dans l'OCR
    si on l'y retrouve ; un manuscrit reste sans position."""
    sortie = []
    for e in extraction:
        if not e or not scans(e) or not all(f in corpus.chemins for f in scans(e)):
            continue
        positions = []  # (fichier, page, ligne dans la page, texte, cadre)
        for f in scans(e):
            with pymupdf.open(corpus.chemin(f)) as doc:
                for n, page in enumerate(doc, 1):
                    positions += [
                        (f, n, i, texte, cadre)
                        for i, (texte, cadre) in enumerate(lignes(page))
                    ]
        genres = [genre(c["title"]) for c in e["contributions"]]
        imprimees = [k for k, g in enumerate(genres) if g in IMPRIMEES]
        trouves = dict(
            zip(
                imprimees,
                localiser(
                    [e["contributions"][k]["text"] for k in imprimees],
                    [p[3] for p in positions],
                ),
            )
        )
        for k, g in enumerate(genres):
            ligne = {
                "insee": e["city"]["insee"],
                "rang": k + 1,
                "genre": g,
                "fichier": "",
                "page": "",
                "ligne": "",
                "y0": "",
                "ressemblance": "",
            }
            if trouves.get(k):
                f, n, i, _, cadre = positions[trouves[k][0]]
                ligne |= {
                    "fichier": f,
                    "page": n,
                    "ligne": i,
                    "y0": round(cadre.y0, 1),
                    "ressemblance": trouves[k][1],
                }
            sortie.append(ligne)
    return sortie


def mesurer_regles(
    alignement: list[dict],
    scans_par_cahier: dict[str, list[str]],
    corpus: Corpus,
    typage: Path,
    ouvertures: set[tuple[str, int]],
) -> list[tuple[str, str, float, float, int, int]]:
    """Précision et rappel des règles sur les pages dactylographiées, par
    règle et sur deux périmètres : (périmètre, règle, précision, rappel,
    débuts trouvés, débuts de la référence).

    - « cahiers à imprimés » : ceux qui ont au moins une contribution
      imprimée retrouvée. Les manuscrits n'ont pas de position : un début de
      manuscrit trouvé par une règle y compte comme une erreur, la précision
      est donc sous-estimée ;
    - « référence complète » : les cahiers dont toutes les contributions sont
      imprimées et retrouvées.
    """
    par_cahier: dict[str, list[dict]] = {}
    for a in alignement:
        par_cahier.setdefault(a["insee"], []).append(a)
    perimetres = {
        "cahiers à imprimés": {
            i for i, lignes_ in par_cahier.items() if any(a["fichier"] for a in lignes_)
        },
        "référence complète": {
            i for i, lignes_ in par_cahier.items() if all(a["fichier"] for a in lignes_)
        },
    }
    fichiers = {
        f for i in perimetres["cahiers à imprimés"] for f in scans_par_cahier[i]
    }
    lues = pages_lues([typage], fichiers, ouvertures)
    premieres = premieres_ecrites([typage], fichiers, ouvertures)
    trouves = []
    for fichier, numeros in sorted(lues.items()):
        with pymupdf.open(corpus.chemin(fichier)) as doc:
            pages = [lignes(doc[n - 1]) for n in numeros]
        for p, i, regle in debuts(
            [[t for t, _ in page] for page in pages],
            debut_du_cahier=numeros[0] == premieres.get(fichier),
        ):
            trouves.append((fichier, numeros[p], pages[p][i][1].y0, regle))
    mesures = []
    for nom, cahiers_ in perimetres.items():
        pages_vues = {
            (f, n)
            for i in cahiers_
            for f in scans_par_cahier[i]
            for n in lues.get(f, [])
        }
        reference = [
            (a["fichier"], a["page"], a["y0"])
            for i in cahiers_
            for a in par_cahier[i]
            if (a["fichier"], a["page"]) in pages_vues
        ]
        for regle in (None, "courriel", "gabarit", "début du cahier"):
            retenus = [
                (f, n, y)
                for f, n, y, r in trouves
                if (f, n) in pages_vues and (regle is None or r.startswith(regle))
            ]
            precision, rappel = evaluer(retenus, reference)
            mesures.append(
                (
                    nom,
                    regle or "toutes règles",
                    precision,
                    rappel,
                    len(retenus),
                    len(reference),
                )
            )
    return mesures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--extraction",
        type=Path,
        default=Path("../data/cahiers_chabin-extraction.json"),
    )
    parser.add_argument("--versement", type=Path, default=Path("data/versement"))
    parser.add_argument("--typage", type=Path, default=Path("data/typage/departements"))
    parser.add_argument("--annotation", type=Path, default=Path("data/annotation"))
    parser.add_argument("--sortie", type=Path, default=Path("data/chabin"))
    parser.add_argument(
        "--ouvertures", type=Path, default=Path("data/ouvertures/ouvertures.csv")
    )
    args = parser.parse_args()

    extraction = json.loads(args.extraction.read_text(encoding="utf-8"))
    liste = cahiers(extraction)
    corpus = Corpus(args.versement, args.typage)
    fichiers = [f for c in liste for f in c.fichiers if f in corpus.chemins]
    pages = {f: corpus.pages(f) for f in fichiers}
    manquants = sum(len(c.fichiers) for c in liste) - len(fichiers)

    listes.ecrire(
        args.annotation / "listes",
        "chabin",
        "Référence Chabin : délimiter les contributions",
        (
            "Cahiers transcrits par Marie-Anne Chabin, pour comparer son "
            "découpage au nôtre. Pour chaque cahier : cliquer chaque début de "
            "contribution, clic droit sur chaque fin, dans l'ordre de lecture "
            "(une contribution : un texte d'un même auteur, ou d'un même groupe, "
            "d'un seul tenant). Pas de caviardage. À la fin, marquer la "
            "dernière page vue (v) : le cahier est alors délimité."
        ),
        elements(liste, {f: len(p) for f, p in pages.items()}),
        tache=TACHE,
    )
    print(
        f"Liste « chabin » : {len(liste)} cahiers, {len(fichiers)} scans"
        + (f" ({manquants} absents du versement)" if manquants else "")
    )

    alignement = aligner(extraction, corpus)
    if alignement:
        args.sortie.mkdir(parents=True, exist_ok=True)
        with (args.sortie / "alignement.csv").open(
            "w", encoding="utf-8", newline=""
        ) as f:
            ecrivain = csv.DictWriter(f, list(alignement[0]))
            ecrivain.writeheader()
            ecrivain.writerows(alignement)
        print("Contributions imprimées retrouvées dans l'OCR :")
        for g in sorted(IMPRIMEES):
            du_genre = [a for a in alignement if a["genre"] == g]
            n = sum(1 for a in du_genre if a["fichier"])
            print(f"  {g} : {n} sur {len(du_genre)}")
        print("Règles de découpage, sur les pages dactylographiées :")
        scans_par_cahier = {e["city"]["insee"]: scans(e) for e in extraction if e}
        for perimetre, regle, precision, rappel, n, ref in mesurer_regles(
            alignement,
            scans_par_cahier,
            corpus,
            args.typage,
            lire_ouvertures(args.ouvertures),
        ):
            print(
                f"  {perimetre}, {regle} : {n} débuts trouvés pour {ref}, "
                f"précision {precision:.0%}, rappel {rappel:.0%}"
            )

    carnet = Carnet(args.annotation / "notes.jsonl")
    qualifications = carnet.qualifications(remarques=False)
    plus_loin = Counter()
    for (f, page), s in carnet.statuts(TACHE, exacte=True).items():
        if s == "vue":
            plus_loin[f] = max(plus_loin[f], page)
    delimites = {
        f
        for f in fichiers
        if plus_loin[f] >= derniere_page(pages[f], f, qualifications)
    }
    debuts = Counter(
        n["fichier"] for n in carnet.positions() if n["etiquette"] == DEBUT
    )
    lignes = comparer(liste, debuts, delimites)
    if not lignes:
        print("Aucun cahier délimité : pas encore de comparaison.")
        return

    args.sortie.mkdir(parents=True, exist_ok=True)
    with (args.sortie / "comparaison.csv").open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, list(lignes[0]))
        ecrivain.writeheader()
        ecrivain.writerows(lignes)
    egaux = sum(1 for x in lignes if x["ecart"] == 0)
    print(f"{len(lignes)} cahiers délimités, {egaux} au même compte que l'édition")
    print(
        f"  contributions : édition {sum(x['chabin'] for x in lignes)}, "
        f"lecteur {sum(x['lecteur'] for x in lignes)}"
    )
    for x in lignes:
        if x["ecart"]:
            print(
                f"  {x['commune']} ({x['insee']}) : édition {x['chabin']}, "
                f"lecteur {x['lecteur']}"
            )


if __name__ == "__main__":
    main()
