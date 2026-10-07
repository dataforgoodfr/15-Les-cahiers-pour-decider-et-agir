"""Référence de découpage : les cahiers de l'édition Chabin, relus à la main.

    uv run python -m chabin
        [--extraction ../data/cahiers_chabin-extraction.json]
        [--versement data/versement] [--typage data/typage/departements]
        [--annotation data/annotation] [--sortie data/chabin]

L'extraction vient de `extraction/chabin` (échantillon ou édition complète).
Écrit la liste « chabin » de l'outil d'annotation : un élément par scan BnF
des cahiers extraits. Le lecteur y délimite toutes les contributions, puis
marque la dernière page vue, comme pour la sélection.

Compare ensuite, pour chaque cahier délimité, ses débuts notés aux
contributions de l'édition (`comparaison.csv` dans la sortie). Des codes, des
noms de fichiers et des comptes, jamais de texte.
"""

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from annotation import listes
from annotation.carnet import Carnet
from annotation.corpus import Corpus
from chabin.reference import cahiers, comparer, elements
from selection.contribution import derniere_page

TACHE = "chabin"
DEBUT = "début de contribution"


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
    args = parser.parse_args()

    liste = cahiers(json.loads(args.extraction.read_text(encoding="utf-8")))
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
