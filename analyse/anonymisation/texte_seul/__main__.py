"""Le texte des contributions de tout le corpus, anonymisé sans LLM (#128).

    uv run python -m anonymisation.texte_seul
        [--contributions data/decoupage/corpus/contributions.csv]
        [--versement data/versement] [--typage data/typage/departements]
        [--communes data/communes/communes.csv] [--cache data/sources]
        [--processus 4] [--sortie data/anonymisation/texte_seul]

La chaîne en texte seul mesurée par `anonymisation.blanche`, sans modèle :
les règles de `detection` (filtrées comme dans `factices.garde`, noms
répandus d'une commune à l'autre compris), la liste blanche
(`blanche.raison`) et les zones de signature (`anonymisation.zones`). Sur les
cahiers délimités à la main, elle couvre 89 % des données personnelles
encadrées, et une donnée reste visible dans 151 contributions sur 837.

Les contributions sont celles du découpage automatique (`python -m
decoupage.corpus`), sur les pages imprimées ; leur texte est la couche
texte du versement (OCR d'ABBYY). Deux passes : la première relève les noms
que les règles repèrent, pour savoir lesquels reviennent dans plusieurs
communes (des personnalités) ; la seconde cache le texte.

Écrit `contributions.csv` dans la sortie : par contribution, ses mots, ses
mots cachés et son texte, chaque suite de mots cachés remplacée par « […] ».
Ce texte n'est relu par personne : il reste dans `data/`, hors git. La
commande n'affiche que des comptes.
"""

import argparse
import csv
import statistics
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

from anonymisation.blanche import lieux
from anonymisation.delimites import references
from anonymisation.detection import _simple
from anonymisation.factices import repandus
from anonymisation.texte_seul.cahier import anonymiser, initialiser, noms
from decoupage.contributions.__main__ import IMPRIMEES
from panels.panel.panel import code_insee, lire_typage

COLONNES = ["fichier", "rang", "page_debut", "page_fin", "mots", "caches", "texte"]
LISIBLE = 20  # mots visibles au moins d'une contribution qu'on peut lire


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--contributions",
        type=Path,
        default=Path("data/decoupage/corpus/contributions.csv"),
    )
    parser.add_argument("--versement", type=Path, default=Path("data/versement"))
    parser.add_argument(
        "--typage", type=Path, nargs="+", default=[Path("data/typage/departements")]
    )
    parser.add_argument(
        "--communes", type=Path, default=Path("data/communes/communes.csv")
    )
    parser.add_argument("--cache", type=Path, default=Path("data/sources"))
    parser.add_argument("--processus", type=int, default=4)
    parser.add_argument(
        "--sortie", type=Path, default=Path("data/anonymisation/texte_seul")
    )
    args = parser.parse_args()

    if not args.contributions.exists():
        parser.error(f"pas de {args.contributions} : lancer python -m decoupage.corpus")
    par_cahier = defaultdict(list)
    with args.contributions.open(encoding="utf-8", newline="") as f:
        for c in csv.DictReader(f):
            par_cahier[c["fichier"]].append(c)
    imprimees = defaultdict(set)
    for ligne in lire_typage(args.typage):
        if ligne["fichier"] in par_cahier and ligne["type_page"] in IMPRIMEES:
            imprimees[ligne["fichier"]].add(int(ligne["page"]))
    chemins = {
        p.name: p
        for p in args.versement.rglob("CC_*.pdf", recurse_symlinks=True)
        if p.name in par_cahier
    }
    pages = {
        f: sorted(
            imprimees[f]
            & {
                n
                for c in cs
                for n in range(int(c["page_debut"]), int(c["page_fin"]) + 1)
            }
        )
        for f, cs in par_cahier.items()
        if f in chemins
    }

    prenoms, lexique, publics_, nom_commune = references(args, set(pages))
    lieux_ = lieux(args.cache)
    ref = {
        "prenoms": frozenset(prenoms),
        "simples": {_simple(p) for p in prenoms},
        "lexique": lexique,
        "noms": publics_,
        "surs": {f: n._replace(seuls=n.seuls | lieux_) for f, n in publics_.items()},
        "communes": {f: nom_commune.get(code_insee(f) or "", "") for f in pages},
        "repandus": set(),
    }

    fichiers = sorted(pages)
    with Pool(args.processus, initialiser, (ref,)) as pool:
        trouves = pool.map(
            noms, [(chemins[f], f, pages[f]) for f in fichiers], chunksize=8
        )
    textes = [
        {
            "insee": code_insee(f) or f,
            "reperes": [{"etiquette": e, "texte": t} for e, t in trouves_],
        }
        for f, trouves_ in zip(fichiers, trouves, strict=True)
    ]
    ref["repandus"] = repandus(textes)
    print(
        f"Première passe : {len(fichiers)} cahiers, {len(ref['repandus'])} noms "
        "répandus dans plusieurs communes",
        flush=True,
    )

    lignes = []
    with Pool(args.processus, initialiser, (ref,)) as pool:
        taches = [(chemins[f], f, pages[f], par_cahier[f]) for f in fichiers]
        for sortie in pool.imap(anonymiser, taches, chunksize=8):
            lignes += sortie

    args.sortie.mkdir(parents=True, exist_ok=True)
    with (args.sortie / "contributions.csv").open(
        "w", encoding="utf-8", newline=""
    ) as f:
        ecrivain = csv.DictWriter(f, COLONNES)
        ecrivain.writeheader()
        ecrivain.writerows(lignes)

    mots = sum(x["mots"] for x in lignes)
    caches = sum(x["caches"] for x in lignes)
    visibles = [x["mots"] - x["caches"] for x in lignes]
    parts = [x["caches"] / x["mots"] for x in lignes if x["mots"]]
    print(
        f"{len(lignes)} contributions, {mots} mots, dont {caches} cachés "
        f"({caches / mots:.0%}), dans {args.sortie / 'contributions.csv'}"
    )
    print(
        f"  sans aucun mot dans la couche texte : {sum(1 for x in lignes if not x['mots'])}"
    )
    print(
        f"  {LISIBLE} mots visibles ou plus : "
        f"{sum(v >= LISIBLE for v in visibles)} ({sum(v >= LISIBLE for v in visibles) / len(lignes):.0%})"
    )
    print(
        "  part cachée par contribution : médiane "
        f"{statistics.median(parts):.0%}, quartiles "
        + ", ".join(f"{q:.0%}" for q in statistics.quantiles(parts, n=4))
    )


if __name__ == "__main__":
    main()
