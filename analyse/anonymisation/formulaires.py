"""Les cahiers à formulaire du corpus, et leurs pages (#128).

    uv run python -m anonymisation.formulaires [--versement data/versement]
        [--typage data/typage/departements]
        [--ouvertures data/ouvertures/ouvertures.csv]
        [--sortie data/anonymisation/formulaires] [--processus 8]

Un relecteur qui encadre deux exemplaires d'un formulaire en fait reporter
les zones sur les autres (`detection.modele_appris`) : il faut savoir quels
cahiers en portent. La règle `decoupage.contributions.regles.gabarit` n'en trouvait
que 62 % sur les cahiers jugés à l'œil : elle ne lit que les pages
dactylographiées (un formulaire rempli à la main est typé manuscrit) et
veut une ligne sur un tiers des pages (un formulaire noyé parmi des lettres
lui échappe).

Ici, toutes les pages écrites sont lues, et le seuil est absolu : une page
de formulaire porte au moins PAR_PAGE lignes imprimées (LONGUEUR caractères
au moins) qui reviennent chacune sur EXEMPLAIRES pages du cahier ; il faut
EXEMPLAIRES de ces pages. Les copies d'une lettre type signées à la main
comptent aussi : leurs données sont au même endroit, comme sur un
formulaire.

Écrit `formulaires.csv` dans la sortie (fichier, pages écrites, pages de
formulaire) et affiche les comptes. Des comptes, jamais de texte.
"""

import argparse
import csv
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pymupdf

from corpus.ouvertures.__main__ import lire as lire_ouvertures
from corpus.ouvertures.ouvertures import normaliser
from decoupage.contributions.__main__ import lignes
from panels.panel.panel import lire_typage

LONGUEUR = 10  # caractères au moins d'une ligne imprimée
PAR_PAGE = 3  # lignes imprimées au moins sur une page de formulaire
EXEMPLAIRES = 4  # pages au moins où revient une ligne, et pages de formulaire


def pages_de_formulaire(pages: list[list[str]]) -> set[int]:
    """Les indices des pages de formulaire d'un cahier : vide s'il n'en a pas
    EXEMPLAIRES. `pages` : les lignes de chaque page écrite, normalisées."""
    presences = Counter()
    for ls in pages:
        presences.update({x for x in ls if len(x) >= LONGUEUR})
    repetees = {x for x, n in presences.items() if n >= EXEMPLAIRES}
    riches = {i for i, ls in enumerate(pages) if len(repetees & set(ls)) >= PAR_PAGE}
    return riches if len(riches) >= EXEMPLAIRES else set()


def pages_ecrites(
    typage: list[Path], ouvertures: set[tuple[str, int]]
) -> dict[str, list[int]]:
    """Les pages écrites de chaque cahier : ni vierges, ni de service, ni
    d'ouverture imprimée."""
    pages = defaultdict(list)
    for ligne in lire_typage(typage):
        f, n = ligne["fichier"], int(ligne["page"])
        if (
            ligne["type_page"] != "vierge"
            and ligne["page_de_service"] != "1"
            and (f, n) not in ouvertures
        ):
            pages[f].append(n)
    return {f: sorted(p) for f, p in pages.items()}


def _cahier(tache: tuple[Path, list[int]]) -> tuple[str, int, int]:
    chemin, numeros = tache
    with pymupdf.open(chemin) as doc:
        pages = [[normaliser(t) for t, _ in lignes(doc[n - 1])] for n in numeros]
    return chemin.name, len(numeros), len(pages_de_formulaire(pages))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--versement", type=Path, default=Path("data/versement"))
    parser.add_argument(
        "--typage", type=Path, nargs="+", default=[Path("data/typage/departements")]
    )
    parser.add_argument(
        "--ouvertures", type=Path, default=Path("data/ouvertures/ouvertures.csv")
    )
    parser.add_argument(
        "--sortie", type=Path, default=Path("data/anonymisation/formulaires")
    )
    parser.add_argument("--processus", type=int, default=8)
    args = parser.parse_args()

    ecrites = pages_ecrites(args.typage, lire_ouvertures(args.ouvertures))
    chemins = {p.name: p for p in args.versement.rglob("*.pdf") if p.name in ecrites}
    taches = [(chemins[f], n) for f, n in sorted(ecrites.items()) if f in chemins]
    with ProcessPoolExecutor(args.processus) as executeur:
        resultats = list(executeur.map(_cahier, taches, chunksize=20))

    args.sortie.mkdir(parents=True, exist_ok=True)
    with (args.sortie / "formulaires.csv").open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(["fichier", "pages", "pages_de_formulaire"])
        ecrivain.writerows(resultats)
    avec = [r for r in resultats if r[2]]
    print(f"{len(resultats)} cahiers, {sum(r[1] for r in resultats)} pages écrites")
    print(
        f"{len(avec)} cahiers à formulaire, {sum(r[2] for r in avec)} pages de "
        f"formulaire ; {sum(r[2] >= 10 for r in avec)} en ont 10 ou plus"
    )


if __name__ == "__main__":
    main()
