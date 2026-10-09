"""Pages d'ouverture imprimées des cahiers citoyens (issue #5).

    uv run python -m ouvertures [--versement data/versement]
        [--typage data/typage/departements] [--sortie data/ouvertures]
        [--processus 4]

Règle dans `ouvertures.ouvertures`. Pour chaque département du typage, lit la
première page dactylographiée (hors service) des cahiers citoyens, puis les
autres pages des cahiers qui portent le modèle du département. Écrit
`ouvertures.csv` dans la sortie : une ligne par page d'ouverture (fichier,
page). `contributions` et `chabin` ne cherchent pas de contribution sur ces
pages. Des noms de fichiers et des comptes, jamais de texte.
"""

import argparse
import csv
from multiprocessing import Pool
from pathlib import Path

from ouvertures.ouvertures import departement


def lire(chemin: Path) -> set[tuple[str, int]]:
    """Les pages d'ouverture écrites par cette commande (vide sans fichier)."""
    if not chemin.exists():
        return set()
    with chemin.open(encoding="utf-8", newline="") as f:
        return {(ligne["fichier"], int(ligne["page"])) for ligne in csv.DictReader(f)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--versement", type=Path, default=Path("data/versement"))
    parser.add_argument("--typage", type=Path, default=Path("data/typage/departements"))
    parser.add_argument("--sortie", type=Path, default=Path("data/ouvertures"))
    parser.add_argument("--processus", type=int, default=4)
    args = parser.parse_args()

    chemins = {
        p.name: p for p in args.versement.rglob("CC_*.pdf", recurse_symlinks=True)
    }
    tables = sorted(args.typage.glob("*.csv"))
    with Pool(args.processus) as pool:
        resultats = pool.map(departement, [(t, chemins) for t in tables])

    args.sortie.mkdir(parents=True, exist_ok=True)
    with (args.sortie / "ouvertures.csv").open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(["fichier", "page"])
        for _, _, ouvertures in resultats:
            ecrivain.writerows(ouvertures)
    total = sum(len(o) for _, _, o in resultats)
    print(f"{total} pages d'ouverture dans {len(tables)} départements")
    for nom, lus, ouvertures in sorted(resultats, key=lambda r: -len(r[2])):
        if ouvertures:
            print(f"  {nom} : {len(ouvertures)} sur {lus} cahiers lus")


if __name__ == "__main__":
    main()
