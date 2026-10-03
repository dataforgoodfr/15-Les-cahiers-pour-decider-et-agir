"""Tirage d'une centaine de cahiers pour l'association (issue #21).

Premier tirage à montrer à l'association : ses réactions donneront les
critères de la sélection « gold » (#29). Les critères sont donc explicites et
le tirage se refait à l'identique avec la même graine.

L'univers est la France entière : tous les cahiers citoyens rattachés à une
commune et dont au moins une page est écrite. Le tirage représente les
habitants, pas les communes :

1. chaque tranche de taille de commune reçoit des cahiers selon sa part de la
   population française de 2017 (plus forts restes) ;
2. dans une tranche, les communes du corpus sont tirées avec une probabilité
   proportionnelle à leur population (tirage systématique). Triées par région,
   elles se répartissent entre régions comme leurs habitants ;
3. dans chaque commune tirée, un cahier au hasard, ou plusieurs si la commune
   est tirée plusieurs fois (une grande ville).

Une commune déléguée ou un arrondissement compte pour sa commune parente.
Mayotte, sans population légale en 2017, ne peut pas sortir.
"""

import random
from collections import defaultdict


def allouer(parts: dict[str, float], n: int) -> dict[str, int]:
    """Répartit n entre les groupes selon leurs parts, aux plus forts restes."""
    total = sum(parts.values())
    exactes = {g: n * p / total for g, p in parts.items()}
    allocation = {g: int(e) for g, e in exactes.items()}
    restes = sorted(exactes, key=lambda g: exactes[g] - allocation[g], reverse=True)
    for g in restes[: n - sum(allocation.values())]:
        allocation[g] += 1
    return allocation


def tirer_communes(
    communes: list[tuple[str, int, str]], n: int, rng: random.Random
) -> list[str]:
    """Tirage systématique de n communes (code, population, région), proportionnel
    à la population. Une commune plus peuplée que le pas sort plusieurs fois."""
    if n <= 0:
        return []
    ordre = sorted(communes, key=lambda c: (c[2], rng.random()))
    total = sum(c[1] for c in ordre)
    pas = total / n
    points = [rng.uniform(0, pas) + k * pas for k in range(n)]
    tirees, cumul, i = [], 0, 0
    for code, population, _ in ordre:
        cumul += population
        while i < n and points[i] < cumul:
            tirees.append(code)
            i += 1
    return tirees


def choisir_cahiers(
    tirees: list[str], cahiers: dict[str, list[str]], rng: random.Random
) -> list[str]:
    """Pour chaque commune, autant de cahiers distincts que de tirages."""
    fois = defaultdict(int)
    for code in tirees:
        fois[code] += 1
    choisis = []
    for code, k in fois.items():
        disponibles = sorted(cahiers[code])
        choisis += rng.sample(disponibles, min(k, len(disponibles)))
    return choisis
