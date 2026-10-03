"""Tirage d'une centaine de cahiers pour l'association (issue #21).

    uv run python -m tirage [--typage data/typage/departements]
        [--communes data/communes/communes.csv] [--cache data/sources]
        [--nombre 100] [--graine 2026] [--sortie data/tirage]

Méthode dans `tirage.tirage`. Écrit dans la sortie :

- `cahiers.csv` : les cahiers tirés, avec leur commune, sa taille et sa
  région, et leurs pages par type ;
- `rapport.md` : cahiers tirés par tranche de taille et par région, contre la
  part de la population française.

Des codes, des noms de communes et des comptes, jamais de texte.
"""

import argparse
import csv
import random
from collections import Counter, defaultdict
from pathlib import Path

from communes.rattachement import COMMUNE, Referentiel
from communes.representativite import TRANCHES, univers
from panel.panel import cahiers as compter_pages
from panel.panel import lire_typage
from tirage.tirage import allouer, choisir_cahiers, tirer_communes


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
        "| | cahiers tirés | attendus selon la population |",
        "|---|---|---|",
    ]
    n = sum(tires.values())
    for groupe in ordre:
        attendus = n * parts.get(groupe, 0) / total
        lignes.append(f"| {groupe} | {tires[groupe]} | {attendus:.1f} |")
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
    parser.add_argument("--sortie", type=Path, default=Path("data/tirage"))
    args = parser.parse_args()

    france = univers(Referentiel.telecharger(args.cache))
    parentes, noms = parente(args.communes)

    # Cahiers écrits, regroupés par commune de plein exercice
    par_cahier, par_commune = {}, defaultdict(list)
    for cahier in compter_pages(lire_typage(args.typage), None, ()):
        ecrites = cahier["dactylographiees"] + cahier["mixtes"] + cahier["manuscrites"]
        code = parentes.get(cahier["code_insee"])
        if not ecrites or code not in france:
            continue
        par_cahier[cahier["fichier"]] = cahier | {"commune_parente": code}
        par_commune[code].append(cahier["fichier"])

    habitants_par_taille = defaultdict(int)
    for c in france.values():
        habitants_par_taille[c["taille"]] += c["population"]
    habitants_par_taille.pop("population inconnue", None)
    allocation = allouer(habitants_par_taille, args.nombre)

    rng = random.Random(args.graine)
    tires = []
    for taille, n in allocation.items():
        communes = [
            (code, france[code]["population"], france[code]["region"])
            for code in sorted(par_commune)
            if france[code]["taille"] == taille and france[code]["population"]
        ]
        tires += choisir_cahiers(tirer_communes(communes, n, rng), par_commune, rng)

    lignes = []
    for fichier in sorted(tires):
        cahier = par_cahier[fichier]
        commune = france[cahier["commune_parente"]]
        lignes.append(
            {
                "fichier": fichier,
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
    with (args.sortie / "cahiers.csv").open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, list(lignes[0]))
        ecrivain.writeheader()
        ecrivain.writerows(lignes)

    habitants_par_region = defaultdict(int)
    for c in france.values():
        habitants_par_region[c["region"]] += c["population"]
    rapport = [
        f"# Tirage de {len(lignes)} cahiers (graine {args.graine})",
        "",
        (
            f"Univers : {len(par_cahier)} cahiers citoyens écrits, "
            f"dans {len(par_commune)} communes."
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
    texte = "\n".join(rapport)
    (args.sortie / "rapport.md").write_text(texte, encoding="utf-8")
    print(texte)
    print(f"Écrit dans {args.sortie}")


if __name__ == "__main__":
    main()
