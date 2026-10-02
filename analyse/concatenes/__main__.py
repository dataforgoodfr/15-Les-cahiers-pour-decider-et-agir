"""Fichiers de cahiers citoyens qui contiennent le cahier d'une autre commune (issue #42).

    uv run python -m concatenes <pdf ou dossier>... [--sortie data/concatenes]
        [--cache data/sources] [--processus 4]

Les dossiers sont ceux des cahiers citoyens du versement (`BnF_GDN_XX_PDF/CC`).
Écrit `concatenes.csv` dans la sortie : une ligne par fichier, avec sa
catégorie, les pages de garde d'autres communes et leurs codes INSEE, les
pages qui leur reviennent, et les pages de garde illisibles à vérifier. Des codes et des comptes, jamais de texte.
"""

import argparse
import csv
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

from communes.rattachement import Referentiel
from concatenes.concatenes import classer, lire, pages_d_autres_communes
from typage.__main__ import pdfs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("chemins", type=Path, nargs="+")
    parser.add_argument("--sortie", type=Path, default=Path("data/concatenes"))
    parser.add_argument("--cache", type=Path, default=Path("data/sources"))
    parser.add_argument("--processus", type=int, default=4)
    args = parser.parse_args()

    ref = Referentiel.telecharger(args.cache)
    noms = {code: ligne["libelle"] for code, ligne in ref.cog.items()}
    parentes = {
        code: ligne["comparent"]
        for code, ligne in ref.cog.items()
        if ligne["comparent"]
    }

    args.sortie.mkdir(parents=True, exist_ok=True)
    categories, pages = Counter(), Counter()
    with (
        Pool(args.processus) as pool,
        (args.sortie / "concatenes.csv").open("w", encoding="utf-8", newline="") as f,
    ):
        ecrivain = csv.writer(f)
        ecrivain.writerow(
            [
                "fichier",
                "pages",
                "pages_de_garde",
                "categorie",
                "autres_communes",
                "pages_autres_communes",
                "gardes_illisibles",
            ]
        )
        for fichier in pool.imap_unordered(lire, pdfs(args.chemins), chunksize=20):
            categorie, trouvees, illisibles = classer(fichier, noms, parentes)
            autres = pages_d_autres_communes(fichier, trouvees)
            categories[categorie] += 1
            pages[categorie] += autres
            ecrivain.writerow(
                [
                    fichier.nom,
                    fichier.pages,
                    len(fichier.gardes),
                    categorie,
                    " ".join(
                        f"p{p}:{'/'.join(c)}" for p, c in sorted(trouvees.items())
                    ),
                    autres,
                    " ".join(f"p{p}" for p in illisibles),
                ]
            )

    for categorie, n in categories.most_common():
        print(f"{n:8} {categorie} ({pages[categorie]} pages d'autres communes)")
    print(f"Écrit dans {args.sortie / 'concatenes.csv'}")


if __name__ == "__main__":
    main()
