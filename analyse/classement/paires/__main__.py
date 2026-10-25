import argparse
import csv
import random
from pathlib import Path

from classement.paires import __doc__ as DOC
from classement.paires.plongements import MODELE, plongements
from classement.paires.tirage import HASARD, REGLAGE, TEST, lots, tirer

PROPOSITION = ["insee", "commune", "rang", "numero", "contexte", "texte"]
COLONNES = (
    ["paire", "lot", "tranche", "similarite"]
    + [f"a_{c}" for c in PROPOSITION]
    + [f"b_{c}" for c in PROPOSITION]
)


def lire(chemin: Path) -> list[dict]:
    with chemin.open(encoding="utf-8", newline="") as f:
        return [x for x in csv.DictReader(f) if x["texte"]]


def main() -> None:
    parser = argparse.ArgumentParser(description=DOC.splitlines()[0])
    parser.add_argument(
        "--propositions", type=Path, default=Path("data/propositions/propositions.csv")
    )
    parser.add_argument("--modele", default=MODELE)
    parser.add_argument("--tranches", type=int, default=5)
    parser.add_argument("--par-tranche", type=int, default=100)
    parser.add_argument("--hasard", type=int, default=100)
    parser.add_argument("--reglage", type=float, default=0.33)
    parser.add_argument("--graine", type=int, default=0)
    parser.add_argument("--sortie", type=Path, default=Path("data/paires"))
    args = parser.parse_args()

    propositions = lire(args.propositions)
    textes = [p["texte"] for p in propositions]
    groupes = [(p["insee"], p["rang"]) for p in propositions]
    vecteurs = plongements(textes, args.modele, args.sortie / "plongements.npz")
    tirees = tirer(
        vecteurs,
        groupes,
        textes,
        args.tranches,
        args.par_tranche,
        args.hasard,
        args.graine,
    )
    lots(tirees, args.reglage, args.graine)
    # l'ordre du fichier ne trahit ni la tranche ni la similarité
    random.Random(args.graine).shuffle(tirees)

    args.sortie.mkdir(parents=True, exist_ok=True)
    with (args.sortie / "paires.csv").open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, COLONNES)
        ecrivain.writeheader()
        for n, p in enumerate(tirees, 1):
            a, b = propositions[p["i"]], propositions[p["j"]]
            ecrivain.writerow(
                {
                    "paire": n,
                    "lot": p["lot"],
                    "tranche": p["tranche"],
                    "similarite": f"{p['similarite']:.3f}",
                }
                | {f"a_{c}": a[c] for c in PROPOSITION}
                | {f"b_{c}": b[c] for c in PROPOSITION}
            )

    print(f"{len(propositions)} propositions plongées ({args.modele})")
    print(f"{len(tirees)} paires tirées ({args.sortie / 'paires.csv'})")
    noms = sorted({p["tranche"] for p in tirees}, key=lambda t: (t == HASARD, t))
    for t in noms:
        dans = [p for p in tirees if p["tranche"] == t]
        sims = sorted(p["similarite"] for p in dans)
        print(
            f"  {'tranche ' + t if t != HASARD else 'au hasard'} : {len(dans)} paires, "
            f"similarité {sims[0]:.2f} à {sims[-1]:.2f}, "
            f"{sum(p['lot'] == REGLAGE for p in dans)} réglage, "
            f"{sum(p['lot'] == TEST for p in dans)} test"
        )


if __name__ == "__main__":
    main()
