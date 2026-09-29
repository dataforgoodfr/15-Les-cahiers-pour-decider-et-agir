"""Ce que le corpus représente déjà, comparé à l'ensemble des communes de 2019 (issue #20).

    uv run python -m communes.representativite [data/communes/communes.csv] [--sortie data/representativite]

Lit la table produite par `python -m communes`. L'univers est l'ensemble des
communes de plein exercice au 1er janvier 2019. Une commune déléguée, associée,
un arrondissement ou un code supprimé du corpus compte pour sa commune parente.

Pour chaque axe (taille, densité, région), et par groupe : part des communes
et des habitants couverts, et représentation, c'est-à-dire la part du groupe
dans le corpus divisée par sa part en France (1 = ni plus ni moins qu'en France).
Si la table a les colonnes `pages` et `pages_texte_natif`, on y ajoute la part
de pages à texte natif et les communes qui n'en ont aucune.
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from communes.rattachement import COMMUNE, DENSITE, Referentiel, rattacher

TRANCHES = [
    (0, "moins de 200"),
    (200, "200 à 499"),
    (500, "500 à 1 999"),
    (2_000, "2 000 à 4 999"),
    (5_000, "5 000 à 19 999"),
    (20_000, "20 000 à 99 999"),
    (100_000, "100 000 et plus"),
]


def tranche(population: int | None) -> str:
    if population is None:
        return "population inconnue"
    return [libelle for seuil, libelle in TRANCHES if population >= seuil][-1]


def univers(ref: Referentiel) -> dict[str, dict]:
    """Les communes de plein exercice de 2019 et leurs groupes sur chaque axe."""
    communes = {}
    for code, ligne in ref.cog.items():
        if ligne["typecom"] != COMMUNE:
            continue
        variables = rattacher(code, ref)
        population = ref.populations.get(code)
        communes[code] = {
            "population": population or 0,
            "taille": tranche(population),
            "densite": DENSITE.get(int(variables["densite"] or 0), "densité inconnue"),
            "region": variables["nom_region"] or ligne["reg"],
        }
    return communes


def corpus(chemin: Path) -> tuple[dict[str, dict], bool]:
    """Communes de plein exercice couvertes, avec leurs pages cumulées."""
    couvertes: dict[str, dict] = defaultdict(lambda: {"pages": 0, "texte_natif": 0})
    with chemin.open(encoding="utf-8") as f:
        lignes = list(csv.DictReader(f))
    avec_pages = bool(lignes) and "pages_texte_natif" in lignes[0]
    for ligne in lignes:
        code = ligne["code_insee"]
        if ligne["type_2019"] != COMMUNE:
            code = ligne["population_incluse_dans"]
        c = couvertes[code]
        if avec_pages:
            c["pages"] += int(ligne["pages"])
            c["texte_natif"] += int(ligne["pages_texte_natif"])
    return couvertes, avec_pages


def comparer(communes: dict, couvertes: dict, axe: str, avec_pages: bool) -> list[dict]:
    groupes: dict[str, dict] = defaultdict(lambda: defaultdict(int))
    for code, c in communes.items():
        g = groupes[c[axe]]
        g["communes"] += 1
        g["habitants"] += c["population"]
        if code in couvertes:
            g["communes_corpus"] += 1
            g["habitants_corpus"] += c["population"]
            g["pages"] += couvertes[code]["pages"]
            g["pages_texte_natif"] += couvertes[code]["texte_natif"]
            g["sans_texte_natif"] += couvertes[code]["texte_natif"] == 0
    total = sum(g["communes"] for g in groupes.values())
    total_corpus = sum(g["communes_corpus"] for g in groupes.values())
    lignes = []
    for nom, g in groupes.items():
        part_france = g["communes"] / total
        part_corpus = g["communes_corpus"] / total_corpus
        ligne = {
            axe: nom,
            "communes": g["communes"],
            "communes_corpus": g["communes_corpus"],
            "part_communes_couvertes": g["communes_corpus"] / g["communes"],
            "part_habitants_couverts": g["habitants_corpus"] / g["habitants"]
            if g["habitants"]
            else None,
            "part_en_france": part_france,
            "part_dans_corpus": part_corpus,
            "representation": part_corpus / part_france,
        }
        if avec_pages:
            ligne |= {
                "pages": g["pages"],
                "part_texte_natif": g["pages_texte_natif"] / g["pages"]
                if g["pages"]
                else None,
                "communes_sans_texte_natif": g["sans_texte_natif"],
            }
        lignes.append(ligne)
    ordre = [libelle for _, libelle in TRANCHES] + list(DENSITE.values())
    return sorted(
        lignes,
        key=lambda lg: (
            ordre.index(lg[axe]) if lg[axe] in ordre else len(ordre),
            lg[axe],
        ),
    )


def _format(valeur) -> str:
    if valeur is None:
        return "—"
    if isinstance(valeur, str):
        return valeur
    if isinstance(valeur, float):
        return f"{valeur:.0%}"
    return f"{valeur:,}".replace(",", " ")


def tableau_markdown(lignes: list[dict], axe: str) -> str:
    colonnes = list(lignes[0])
    sortie = ["| " + " | ".join(colonnes) + " |", "|" + "---|" * len(colonnes)]
    for ligne in lignes:
        cellules = [
            f"{ligne[c]:.2f}" if c == "representation" else _format(ligne[c])
            for c in colonnes
        ]
        sortie.append("| " + " | ".join(cellules) + " |")
    return "\n".join(sortie)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "communes", type=Path, nargs="?", default=Path("data/communes/communes.csv")
    )
    parser.add_argument("--sortie", type=Path, default=Path("data/representativite"))
    parser.add_argument("--cache", type=Path, default=Path("data/sources"))
    args = parser.parse_args()

    ref = Referentiel.telecharger(args.cache)
    communes = univers(ref)
    couvertes, avec_pages = corpus(args.communes)
    hors_univers = set(couvertes) - set(communes)
    args.sortie.mkdir(parents=True, exist_ok=True)

    habitants = sum(c["population"] for c in communes.values())
    habitants_corpus = sum(
        communes[c]["population"] for c in couvertes if c in communes
    )
    rapport = [
        (
            f"Communes de 2019 couvertes : {len(set(couvertes) & set(communes))} "
            f"sur {len(communes)} ; habitants : {habitants_corpus / habitants:.0%}."
        ),
    ]
    if hors_univers:
        rapport.append(f"Hors univers (non comptées) : {sorted(hors_univers)}")
    for axe, titre in (
        ("taille", "Taille"),
        ("densite", "Densité"),
        ("region", "Région"),
    ):
        lignes = comparer(communes, couvertes, axe, avec_pages)
        with (args.sortie / f"{axe}.csv").open("w", encoding="utf-8", newline="") as f:
            ecrivain = csv.DictWriter(f, list(lignes[0]))
            ecrivain.writeheader()
            ecrivain.writerows(lignes)
        rapport += ["", f"## {titre}", "", tableau_markdown(lignes, axe)]
    texte = "\n".join(rapport) + "\n"
    (args.sortie / "rapport.md").write_text(texte, encoding="utf-8")
    print(texte)


if __name__ == "__main__":
    main()
