"""Place de chaque sous-thème dans les contributions et le corpus (issue #24).

    uv run python -m classement.themes [--delimitation data/delimitation/contributions.csv]
        [--versement data/versement] [--typage data/typage/departements]
        [--ouvertures data/ouvertures/ouvertures.csv]
        [--vrai-debat ../data/vrai-debat/1059propositionsvraidébat.pdf]
        [--sans-corpus] [--sortie data/themes]

Trois mesures, par sous-thème (`classement.themes.sous_themes`) :

- **contributions** : les contributions délimitées à la main
  (`python -m decoupage.delimitation`) qui ont du texte dactylographié ;
- **cahiers** : les cahiers du versement qui ont des pages dactylographiées
  (hors pages de service et d'ouverture). Long : `--sans-corpus` le saute ;
- **Vrai débat** : les propositions de la plateforme du Vrai débat, et la
  part des votes qu'elles ont reçus.

Les lignes qui reviennent au moins `REPETEE` fois dans un même cahier sont
retirées avant le repérage : les questions imprimées d'un formulaire (dont
ceux du Grand débat) ne comptent pas comme le sujet d'une contribution.

Écrit `frequences.md` dans la sortie, et le vocabulaire fréquent des
contributions qu'aucun sous-thème ne touche : des mots présents dans au
moins `CAHIERS_MIN` cahiers différents, pour trouver ce qui manque à la
liste sans lire de contribution. Des comptes et des mots courants, jamais
d'extrait.
"""

import argparse
import csv
import re
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pymupdf

from classement.themes.lecture import (
    TEXTE_MIN,
    cahier,
    lignes_de_page,
    lignes_imprimees,
    texte,
)
from classement.themes.sous_themes import AJOUTS, THEMES, TOUS, normaliser, sous_themes
from corpus.ouvertures.__main__ import lire as lire_ouvertures
from decoupage.contributions.__main__ import pages_lues

CAHIERS_MIN = 10  # cahiers au moins où un mot paraît pour être montré
MOTS_VIDES = set(
    normaliser(
        "le la les un une des du de d l et ou a au aux en dans par pour sur avec "
        "sans sous ce cet cette ces se sa son ses leur leurs nos notre vos votre "
        "qui que quoi dont ne pas plus moins tres tout tous toute toutes il ils "
        "elle elles on nous vous je j me m mon ma mes est sont etre ete avoir ont "
        "fait faire faut doit doivent peut peuvent comme mais donc car si y n s c "
        "qu aussi bien meme autres autre deja ainsi entre etc cela ca celle ceux "
        "lui aujourd hui afin depuis avant apres encore chaque non oui"
    ).split()
)


def mesurer_contributions(delimitation: Path, chemins: dict, lues: dict):
    """Sous-thèmes de chaque contribution qui a du texte dactylographié, et
    les mots des contributions qu'aucun ne touche (mot -> cahiers)."""
    par_cahier = defaultdict(list)
    with delimitation.open(encoding="utf-8", newline="") as f:
        for x in csv.DictReader(f):
            par_cahier[x["fichier"]].append(x)
    resultats, orphelins = [], defaultdict(set)
    for fichier, contributions in sorted(par_cahier.items()):
        dactylo = set(lues.get(fichier, ()))
        if not dactylo or fichier not in chemins:
            continue
        with pymupdf.open(chemins[fichier]) as doc:
            imprimees = lignes_imprimees(
                [lignes_de_page(doc[n - 1]) for n in sorted(dactylo)]
            )
            for c in contributions:
                debut, fin = int(c["page_debut"]), int(c["page_fin"])
                lignes = []
                for n in range(debut, fin + 1):
                    if n not in dactylo:
                        continue
                    haut = float(c["y_debut"]) if n == debut and c["y_debut"] else None
                    bas = float(c["y_fin"]) if n == fin and c["y_fin"] else None
                    lignes += lignes_de_page(doc[n - 1], haut, bas)
                t = texte(lignes, imprimees)
                if len(t) < TEXTE_MIN:
                    continue
                trouves = sous_themes(t)
                resultats.append(trouves)
                if not trouves:
                    for mot in set(normaliser(t).split()):
                        if len(mot) > 3 and mot not in MOTS_VIDES:
                            orphelins[mot].add(fichier)
    return resultats, orphelins


def mesurer_corpus(chemins: dict, lues: dict) -> list[set[str]]:
    taches = [(f, chemins[f], n) for f, n in sorted(lues.items()) if f in chemins]
    with ProcessPoolExecutor() as ex:
        return [r[1] for r in ex.map(cahier, taches, chunksize=20) if r]


PROPOSITION = re.compile(r"\[n°\d+\]")
VOTES = re.compile(r"totalVotes:\s*(\d+)")


def mesurer_vrai_debat(chemin: Path) -> list[tuple[set[str], int]]:
    """(sous-thèmes, votes) de chaque proposition du Vrai débat."""
    with pymupdf.open(chemin) as doc:
        tout = "\n".join(p.get_text() for p in doc)
    morceaux = PROPOSITION.split(tout)
    sortie = []
    for k in range(1, len(morceaux)):
        # le titre est la fin du morceau précédent, le corps le début de celui-ci
        titre = morceaux[k - 1].rsplit("\n", 1)[-1]
        corps = morceaux[k].split("score:")[0]
        votes = VOTES.search(morceaux[k])
        sortie.append((sous_themes(titre + " " + corps), int(votes[1]) if votes else 0))
    return sortie


def colonne(resultats: list[set[str]], nom: str) -> str:
    if not resultats:
        return "–"
    n = sum(nom in r for r in resultats)
    return f"{n / len(resultats):.0%} ({n})"


def rapport(contributions, cahiers, vrai_debat) -> str:
    propositions = [r for r, _ in vrai_debat]
    votes = sum(v for _, v in vrai_debat) or 1

    def part_votes(nom):
        if not vrai_debat:
            return "–"
        return f"{sum(v for r, v in vrai_debat if nom in r) / votes:.0%}"

    lignes = [
        "# Place des sous-thèmes",
        "",
        (
            f"Repérage par mots-clés (`classement.themes.sous_themes`) : {len(contributions)} "
            f"contributions délimitées avec du texte dactylographié, "
            f"{len(cahiers)} cahiers du versement, {len(propositions)} "
            "propositions du Vrai débat. Un mot repéré ne dit pas que le sujet "
            "est traité : ce sont des ordres de grandeur, pas un classement."
        ),
        "",
        "| sous-thème | thèmes | contributions | cahiers | Vrai débat | votes VD |",
        "|---|---|---|---|---|---|",
    ]
    ajouts = {nom for nom, _, _ in AJOUTS}
    ordre = sorted(TOUS, key=lambda s: -sum(s[0] in r for r in contributions))
    for nom, codes, _ in ordre:
        etiquette = f"{nom} *" if nom in ajouts else nom
        themes = ", ".join(THEMES[c] for c in codes if c not in "+2") or (
            "complémentaire" if "2" in codes else "–"
        )
        lignes.append(
            f"| {etiquette} | {themes} | {colonne(contributions, nom)} | "
            f"{colonne(cahiers, nom)} | {colonne(propositions, nom)} | "
            f"{part_votes(nom)} |"
        )
    lignes += [
        "",
        "\\* absent de la liste de l'association.",
        "",
        "## Par thème",
        "",
        "Un thème est touché si un de ses sous-thèmes l'est.",
        "",
        "| thème | contributions | cahiers | Vrai débat |",
        "|---|---|---|---|",
    ]
    for code, titre in THEMES.items():
        noms = {nom for nom, codes, _ in TOUS if code in codes}
        a_theme = [{"x"} if r & noms else set() for r in contributions]
        b_theme = [{"x"} if r & noms else set() for r in cahiers]
        c_theme = [{"x"} if r & noms else set() for r in propositions]
        lignes.append(
            f"| {titre} | {colonne(a_theme, 'x')} | {colonne(b_theme, 'x')} | "
            f"{colonne(c_theme, 'x')} |"
        )
    hors_liste = [set() if r - ajouts else {"x"} for r in contributions]
    aucun = [set() if r else {"x"} for r in contributions]
    lignes += [
        "",
        (
            "Contributions qu'aucun sous-thème de la liste de l'association ne "
            f"touche : {colonne(hors_liste, 'x')} ; sans aucun sous-thème, même "
            f"avec les ajouts : {colonne(aucun, 'x')}."
        ),
        "",
    ]
    return "\n".join(lignes)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--delimitation", type=Path, default=Path("data/delimitation/contributions.csv")
    )
    parser.add_argument("--versement", type=Path, default=Path("data/versement"))
    parser.add_argument(
        "--typage", type=Path, nargs="+", default=[Path("data/typage/departements")]
    )
    parser.add_argument(
        "--ouvertures", type=Path, default=Path("data/ouvertures/ouvertures.csv")
    )
    parser.add_argument(
        "--vrai-debat",
        type=Path,
        default=Path("../data/vrai-debat/1059propositionsvraidébat.pdf"),
    )
    parser.add_argument("--sans-corpus", action="store_true")
    parser.add_argument("--sortie", type=Path, default=Path("data/themes"))
    args = parser.parse_args()

    chemins = {p.name: p for p in args.versement.rglob("CC_*.pdf")}
    lues = pages_lues(args.typage, set(chemins), lire_ouvertures(args.ouvertures))
    contributions, orphelins = mesurer_contributions(args.delimitation, chemins, lues)
    cahiers = [] if args.sans_corpus else mesurer_corpus(chemins, lues)
    vrai_debat = mesurer_vrai_debat(args.vrai_debat) if args.vrai_debat.exists() else []

    texte_rapport = rapport(contributions, cahiers, vrai_debat)
    frequents = sorted(
        ((mot, len(c)) for mot, c in orphelins.items() if len(c) >= CAHIERS_MIN),
        key=lambda x: -x[1],
    )[:80]
    texte_rapport += (
        "\n## Vocabulaire des contributions sans sous-thème\n\n"
        f"Mots présents dans au moins {CAHIERS_MIN} cahiers, avec leur nombre "
        "de cahiers : ce que la liste ne couvre peut-être pas.\n\n"
        + ", ".join(f"{mot} ({n})" for mot, n in frequents)
        + "\n"
    )
    args.sortie.mkdir(parents=True, exist_ok=True)
    (args.sortie / "frequences.md").write_text(texte_rapport, encoding="utf-8")
    print(texte_rapport)
    print(f"Écrit dans {args.sortie / 'frequences.md'}")


if __name__ == "__main__":
    main()
