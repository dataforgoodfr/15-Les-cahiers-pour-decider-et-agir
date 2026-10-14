import argparse
import csv
import json
import random
import statistics
from collections import Counter
from pathlib import Path

from propositions import __doc__ as DOC
from propositions.decoupage import decouper

COLONNES = ["insee", "commune", "rang", "numero", "forme", "contexte", "texte"]
A_REMPLIR = ["decoupage", "nature"]


def lignes(extraction: list[dict | None]) -> list[dict]:
    """Une ligne par proposition ; une contribution sans proposition a une
    ligne sans texte, pour que la vérification la voie."""
    sortie = []
    for e in extraction:
        if not e:
            continue
        for rang, c in enumerate(e["contributions"], 1):
            base = {
                "insee": e["city"]["insee"],
                "commune": e["city"]["commune"],
                "rang": rang,
            }
            propositions = decouper(c["text"])
            if not propositions:
                sortie.append(
                    base | {"numero": "", "forme": "", "contexte": "", "texte": ""}
                )
            for numero, p in enumerate(propositions, 1):
                sortie.append(
                    base
                    | {
                        "numero": numero,
                        "forme": p.forme,
                        "contexte": p.contexte,
                        "texte": p.texte,
                    }
                )
    return sortie


def echantillon(lignes_: list[dict], n: int, graine: int) -> list[dict]:
    """Les lignes de `n` contributions tirées au hasard, dans l'ordre."""
    contributions = sorted({(x["insee"], x["rang"]) for x in lignes_})
    tirees = set(
        random.Random(graine).sample(contributions, min(n, len(contributions)))
    )
    return [
        x | dict.fromkeys(A_REMPLIR, "")
        for x in lignes_
        if (x["insee"], x["rang"]) in tirees
    ]


def ecrire(chemin: Path, lignes_: list[dict], colonnes: list[str]) -> None:
    with chemin.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, colonnes)
        ecrivain.writeheader()
        ecrivain.writerows(lignes_)


def main() -> None:
    parser = argparse.ArgumentParser(description=DOC.splitlines()[0])
    parser.add_argument(
        "--extraction",
        type=Path,
        default=Path("../data/cahiers_chabin-extraction.json"),
    )
    parser.add_argument("--echantillon", type=int, default=50)
    parser.add_argument("--graine", type=int, default=0)
    parser.add_argument("--sortie", type=Path, default=Path("data/propositions"))
    args = parser.parse_args()

    extraction = json.loads(args.extraction.read_text(encoding="utf-8"))
    toutes = lignes(extraction)
    args.sortie.mkdir(parents=True, exist_ok=True)
    ecrire(args.sortie / "propositions.csv", toutes, COLONNES)
    tirees = echantillon(toutes, args.echantillon, args.graine)
    ecrire(args.sortie / "verification.csv", tirees, COLONNES + A_REMPLIR)

    propositions = [x for x in toutes if x["texte"]]
    par_contribution = Counter((x["insee"], x["rang"]) for x in propositions)
    contributions = {(x["insee"], x["rang"]) for x in toutes}
    formes = Counter(x["forme"] for x in propositions)
    mots = sorted(len(x["texte"].split()) for x in propositions)
    print(
        f"{len(propositions)} propositions dans {len(contributions)} contributions "
        f"({len(contributions) - len(par_contribution)} sans proposition)"
    )
    print(
        "  par contribution : médiane "
        f"{statistics.median(par_contribution.get(c, 0) for c in contributions)}, "
        f"au plus {max(par_contribution.values())}"
    )
    print(
        f"  formes : {formes['puce']} puces, {formes['phrase']} phrases ; "
        f"{sum(1 for x in propositions if x['contexte'])} sous un intitulé"
    )
    print(
        f"  mots : médiane {statistics.median(mots)}, "
        f"9e décile {mots[len(mots) * 9 // 10]}, au plus {mots[-1]}"
    )
    print(
        f"À vérifier : {len({(x['insee'], x['rang']) for x in tirees})} "
        f"contributions, {sum(1 for x in tirees if x['texte'])} propositions "
        f"({args.sortie / 'verification.csv'})"
    )


if __name__ == "__main__":
    main()
