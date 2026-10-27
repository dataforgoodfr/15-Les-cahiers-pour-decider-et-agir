"""Mots-clés, LLM et annotateurs sur les sous-thèmes des propositions (issue #24).

    uv run python -m classement.themes.accord [--revue data/themes/revue.csv]
        [--journaux data/annotation/themes.jsonl ...]
        [--chabin ../data/cahiers_chabin-extraction.json]
        [--llm-contributions data/themes/haiku]
        [--llm-propositions data/themes/llm-propositions]

Lit la liste à revoir (`python -m classement.themes.revue`) et les journaux
de l'outil d'annotation (`/themes`, `annotation.themes`), un par machine au
besoin. Chaque sous-thème de la grille est, pour chaque proposition, une
décision oui ou non ; les propositions signalées mal coupées sont mises de
côté. Les réponses d'un LLM sont des TSV, `identifiant<TAB>sous-thème | …`
ou `aucun`. Affiche :

- par proposition : l'accord des annotateurs entre eux (le plafond qu'une
  méthode peut espérer), puis la précision, le rappel et le kappa médian par
  sous-thème des mots-clés et du LLM face à chacun ;
- par contribution, en réunissant les sous-thèmes de ses propositions : les
  mêmes mesures, les mots-clés portant sur le texte entier de l'édition ;
  seules comptent les contributions dont l'annotateur a fait toutes les
  propositions.

Des comptes, jamais de texte.
"""

import argparse
import csv
import json
import statistics
from collections import defaultdict
from itertools import combinations
from pathlib import Path

from annotation.paires import kappa
from annotation.themes import NOMS, JournalThemes, etat
from classement.themes.sous_themes import sous_themes

OCCURRENCES_MIN = 3  # oui, au moins, pour un kappa par sous-thème


def lire_llm(dossier: Path) -> dict[str, set[str]]:
    reponses = {}
    for chemin in sorted(dossier.glob("*.tsv")) if dossier.exists() else []:
        for ligne in chemin.read_text(encoding="utf-8").splitlines():
            if "\t" not in ligne:
                continue
            ident, valeur = ligne.split("\t", 1)
            reponses[ident] = (
                set()
                if valeur.strip() == "aucun"
                else {s.strip() for s in valeur.split("|")} & set(NOMS)
            )
    return reponses


def scores(
    predit: dict[str, set[str]], vrai: dict[str, set[str]], unites: list[str]
) -> dict:
    """Sous-thèmes en commun, précision, rappel et kappa médian par
    sous-thème de `predit` face à `vrai`."""
    vp = sum(len(predit[u] & vrai[u]) for u in unites)
    oui = sum(len(predit[u]) for u in unites)
    vrais = sum(len(vrai[u]) for u in unites)
    kappas = []
    for s in NOMS:
        couples = [(s in predit[u], s in vrai[u]) for u in unites]
        if sum(x or y for x, y in couples) >= OCCURRENCES_MIN:
            kappas.append(kappa(couples))
    return {
        "communs": vp,
        "precision": vp / oui if oui else 0.0,
        "rappel": vp / vrais if vrais else 0.0,
        "kappa": statistics.median(kappas) if kappas else None,
        "sous_themes": len(kappas),
    }


def _kappa(s: dict) -> str:
    k = "—" if s["kappa"] is None else f"{s['kappa']:.2f}"
    return f"kappa médian {k} ({s['sous_themes']} sous-thèmes)"


def rapport(
    humains: dict[str, dict[str, set[str]]], methodes: dict[str, dict[str, set[str]]]
) -> list[str]:
    """`humains` : {annotateur: {unité: sous-thèmes}} ; `methodes` : {nom:
    {unité: sous-thèmes}}, sans les unités auxquelles la méthode n'a pas
    répondu."""
    sortie = []
    for a, b in combinations(sorted(humains), 2):
        communes = sorted(humains[a].keys() & humains[b].keys())
        if communes:
            s = scores(humains[a], humains[b], communes)
            sortie.append(
                f"  {a} et {b}, {len(communes)} unités : {s['communs']} sous-thèmes "
                f"en commun, {s['precision']:.0%} des siens pour {a}, "
                f"{s['rappel']:.0%} pour {b}, {_kappa(s)}"
            )
    for a, siennes in sorted(humains.items()):
        for nom, reponses in methodes.items():
            unites = sorted(siennes.keys() & reponses.keys())
            if unites:
                s = scores(reponses, siennes, unites)
                sortie.append(
                    f"  {nom} face à {a}, {len(unites)} unités : précision "
                    f"{s['precision']:.0%}, rappel {s['rappel']:.0%}, {_kappa(s)}"
                )
    return sortie


def par_contribution(
    humains: dict[str, dict[str, set[str]]],
    propositions: dict[str, set[str]],
    mal_coupees: set[str],
) -> dict[str, dict[str, set[str]]]:
    """Les sous-thèmes des propositions réunis par contribution, pour les
    contributions dont l'annotateur a fait toutes les propositions bien
    coupées."""
    sortie: dict[str, dict[str, set[str]]] = defaultdict(dict)
    for a, siennes in humains.items():
        for c, ps in propositions.items():
            if ps - mal_coupees <= siennes.keys():
                sortie[a][c] = set().union(*(siennes.get(p, set()) for p in ps))
    return sortie


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--revue", type=Path, default=Path("data/themes/revue.csv"))
    parser.add_argument(
        "--journaux",
        type=Path,
        nargs="+",
        default=[Path("data/annotation/themes.jsonl")],
    )
    parser.add_argument(
        "--chabin", type=Path, default=Path("../data/cahiers_chabin-extraction.json")
    )
    parser.add_argument(
        "--llm-contributions", type=Path, default=Path("data/themes/haiku")
    )
    parser.add_argument(
        "--llm-propositions", type=Path, default=Path("data/themes/llm-propositions")
    )
    args = parser.parse_args()

    with args.revue.open(encoding="utf-8", newline="") as f:
        revue = list(csv.DictReader(f))
    contribution_de = {x["proposition"]: x["contribution"] for x in revue}
    annotations = etat(
        [e for j in args.journaux for e in JournalThemes(j).evenements()]
    )
    humains: dict[str, dict[str, set[str]]] = defaultdict(dict)
    mal_coupees = set()
    for p, par in annotations.items():
        if p not in contribution_de:
            continue
        for a, x in par.items():
            if x["mal_coupee"]:
                mal_coupees.add(p)
            else:
                humains[a][p] = x["sous_themes"]
    print(
        f"{sum(len(x) for x in humains.values())} annotations de "
        f"{len({p for x in humains.values() for p in x})} propositions sur "
        f"{len(revue)}, par {len(humains)} annotateurs ; "
        f"{len(mal_coupees)} propositions signalées mal coupées"
    )
    if not humains:
        return

    print("\nPar proposition :")
    methodes = {
        "mots-clés": {x["proposition"]: sous_themes(x["texte"]) for x in revue},
        "LLM": lire_llm(args.llm_propositions),
    }
    print("\n".join(rapport(humains, methodes)))

    print("\nPar contribution (sous-thèmes de ses propositions réunis) :")
    propositions = defaultdict(set)
    for x in revue:
        propositions[x["contribution"]].add(x["proposition"])
    extraction = json.loads(args.chabin.read_text(encoding="utf-8"))
    textes = {
        f"{e['city']['insee']}-{rang}": c["text"]
        for e in extraction
        if e
        for rang, c in enumerate(e["contributions"], 1)
    }
    llm = lire_llm(args.llm_contributions)
    methodes = {
        "mots-clés": {c: sous_themes(textes[c]) for c in propositions},
        "LLM": {c: llm[c] for c in propositions if c in llm},
    }
    lignes = rapport(par_contribution(humains, propositions, mal_coupees), methodes)
    print("\n".join(lignes) or "  aucune contribution finie")


if __name__ == "__main__":
    main()
