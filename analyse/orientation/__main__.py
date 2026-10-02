"""Pages tournées d'un quart de tour dans les PDF de cahiers (issue #43).

    uv run python -m orientation <pdf ou dossier>... [--sortie data/orientation]
        [--processus 4]

Écrit `pages_tournees.csv` dans la sortie : une ligne par fichier, avec son
nombre de pages et ses pages tournées. Des numéros de page, jamais de texte.
"""

import argparse
import csv
from multiprocessing import Pool
from pathlib import Path

from orientation.orientation import pages_tournees
from typage.__main__ import pdfs

SERIE = 3  # pages tournées à partir desquelles un fichier est signalé


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("chemins", type=Path, nargs="+")
    parser.add_argument("--sortie", type=Path, default=Path("data/orientation"))
    parser.add_argument("--processus", type=int, default=4)
    args = parser.parse_args()

    args.sortie.mkdir(parents=True, exist_ok=True)
    fichiers = pages = tournees = en_serie = pages_en_serie = 0
    with (
        Pool(args.processus) as pool,
        (args.sortie / "pages_tournees.csv").open(
            "w", encoding="utf-8", newline=""
        ) as f,
    ):
        ecrivain = csv.writer(f)
        ecrivain.writerow(["fichier", "pages", "tournees", "pages_tournees"])
        for nom, n, liste in pool.imap_unordered(
            pages_tournees, pdfs(args.chemins), chunksize=4
        ):
            ecrivain.writerow([nom, n, len(liste), " ".join(f"p{p}" for p in liste)])
            fichiers += 1
            pages += n
            tournees += len(liste)
            if len(liste) >= SERIE:
                en_serie += 1
                pages_en_serie += len(liste)

    print(f"{tournees} pages tournées sur {pages}, dans {fichiers} fichiers")
    print(f"{en_serie} fichiers en ont au moins {SERIE} ({pages_en_serie} pages)")
    print(f"Écrit dans {args.sortie / 'pages_tournees.csv'}")


if __name__ == "__main__":
    main()
