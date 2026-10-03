"""Documents manquants : inventaires du versement contre fichiers (issue #43).

    uv run python -m inventaires <racine du versement> [--sortie data/inventaires]
        [--processus 4]

La racine contient `A_lire/` (les inventaires) et les dossiers
`BnF_GDN_XX_PDF`. Écrit dans la sortie :

- `documents.csv` : un document par ligne, inventorié ou présent, avec son
  département, son code INSEE, le nombre d'inventaires qui le listent, et ses
  pages attendues (inventaire) et présentes (PDF) ;
- `departements.csv` : par département et catégorie, les documents
  inventoriés, présents, manquants, sans inventaire, et ceux dont le nombre
  de pages diffère.

Des codes et des comptes, jamais de texte.
"""

import argparse
import csv
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

import pymupdf

from inventaires.inventaires import (
    CATEGORIES,
    lire_inventaire,
    pages,
    rapprocher,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("racine", type=Path)
    parser.add_argument("--sortie", type=Path, default=Path("data/inventaires"))
    parser.add_argument("--processus", type=int, default=4)
    args = parser.parse_args()
    pymupdf.TOOLS.mupdf_display_errors(False)

    inventaires = sorted(
        (args.racine / "A_lire").glob("*_inventaire_contributions.pdf")
    )
    fichiers = [
        pdf
        for dossier in sorted(args.racine.glob("B[nN][fF]_GDN_*_PDF"))
        for categorie in CATEGORIES
        for pdf in sorted((dossier / categorie).glob("*.pdf"))
    ]
    with Pool(args.processus) as pool:
        entrees = [e for es in pool.map(lire_inventaire, inventaires) for e in es]
        presents = {
            nom: (dep, n)
            for nom, dep, n in pool.imap_unordered(pages, fichiers, chunksize=50)
        }
    print(f"{len(entrees)} entrées dans {len(inventaires)} inventaires")
    print(f"{len(presents)} fichiers dans le versement")
    documents = rapprocher(entrees, presents)

    args.sortie.mkdir(parents=True, exist_ok=True)
    comptes = defaultdict(Counter)
    with (args.sortie / "documents.csv").open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(
            [
                "fichier",
                "categorie",
                "departement",
                "code_insee",
                "inventaires",
                "present",
                "pages_attendues",
                "pages_presentes",
            ]
        )
        for d in documents:
            ecrivain.writerow(
                [
                    d.fichier,
                    d.categorie,
                    d.departement,
                    d.code_insee,
                    d.inventaires,
                    int(d.present),
                    "" if d.pages_attendues is None else d.pages_attendues,
                    "" if d.pages_presentes is None else d.pages_presentes,
                ]
            )
            c = comptes[(d.departement, d.categorie)]
            c["inventories"] += d.inventaires > 0
            c["presents"] += d.present
            c["manquants"] += d.inventaires > 0 and not d.present
            c["sans_inventaire"] += d.present and not d.inventaires
            c["pages_differentes"] += (
                d.inventaires > 0
                and d.present
                and d.pages_attendues != d.pages_presentes
            )

    colonnes = [
        "inventories",
        "presents",
        "manquants",
        "sans_inventaire",
        "pages_differentes",
    ]
    total = Counter()
    with (args.sortie / "departements.csv").open(
        "w", encoding="utf-8", newline=""
    ) as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(["departement", "categorie", *colonnes, "taux_manquants"])
        for (dep, cat), c in sorted(comptes.items()):
            taux = (
                f"{c['manquants'] / c['inventories']:.4f}" if c["inventories"] else ""
            )
            ecrivain.writerow([dep, cat, *(c[k] for k in colonnes), taux])
            total += c
    print(", ".join(f"{total[k]} {k}" for k in colonnes))
    print(f"Écrit dans {args.sortie}")


if __name__ == "__main__":
    main()
