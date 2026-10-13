"""Ce que vaut le repérage automatique, mesuré sur les caviardages relus (#96).

    uv run python -m anonymisation.mesure
        [--selection data/selection/selection.csv]
        [--reperes data/anonymisation/reperes.csv]
        [--typage data/typage/departements] [--annotation data/annotation]
        [--sortie data/anonymisation/mesure.md]

Pages mesurées : les pages dactylographiées des contributions exportées par
`selection`, toutes relues avant export, dans les cahiers où `anonymisation`
a tourné. Sur ces pages, la référence est ce qui a été caviardé : les
repérages que la relecture n'a pas rétablis, et les données encadrées à la
main qu'aucun d'eux ne couvrait (les oublis).

Par source et par étiquette : la précision (part des repérages non rétablis)
et le rappel (part de la référence couverte par un repérage juste de la
source). « Seule » compte la référence que cette source est seule à couvrir :
ce qu'on perdrait à la retirer. Des comptes, jamais de texte.
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from annotation.carnet import Carnet
from anonymisation.__main__ import PERSONNELLES, _ordonner
from anonymisation.masquage import CHAMPS, dans, est_retabli, fusionner
from contributions.__main__ import pages_lues

A_CACHER = PERSONNELLES | {"signature"}
TOUCHE = 0.5  # part d'un cadre dans l'autre pour qu'un repérage couvre une donnée


def touche(a: dict, b: dict) -> bool:
    return (a["fichier"], a["page"]) == (b["fichier"], b["page"]) and (
        dans(a, b) >= TOUCHE or dans(b, a) >= TOUCHE
    )


def reference(reperes: list[dict], retablis: list[dict], notes: list[dict]):
    """Ce qui a été caviardé : repérages fusionnés non rétablis, et notes
    qu'aucun d'eux ne couvre (les oublis), chacun avec son origine."""
    justes = [r for r in fusionner(reperes) if not est_retabli(r, retablis)]
    oublis = [n for n in notes if not any(touche(n, r) for r in justes)]
    return [r | {"origine": "repérage"} for r in justes] + [
        n | {"origine": "oubli"} for n in oublis
    ]


def mesurer(
    reperes: list[dict], retablis: list[dict], notes: list[dict]
) -> dict[str, dict]:
    """Par source (et « toutes ») : repérages, justes, précision ; données de
    la référence couvertes, rappel, couvertes par elle seule. Et par
    étiquette de la référence, le rappel de l'ensemble."""
    ref = reference(reperes, retablis, notes)
    justes = [r for r in reperes if not est_retabli(r, retablis)]
    par_source = defaultdict(list)
    for r in reperes:
        par_source[r["source"]].append(r)
    couvreurs = [
        {r["source"] for r in justes if touche(d, r)} for d in ref
    ]  # sources qui couvrent chaque donnée
    sortie = {}
    for source, rs in sorted(par_source.items()):
        n_justes = sum(not est_retabli(r, retablis) for r in rs)
        couvertes = sum(source in c for c in couvreurs)
        sortie[source] = {
            "reperes": len(rs),
            "justes": n_justes,
            "precision": n_justes / len(rs),
            "couvertes": couvertes,
            "rappel": couvertes / len(ref) if ref else 0.0,
            "seule": sum(c == {source} for c in couvreurs),
        }
    couvertes = sum(bool(c) for c in couvreurs)
    sortie["toutes"] = {
        "reperes": len(reperes),
        "justes": len(justes),
        "precision": len(justes) / len(reperes) if reperes else 0.0,
        "couvertes": couvertes,
        "rappel": couvertes / len(ref) if ref else 0.0,
        "seule": "",
    }
    par_etiquette = defaultdict(lambda: [0, 0])
    for d, c in zip(ref, couvreurs, strict=True):
        par_etiquette[d["etiquette"]][0] += bool(c)
        par_etiquette[d["etiquette"]][1] += 1
    precision_etiquette = defaultdict(lambda: [0, 0])
    for r in reperes:
        precision_etiquette[r["etiquette"]][0] += not est_retabli(r, retablis)
        precision_etiquette[r["etiquette"]][1] += 1
    return {
        "sources": sortie,
        "rappel": dict(par_etiquette),
        "precision": dict(precision_etiquette),
        "references": len(ref),
        "oublis": sum(d["origine"] == "oubli" for d in ref),
    }


def pourcent(a: int, b: int) -> str:
    return f"{a / b:.0%}" if b else "–"


def rapport(
    m: dict, pages: int, cahiers: int, absents: list[str], a_la_main: tuple[int, int]
) -> str:
    lignes = [
        "# Repérage automatique des données personnelles",
        "",
        (
            f"{pages} pages dactylographiées relues, dans {cahiers} contributions "
            f"exportées : {m['references']} données caviardées, dont "
            f"{m['oublis']} encadrées à la main (oublis du repérage)."
        ),
        "",
        (
            "La relecture garde caché ce qui est douteux : une fausse alerte "
            "laissée cachée compte comme juste, la précision est un majorant."
        ),
        "",
        (
            f"Sans repérage possible, sur les {a_la_main[1]} autres pages "
            f"(manuscrites, mixtes) des contributions exportées : {a_la_main[0]} données "
            "encadrées à la main."
        ),
        "",
    ]
    if absents:
        lignes += [
            "Sans repérage calculé, donc hors mesure : " + ", ".join(absents) + ".",
            "",
        ]
    lignes += [
        "## Par source",
        "",
        "| source | repérages | précision | rappel | seule à couvrir |",
        "|---|---|---|---|---|",
    ]
    for source, s in m["sources"].items():
        lignes.append(
            f"| {source} | {s['reperes']} | {s['precision']:.0%} "
            f"| {s['rappel']:.0%} | {s['seule']} |"
        )
    lignes += [
        "",
        "## Par étiquette",
        "",
        (
            "Précision : étiquette du repérage ; rappel : étiquette de la donnée "
            "caviardée (celle de la note pour un oubli)."
        ),
        "",
        "| étiquette | repérages | précision | données | rappel |",
        "|---|---|---|---|---|",
    ]
    for e in sorted(set(m["rappel"]) | set(m["precision"])):
        justes, total = m["precision"].get(e, (0, 0))
        couvertes, donnees = m["rappel"].get(e, (0, 0))
        lignes.append(
            f"| {e} | {total} | {pourcent(justes, total)} | {donnees} "
            f"| {pourcent(couvertes, donnees)} |"
        )
    return "\n".join(lignes) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--selection", type=Path, default=Path("data/selection/selection.csv")
    )
    parser.add_argument(
        "--reperes", type=Path, default=Path("data/anonymisation/reperes.csv")
    )
    parser.add_argument(
        "--typage", type=Path, nargs="+", default=[Path("data/typage/departements")]
    )
    parser.add_argument("--annotation", type=Path, default=Path("data/annotation"))
    parser.add_argument(
        "--sortie", type=Path, default=Path("data/anonymisation/mesure.md")
    )
    args = parser.parse_args()

    with args.selection.open(encoding="utf-8", newline="") as f:
        exportees = [r for r in csv.DictReader(f) if r["statut"] == "exporté"]
    with args.reperes.open(encoding="utf-8", newline="") as f:
        reperes = [
            {**r, "page": int(r["page"]), **{k: float(r[k]) for k in CHAMPS}}
            for r in csv.DictReader(f)
        ]
    calcules = {r["fichier"] for r in reperes}
    lues = pages_lues(args.typage, {e["fichier"] for e in exportees})
    pages, autres = set(), set()
    absents = []
    for e in exportees:
        dactylographiees = set(lues.get(e["fichier"], ()))
        relues = set(range(int(e["page_debut"]), int(e["page_fin"]) + 1))
        autres |= {(e["fichier"], p) for p in relues - dactylographiees}
        if not dactylographiees & relues:
            continue
        if e["fichier"] not in calcules:
            absents.append(e["commune"])
            continue
        pages |= {(e["fichier"], p) for p in dactylographiees & relues}

    carnet = Carnet(args.annotation / "notes.jsonl")
    a_cacher = [n for n in carnet.positions() if n["etiquette"] in A_CACHER]
    notes = [
        {**n, **{k: v for k, v in zip(CHAMPS, _ordonner(n))}}
        for n in a_cacher
        if (n["fichier"], n["page"]) in pages
    ]
    a_la_main = (
        sum((n["fichier"], n["page"]) in autres for n in a_cacher),
        len(autres),
    )
    retablis = [
        r for r in carnet.retablis().values() if (r["fichier"], r["page"]) in pages
    ]
    reperes = [r for r in reperes if (r["fichier"], r["page"]) in pages]
    m = mesurer(reperes, retablis, notes)
    texte = rapport(m, len(pages), len({f for f, _ in pages}), absents, a_la_main)
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    args.sortie.write_text(texte, encoding="utf-8")
    print(texte)
    print(f"Écrit dans {args.sortie}")


if __name__ == "__main__":
    main()
