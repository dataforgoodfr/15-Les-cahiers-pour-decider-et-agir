"""Tirage d'une centaine de contributions pour l'association (issue #21).

    uv run python -m tirage [--typage data/typage/departements]
        [--communes data/communes/communes.csv] [--cache data/sources]
        [--nombre 100] [--graine 2026] [--avec-manuscrits]
        [--sortie data/tirage]

Méthode dans `tirage.tirage`. Écrit dans la sortie :

- `contributions.csv` : une ligne par contribution tirée, son cahier et la
  position où la prendre, avec la commune, sa taille, sa région et les pages
  du cahier par type ;
- `rapport.md` : contributions tirées par tranche de taille et par région,
  contre la
    part de la population française ; profil des communes (CSP, âges, revenu)
  du tirage et du corpus, contre la France (`tirage.profil`).

Sans `--avec-manuscrits`, seules les pages dactylographiées comptent : un
cahier entièrement manuscrit ne peut pas sortir.

Des codes, des noms de communes et des comptes, jamais de texte.
"""

import argparse
import csv
import random
from collections import Counter, defaultdict
from pathlib import Path

from communes import sources
from communes.rattachement import COMMUNE, Referentiel
from communes.representativite import TRANCHES, univers
from panel.panel import cahiers as compter_pages
from panel.panel import lire_typage
from tirage import profil
from tirage.tirage import arrondir, caler, choisir_contributions, tirer_communes


def parente(chemin: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Code du corpus vers sa commune de plein exercice, et vers son nom."""
    parentes, noms = {}, {}
    with chemin.open(encoding="utf-8", newline="") as f:
        for ligne in csv.DictReader(f):
            code = ligne["code_insee"]
            noms[code] = ligne["nom_2019"] or ligne["commune"]
            if ligne["type_2019"] == COMMUNE:
                parentes[code] = code
            elif ligne["population_incluse_dans"]:
                parentes[code] = ligne["population_incluse_dans"]
    return parentes, noms


def tableau(titre: str, tires: Counter, parts: dict[str, float], ordre) -> list[str]:
    total = sum(parts.values())
    lignes = [
        f"## {titre}",
        "",
        "| | contributions tirées | attendues selon la population |",
        "|---|---|---|",
    ]
    n = sum(tires.values())
    for groupe in ordre:
        attendus = n * parts.get(groupe, 0) / total
        lignes.append(f"| {groupe} | {tires[groupe]} | {attendus:.1f} |")
    return lignes + [""]


def ligne_pct(groupe: str, *colonnes: dict[str, float]) -> str:
    return (
        f"| {groupe} | "
        + " | ".join(f"{c.get(groupe, 0):.0%}" for c in colonnes)
        + " |"
    )


def profils(cache: Path, france: dict, corpus: list[str], tires: list[str]):
    """Section du rapport : CSP, âges et revenu des communes, contre la France.

    `corpus` : la commune de plein exercice de chaque cahier ; `tires`, de
    chaque contribution tirée.
    """
    structure = sources.colonnes_csv_zip(
        sources.telecharger(sources.STRUCTURE_POPULATION, cache),
        "base-cc-evol-struct-pop-2017.CSV",
        profil.COLONNES,
    )
    lignes = [
        "## Profil des communes",
        "",
        (
            "Chaque cahier ou contribution porte le profil de sa commune "
            "(recensement et Filosofi 2017) : ce n'est pas celui des contributeurs."
        ),
        "",
    ]
    for titre, groupes in (("CSP (15 ans et plus)", profil.CSP), ("Âges", profil.AGES)):
        colonnes = [
            profil.france(structure, france, groupes),
            profil.moyenne(structure, corpus, groupes),
            profil.moyenne(structure, tires, groupes),
        ]
        lignes += [
            f"### {titre}",
            "",
            "| | France | corpus | tirage |",
            "|---|---|---|---|",
        ]
        lignes += [ligne_pct(g, *colonnes) for g in dict.fromkeys(groupes.values())]
        lignes.append("")

    medianes = sources.revenus_medians(sources.telecharger(sources.REVENUS, cache))
    populations = {code: c["population"] for code, c in france.items()}
    seuils = profil.seuils_quarts(medianes, populations)
    codes = list(populations)
    colonnes = [
        profil.repartition(
            [profil.quart(medianes.get(c), seuils) for c in codes],
            [populations[c] for c in codes],
        ),
        profil.repartition([profil.quart(medianes.get(c), seuils) for c in corpus]),
        profil.repartition([profil.quart(medianes.get(c), seuils) for c in tires]),
    ]
    lignes += [
        "### Revenu médian de la commune",
        "",
        "Quarts de la population française, seuils : "
        + ", ".join(f"{s} €" for s in seuils)
        + ". Inconnu : secret statistique ou commune nouvelle de 2019.",
        "",
        "| | France | corpus | tirage |",
        "|---|---|---|---|",
    ]
    lignes += [ligne_pct(g, *colonnes) for g in [*profil.QUARTS, profil.INCONNU]]
    return lignes + [""]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--typage", type=Path, nargs="+", default=[Path("data/typage/departements")]
    )
    parser.add_argument(
        "--communes", type=Path, default=Path("data/communes/communes.csv")
    )
    parser.add_argument("--cache", type=Path, default=Path("data/sources"))
    parser.add_argument("--nombre", type=int, default=100)
    parser.add_argument("--graine", type=int, default=2026)
    parser.add_argument(
        "--avec-manuscrits",
        action="store_true",
        help="compter aussi les pages mixtes et manuscrites",
    )
    parser.add_argument("--sortie", type=Path, default=Path("data/tirage"))
    args = parser.parse_args()

    france = univers(Referentiel.telecharger(args.cache))
    parentes, noms = parente(args.communes)

    # Pages retenues de chaque cahier, regroupés par commune de plein exercice
    par_cahier, par_commune = {}, defaultdict(dict)
    for cahier in compter_pages(lire_typage(args.typage), None, ()):
        retenues = cahier["dactylographiees"]
        if args.avec_manuscrits:
            retenues += cahier["mixtes"] + cahier["manuscrites"]
        code = parentes.get(cahier["code_insee"])
        if not retenues or code not in france:
            continue
        par_cahier[cahier["fichier"]] = cahier | {"commune_parente": code}
        par_commune[code][cahier["fichier"]] = retenues

    habitants_par_taille = defaultdict(int)
    for c in france.values():
        habitants_par_taille[c["taille"]] += c["population"]
    habitants_par_taille.pop("population inconnue", None)
    habitants_par_region = defaultdict(int)
    for c in france.values():
        habitants_par_region[c["region"]] += c["population"]

    corpus = {
        code: france[code] for code in sorted(par_commune) if france[code]["population"]
    }
    poids = caler(
        corpus, {"taille": habitants_par_taille, "region": habitants_par_region}
    )
    cases = defaultdict(float)
    for code, c in corpus.items():
        cases[c["taille"], c["region"]] += poids[code]
    rng = random.Random(args.graine)
    tires = []
    for (taille, region), n in sorted(arrondir(cases, args.nombre).items()):
        communes = [
            (code, poids[code], ())
            for code, c in corpus.items()
            if (c["taille"], c["region"]) == (taille, region)
        ]
        tires += choisir_contributions(
            tirer_communes(communes, n, rng), par_commune, rng
        )

    lignes = []
    for fichier, position in sorted(tires):
        cahier = par_cahier[fichier]
        commune = france[cahier["commune_parente"]]
        lignes.append(
            {
                "fichier": fichier,
                "position": position,
                "code_insee": cahier["code_insee"],
                "commune": noms.get(cahier["code_insee"], ""),
                "departement": cahier["departement"],
                "region": commune["region"],
                "taille": commune["taille"],
                "population": commune["population"],
                "pages": cahier["pages"],
                "dactylographiees": cahier["dactylographiees"],
                "mixtes": cahier["mixtes"],
                "manuscrites": cahier["manuscrites"],
            }
        )

    args.sortie.mkdir(parents=True, exist_ok=True)
    with (args.sortie / "contributions.csv").open(
        "w", encoding="utf-8", newline=""
    ) as f:
        ecrivain = csv.DictWriter(f, list(lignes[0]))
        ecrivain.writeheader()
        ecrivain.writerows(lignes)

    rapport = [
        f"# Tirage de {len(lignes)} contributions (graine {args.graine})",
        "",
        (
            f"Univers : {len(par_cahier)} cahiers citoyens avec des pages "
            + ("écrites" if args.avec_manuscrits else "dactylographiées")
            + f", dans {len(par_commune)} communes."
        ),
        "",
        (
            "Dans chaque cahier tiré, compter les n contributions retenues et "
            "prendre la ⌈position × n⌉-ième."
        ),
        "",
    ]
    rapport += tableau(
        "Taille de commune",
        Counter(lg["taille"] for lg in lignes),
        habitants_par_taille,
        [libelle for _, libelle in TRANCHES],
    )
    rapport += tableau(
        "Région",
        Counter(lg["region"] for lg in lignes),
        habitants_par_region,
        sorted(habitants_par_region),
    )
    rapport += profils(
        args.cache,
        france,
        [c["commune_parente"] for c in par_cahier.values()],
        [par_cahier[f]["commune_parente"] for f, _ in tires],
    )
    texte = "\n".join(rapport)
    (args.sortie / "rapport.md").write_text(texte, encoding="utf-8")
    print(texte)
    print(f"Écrit dans {args.sortie}")


if __name__ == "__main__":
    main()
