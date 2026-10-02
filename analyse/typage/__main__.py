"""Type chaque page de PDF de cahiers (issue #17).

    uv run python -m typage <pdf ou dossier>... [--sortie data/typage/pages.csv]

Écrit une ligne par page : fichier, page, type_page, encre, qualite, mots,
page_de_service. Des mesures, jamais de texte.
"""

import argparse
import csv
from collections import Counter
from pathlib import Path

import pymupdf

from typage.typage import typer


def pdfs(chemins: list[Path]) -> list[Path]:
    fichiers = []
    for chemin in chemins:
        fichiers += sorted(chemin.rglob("*.pdf")) if chemin.is_dir() else [chemin]
    return fichiers


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("chemins", type=Path, nargs="+")
    parser.add_argument("--sortie", type=Path, default=Path("data/typage/pages.csv"))
    args = parser.parse_args()

    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    compte = Counter()
    with args.sortie.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(
            [
                "fichier",
                "page",
                "type_page",
                "encre",
                "qualite",
                "mots",
                "page_de_service",
            ]
        )
        for fichier in pdfs(args.chemins):
            with pymupdf.open(fichier) as doc:
                for numero, page in enumerate(doc, start=1):
                    t = typer(page)
                    compte[t.type_page] += 1
                    ecrivain.writerow(
                        [
                            fichier.name,
                            numero,
                            t.type_page,
                            f"{t.encre:.5f}",
                            f"{t.qualite:.3f}",
                            t.mots,
                            int(t.page_de_service),
                        ]
                    )
    total = sum(compte.values())
    for type_page, n in compte.most_common():
        print(f"{n:8} {type_page} ({n / total:.0%})")
    print(f"Écrit dans {args.sortie}")


if __name__ == "__main__":
    main()
