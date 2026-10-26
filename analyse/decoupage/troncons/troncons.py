"""Tronçons de cahiers à délimiter, pour tester le découpage (issue #5).

Les 98 cahiers délimités pour le tirage de l'association servent à écrire
les règles et à entraîner le modèle ; mesurer sur eux flatte les chiffres.
La référence de test prend un tronçon de cahier dans chaque département du
versement qu'ils ne couvrent pas : des numérisations et des usages locaux
que le découpage n'a jamais vus.

Dans chaque département, on tire une page dactylographiée au hasard (un
cahier pèse donc ses pages dactylographiées) ; le tronçon est fait des
`longueur` pages écrites qui partent de celle-là, reculé si le cahier finit
avant. Les pages écrites ne sont ni vierges, ni de service, ni d'ouverture.
Un tronçon représente les pages dactylographiées de son département : c'est
le poids de ses mesures.

Une page du tronçon compte dans les mesures dès qu'elle est vue (tâche
« decoupage ») : toutes ses notes sont posées. Chaque page mesurée d'un
tronçon vaut alors `dactylographiees_departement` / pages mesurées du
tronçon.
"""

import csv
import random
from pathlib import Path

DACTYLOGRAPHIEE = "dactylographiée"


def tirer(
    cahiers: dict[str, dict],
    exclus: set[str],
    rng: random.Random,
    longueur: int = 10,
) -> list[dict]:
    """Un tronçon par département hors `exclus`.

    `cahiers` : par fichier, son département de versement et ses pages
    écrites, [(numéro, type)] dans l'ordre. Le département ne compte pas
    s'il n'a aucune page dactylographiée.
    """
    par_departement: dict[str, list[tuple[str, int]]] = {}
    for fichier in sorted(cahiers):
        cahier = cahiers[fichier]
        if cahier["departement"] in exclus:
            continue
        candidates = par_departement.setdefault(cahier["departement"], [])
        candidates += [
            (fichier, i)
            for i, (_, type_page) in enumerate(cahier["pages"])
            if type_page == DACTYLOGRAPHIEE
        ]
    troncons = []
    for departement, candidates in sorted(par_departement.items()):
        if not candidates:
            continue
        fichier, i = rng.choice(candidates)
        pages = cahiers[fichier]["pages"]
        debut = max(0, min(i, len(pages) - longueur))
        numeros = [n for n, _ in pages[debut : debut + longueur]]
        troncons.append(
            {
                "departement": departement,
                "fichier": fichier,
                "premiere": numeros[0],
                "derniere": numeros[-1],
                "pages": len(numeros),
                "dactylographiees": sum(
                    t == DACTYLOGRAPHIEE for _, t in pages[debut : debut + longueur]
                ),
                "dactylographiees_departement": len(candidates),
            }
        )
    return troncons


def lire(chemin: Path) -> list[dict]:
    """Les tronçons écrits par `python -m decoupage.troncons`, ou aucun."""
    if not chemin.exists():
        return []
    with chemin.open(encoding="utf-8", newline="") as f:
        return [
            {
                **t,
                "premiere": int(t["premiere"]),
                "derniere": int(t["derniere"]),
                "dactylographiees_departement": int(t["dactylographiees_departement"]),
            }
            for t in csv.DictReader(f)
        ]


def pages_mesurees(
    troncons: list[dict], pages: dict[str, list[int]], vues: set[tuple[str, int]]
) -> list[set[tuple[str, int]]]:
    """Par tronçon, ses pages (parmi `pages`, par cahier) qui sont vues."""
    return [
        {
            (t["fichier"], n)
            for n in pages.get(t["fichier"], [])
            if t["premiere"] <= n <= t["derniere"] and (t["fichier"], n) in vues
        }
        for t in troncons
    ]


def ponderer(comptes: list[tuple[float, int, int, int]]) -> tuple[float, float]:
    """Précision et rappel pondérés, de (poids, justes, trouvés, référence)
    par tronçon."""
    justes = sum(w * j for w, j, _, _ in comptes)
    trouves = sum(w * t for w, _, t, _ in comptes)
    reference = sum(w * r for w, _, _, r in comptes)
    return (
        justes / trouves if trouves else 0.0,
        justes / reference if reference else 0.0,
    )
