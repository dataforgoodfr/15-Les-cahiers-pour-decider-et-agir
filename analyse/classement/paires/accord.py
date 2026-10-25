"""Accord des annotateurs sur les paires de propositions (issue #94).

    uv run python -m classement.paires.accord [--journaux data/annotation/paires.jsonl ...]

Lit les journaux de jugements de l'outil d'annotation (tâche « paires »,
`annotation.paires`), un par machine au besoin. Affiche, pour chaque couple
d'annotateurs, les paires jugées par les deux et leur kappa de Cohen, le
plafond qu'une méthode peut espérer, puis les litiges adjugés ou non. Des
comptes, jamais de texte.
"""

import argparse
from collections import Counter
from itertools import combinations
from pathlib import Path

from annotation.paires import Journal, etat, kappa, litiges, retenus


def couples(jugements: dict) -> dict[tuple[str, str], list[tuple[str, str]]]:
    """Par couple d'annotateurs (ordre alphabétique), leurs jugements des
    paires jugées par les deux."""
    sortie: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for par in jugements.values():
        for a, b in combinations(sorted(par), 2):
            sortie.setdefault((a, b), []).append((par[a], par[b]))
    return sortie


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--journaux",
        type=Path,
        nargs="+",
        default=[Path("data/annotation/paires.jsonl")],
    )
    args = parser.parse_args()

    evenements = [e for j in args.journaux for e in Journal(j).evenements()]
    jugements, adjudications = etat(evenements)
    jugees = {p for p, par in jugements.items() if par}
    print(f"{len(jugees)} paires jugées")
    for (a, b), liste in sorted(couples(jugements).items()):
        k = kappa(liste)
        accord = sum(x == y for x, y in liste) / len(liste)
        print(f"  {a} et {b} : {len(liste)} paires, accord {accord:.0%}, kappa {k:.2f}")
    en_litige = litiges(jugements)
    print(
        f"{len(en_litige)} litiges, "
        f"{sum(p in adjudications for p in en_litige)} adjugés"
    )
    finals = retenus(jugements, adjudications)
    print(f"{len(finals)} paires au jugement retenu (accord ou adjudication)")
    par_jugement = Counter(finals.values())
    for jugement, n in par_jugement.most_common():
        print(f"  {jugement} : {n}")


if __name__ == "__main__":
    main()
