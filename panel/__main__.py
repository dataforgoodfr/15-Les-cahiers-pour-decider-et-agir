"""Panel de cahiers citoyens aligné sur l'échantillon du Campus Condorcet (issue #22).

    uv run python -m panel --typage <csv ou dossier>...
        [--communes data/communes/communes.csv] [--sortie data/panel]
        [--departements 04 23 ...] [--insee 33063 ...]

Le typage est la sortie de `python -m typage` ; la table des communes, celle de
`python -m communes` (#19). Par défaut, les départements et les communes de
l'échantillon du Campus (`panel.panel`). Écrit dans la sortie :

- `cahiers.csv` : les cahiers du panel, avec leurs pages par type ;
- `communes.csv` : les communes du panel, au format de la table d'entrée.

Pour comparer le panel à la France :

    uv run python -m communes.representativite data/panel/communes.csv \\
        --sortie data/panel/representativite
"""

import argparse
import csv
from pathlib import Path

from panel.panel import (
    COMMUNES_CAMPUS,
    DEPARTEMENTS_CAMPUS,
    cahiers,
    communes_du_panel,
    lire_typage,
    par_departement,
)


def ecrire(chemin: Path, lignes: list[dict]) -> None:
    with chemin.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, list(lignes[0]))
        ecrivain.writeheader()
        ecrivain.writerows(lignes)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--typage", type=Path, nargs="+", required=True)
    parser.add_argument(
        "--communes", type=Path, default=Path("data/communes/communes.csv")
    )
    parser.add_argument("--sortie", type=Path, default=Path("data/panel"))
    parser.add_argument("--departements", nargs="+", default=DEPARTEMENTS_CAMPUS)
    parser.add_argument("--insee", nargs="+", default=COMMUNES_CAMPUS)
    args = parser.parse_args()

    departements, insee = set(args.departements), set(args.insee)
    panel = cahiers(lire_typage(args.typage), departements, insee)
    communes = communes_du_panel(args.communes, departements, insee)

    args.sortie.mkdir(parents=True, exist_ok=True)
    ecrire(args.sortie / "cahiers.csv", panel)
    ecrire(args.sortie / "communes.csv", communes)

    for cle, c in par_departement(panel, insee).items():
        print(
            f"{cle:>6} : {c['cahiers']:>4} cahiers, {c['pages']:>6} pages, "
            f"{c['ecrites']:>6} écrites"
        )
    absents = sorted(departements - {c["departement"] for c in panel})
    if absents:
        print(f"Sans cahier citoyen : {', '.join(absents)}")
    print(
        f"Panel : {len(panel)} cahiers, {len(communes)} communes, "
        f"{sum(c['pages'] for c in panel)} pages. Écrit dans {args.sortie}"
    )


if __name__ == "__main__":
    main()
