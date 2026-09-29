"""Rattache les communes du corpus à leurs variables INSEE (issue #19).

    uv run python -m communes <corpus.csv> [--colonne code_insee] [--sortie data/communes]

Le fichier d'entrée a une ligne par commune et une colonne de codes INSEE ;
ses autres colonnes sont recopiées telles quelles. Sorties :

- `communes.csv` : les lignes rattachées, avec les variables de `rattachement.COLONNES` ;
- `non_rattaches.csv` : les autres, avec la raison.
"""

import argparse
import csv
from collections import Counter
from pathlib import Path

from communes.rattachement import COLONNES, Referentiel, raison_non_rattache, rattacher


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("corpus", type=Path, help="CSV d'une ligne par commune")
    parser.add_argument("--colonne", default="code_insee", help="colonne du code INSEE")
    parser.add_argument("--sortie", type=Path, default=Path("data/communes"))
    parser.add_argument("--cache", type=Path, default=Path("data/sources"))
    args = parser.parse_args()

    ref = Referentiel.telecharger(args.cache)
    with args.corpus.open(encoding="utf-8") as f:
        lecteur = csv.DictReader(f)
        entree = list(lecteur.fieldnames)
        lignes = list(lecteur)

    rattachees, rejetees = [], []
    for ligne in lignes:
        code = ligne[args.colonne].strip().upper()
        variables = rattacher(code, ref)
        if variables is None:
            rejetees.append({**ligne, "raison": raison_non_rattache(code, ref)})
        else:
            rattachees.append({**ligne, **variables})

    args.sortie.mkdir(parents=True, exist_ok=True)
    for nom, colonnes, table in (
        ("communes.csv", entree + COLONNES, rattachees),
        ("non_rattaches.csv", entree + ["raison"], rejetees),
    ):
        with (args.sortie / nom).open("w", encoding="utf-8", newline="") as f:
            ecrivain = csv.DictWriter(f, colonnes)
            ecrivain.writeheader()
            ecrivain.writerows(table)

    codes = {ligne[args.colonne] for ligne in rattachees}
    doubles = [c for c in rattachees if c["population_incluse_dans"] in codes]
    print(
        f"{len(lignes)} communes lues, {len(rattachees)} rattachées, {len(rejetees)} non."
    )
    for type_, n in Counter(c["type_2019"] for c in rattachees).most_common():
        print(f"  {n:6} {type_}")
    print(f"  {sum(not c['densite'] for c in rattachees):6} sans densité")
    print(f"  {sum(not c['population_2017'] for c in rattachees):6} sans population")
    print(f"  {sum(bool(c['note']) for c in rattachees):6} avec une note")
    print(
        f"  {len(doubles):6} dont la population est déjà comptée dans une commune "
        "parente du corpus (ne pas sommer)"
    )
    for raison, n in Counter(r["raison"] for r in rejetees).most_common():
        print(f"  non rattachés : {n} — {raison}")
    print(f"Écrit dans {args.sortie}/")


if __name__ == "__main__":
    main()
