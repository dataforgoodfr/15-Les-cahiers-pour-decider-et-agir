"""Tirage d'une centaine de contributions pour l'association (issue #21).

Premier tirage à montrer à l'association : ses réactions donneront les
critères de la sélection « gold » (#29). Les critères sont donc explicites et
le tirage se refait à l'identique avec la même graine.

L'univers est la France entière : tous les cahiers citoyens rattachés à une
commune et dont au moins une page est retenue (dactylographiée, et en option
mixte ou manuscrite). Le tirage représente les habitants, pas les communes :

1. chaque commune du corpus pèse sa population de 2017, recalée pour que
   les communes du corpus pèsent, par tranche de taille et par région, autant
   que les habitants de la France (calage sur marges) ;
2. chaque case tranche × région reçoit sa part du tirage, arrondie au-dessus
   ou au-dessous, de sorte que chaque tranche et chaque région reçoivent leur
   part à une unité près (arrondi contrôlé) ;
3. dans une case, les communes sont tirées avec une probabilité
   proportionnelle à leur poids (tirage systématique) ;
4. à chaque tirage d'une commune, une contribution : un cahier de la commune,
   avec une probabilité proportionnelle à ses pages retenues (une estimation
   de son nombre de contributions), puis une position au hasard entre 0 et 1.
   Une grande ville tirée plusieurs fois donne plusieurs contributions.

Les cahiers ne sont pas encore découpés en contributions (#5) : la personne
qui ouvre le cahier compte ses n contributions retenues et prend la
⌈position × n⌉-ième.

Une commune déléguée ou un arrondissement compte pour sa commune parente.
Mayotte, sans population légale en 2017, ne peut pas sortir.
"""

import random
from collections import defaultdict, deque


def caler(
    communes: dict[str, dict], cibles: dict[str, dict[str, float]], tours: int = 50
) -> dict[str, float]:
    """Poids des communes, partant de leur population, recalés pour que leur
    somme par modalité de chaque variable (taille, région) suive les cibles.

    Une modalité absente des communes est ignorée : les autres se partagent
    sa part.
    """
    poids = {code: float(c["population"]) for code, c in communes.items()}
    for _ in range(tours):
        for variable, cible in cibles.items():
            sommes = defaultdict(float)
            for code, c in communes.items():
                sommes[c[variable]] += poids[code]
            total = sum(v for m, v in cible.items() if sommes[m])
            for code, c in communes.items():
                m = c[variable]
                poids[code] *= cible.get(m, 0) / total / sommes[m]
    return poids


def allouer(parts: dict, n: int) -> dict:
    """Répartit n entre les groupes selon leurs parts, aux plus forts restes."""
    total = sum(parts.values())
    exactes = {g: n * p / total for g, p in parts.items()}
    allocation = {g: int(e) for g, e in exactes.items()}
    restes = sorted(exactes, key=lambda g: exactes[g] - allocation[g], reverse=True)
    for g in restes[: n - sum(allocation.values())]:
        allocation[g] += 1
    return allocation


def arrondir(cases: dict[tuple, float], n: int) -> dict[tuple, int]:
    """Répartit n entre les cases (ligne, colonne) selon leurs parts : chaque
    case reçoit sa part exacte arrondie au-dessus ou au-dessous, chaque ligne
    et chaque colonne sa part aux plus forts restes.

    Les cases à arrondir au-dessus sont un flot maximal : de chaque ligne vers
    ses colonnes, une unité par case à part fractionnaire.
    """
    total = sum(cases.values())
    exactes = {c: n * p / total for c, p in cases.items()}
    allocation = {c: int(e) for c, e in exactes.items()}
    lignes, colonnes = defaultdict(float), defaultdict(float)
    for (i, j), p in cases.items():
        lignes[i] += p
        colonnes[j] += p

    capacite = defaultdict(int)
    for i, k in allouer(lignes, n).items():
        capacite["source", ("l", i)] = k
    for j, k in allouer(colonnes, n).items():
        capacite[("c", j), "puits"] = k
    for (i, j), k in allocation.items():
        capacite["source", ("l", i)] -= k
        capacite[("c", j), "puits"] -= k
        if exactes[(i, j)] > k:
            capacite[("l", i), ("c", j)] = 1
    besoin = sum(capacite[a, b] for a, b in list(capacite) if a == "source")
    if flot_maximal(capacite) < besoin:
        raise ValueError("arrondi contrôlé impossible")
    for (i, j), k in allocation.items():
        if exactes[(i, j)] > k and capacite[("l", i), ("c", j)] == 0:
            allocation[(i, j)] += 1
    return allocation


def flot_maximal(capacite: dict) -> int:
    """Flot de "source" à "puits" (Edmonds-Karp). Laisse dans `capacite` les
    capacités résiduelles."""
    voisins = defaultdict(set)
    for a, b in list(capacite):
        voisins[a].add(b)
        voisins[b].add(a)
    flot = 0
    while True:
        precedent, file = {"source": None}, deque(["source"])
        while file and "puits" not in precedent:
            a = file.popleft()
            for b in sorted(voisins[a], key=str):
                if b not in precedent and capacite[a, b] > 0:
                    precedent[b] = a
                    file.append(b)
        if "puits" not in precedent:
            return flot
        b = "puits"
        while precedent[b] is not None:
            a = precedent[b]
            capacite[a, b] -= 1
            capacite[b, a] += 1
            b = a
        flot += 1


def tirer_communes(
    communes: list[tuple[str, float, tuple]], n: int, rng: random.Random
) -> list[str]:
    """Tirage systématique de n communes (code, poids, ordre), proportionnel
    au poids. Une commune plus lourde que le pas sort plusieurs fois."""
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


def choisir_contributions(
    tirees: list[str], cahiers: dict[str, dict[str, int]], rng: random.Random
) -> list[tuple[str, float]]:
    """Une contribution (cahier, position) par tirage de commune.

    `cahiers` : pour chaque commune, les pages retenues de chacun de ses cahiers.
    """
    choisies = []
    for code in tirees:
        fichiers = sorted(cahiers[code])
        fichier = rng.choices(fichiers, [cahiers[code][f] for f in fichiers])[0]
        choisies.append((fichier, round(1 - rng.random(), 3) or 0.001))
    return choisies
