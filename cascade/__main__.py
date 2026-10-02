"""Cascade du corpus : du versement BnF aux pages écrites des cahiers citoyens.

    uv run python -m cascade <racine du versement> --typage <csv ou dossier>...
        [--sortie data/cascade] [--figure docs/cascade.svg]

La racine du versement contient les dossiers `BnF_GDN_XX_PDF` ; le typage est
la sortie de `python -m typage` (un fichier, ou un dossier de fichiers). Écrit
`cascade.csv` dans la sortie et la figure SVG.
"""

import argparse
import datetime
from pathlib import Path

from cascade.cascade import (
    compter_versement,
    ecrire_csv,
    lire_typage,
    milliers,
    niveaux,
    svg,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("racine", type=Path)
    parser.add_argument("--typage", type=Path, nargs="+", required=True)
    parser.add_argument("--sortie", type=Path, default=Path("data/cascade"))
    parser.add_argument("--figure", type=Path, default=Path("docs/cascade.svg"))
    args = parser.parse_args()

    documents, pages = compter_versement(args.racine)
    cascade = niveaux(pages, lire_typage(args.typage))

    args.sortie.mkdir(parents=True, exist_ok=True)
    ecrire_csv(args.sortie / "cascade.csv", cascade, documents)
    args.figure.parent.mkdir(parents=True, exist_ok=True)
    args.figure.write_text(
        svg(cascade, datetime.datetime.now().astimezone().date().isoformat()),
        encoding="utf-8",
    )

    for niveau in cascade:
        print(f"{niveau.titre} : {milliers(niveau.pages)} pages")
        for s in niveau.segments:
            part = s.pages / niveau.pages if niveau.pages else 0
            print(f"  {milliers(s.pages):>9} {s.libelle} ({part:.0%})")
    print(f"Écrit dans {args.sortie / 'cascade.csv'} et {args.figure}")


if __name__ == "__main__":
    main()
