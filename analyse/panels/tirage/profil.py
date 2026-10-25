"""Profil des communes d'un ensemble de cahiers, comparé à la France (issue #21).

On ne connaît ni l'âge, ni la CSP, ni le revenu de ceux qui ont écrit : on
compare le contexte où ils vivent. Pour un ensemble de cahiers, chaque cahier
porte le profil de sa commune (recensement 2017, Filosofi 2017), et on fait
la moyenne sur les cahiers. Dans le tirage, les communes sortent
proportionnellement à leur population : cette moyenne estime la part de la
France, et l'écart entre les deux mesure ce que le tirage déforme.
"""

from collections import defaultdict

CSP = {
    "C17_POP15P_CS1": "agriculteurs",
    "C17_POP15P_CS2": "artisans, commerçants, chefs d'entreprise",
    "C17_POP15P_CS3": "cadres",
    "C17_POP15P_CS4": "professions intermédiaires",
    "C17_POP15P_CS5": "employés",
    "C17_POP15P_CS6": "ouvriers",
    "C17_POP15P_CS7": "retraités",
    "C17_POP15P_CS8": "autres sans activité",
}
AGES = {
    "P17_POP0014": "0 à 14 ans",
    "P17_POP1529": "15 à 29 ans",
    "P17_POP3044": "30 à 44 ans",
    "P17_POP4559": "45 à 59 ans",
    "P17_POP6074": "60 à 74 ans",
    "P17_POP7589": "75 ans et plus",
    "P17_POP90P": "75 ans et plus",
}
COLONNES = ["C17_POP15P", *CSP, "P17_POP", *AGES]
QUARTS = [
    "revenu médian du premier quart",
    "deuxième quart",
    "troisième quart",
    "dernier quart",
]
INCONNU = "revenu inconnu"


def comptes(ligne: dict[str, str], groupes: dict[str, str]) -> dict[str, float]:
    total = defaultdict(float)
    for colonne, groupe in groupes.items():
        total[groupe] += float(ligne[colonne] or 0)
    return total


def parts(ligne: dict[str, str], groupes: dict[str, str]) -> dict[str, float]:
    c = comptes(ligne, groupes)
    somme = sum(c.values())
    return {g: v / somme for g, v in c.items()} if somme else {}


def france(structure: dict[str, dict], codes, groupes) -> dict[str, float]:
    """Parts de la France : comptes sommés sur les communes de plein exercice."""
    total = defaultdict(float)
    for code in codes:
        if code in structure:
            for g, v in comptes(structure[code], groupes).items():
                total[g] += v
    somme = sum(total.values())
    return {g: v / somme for g, v in total.items()}


def moyenne(structure: dict[str, dict], codes: list[str], groupes) -> dict[str, float]:
    """Moyenne des parts des communes, un cahier comptant pour un."""
    total, n = defaultdict(float), 0
    for code in codes:
        p = parts(structure.get(code, {}), groupes) if code in structure else {}
        if p:
            n += 1
            for g, v in p.items():
                total[g] += v
    return {g: v / n for g, v in total.items()} if n else {}


def seuils_quarts(medianes: dict[str, int], populations: dict[str, int]) -> list[int]:
    """Revenus médians qui partagent les habitants de la France en quatre."""
    connues = sorted(
        (medianes[c], p) for c, p in populations.items() if c in medianes and p
    )
    total = sum(p for _, p in connues)
    seuils, cumul, cible = [], 0, 1
    for mediane, p in connues:
        cumul += p
        while cible < 4 and cumul >= cible * total / 4:
            seuils.append(mediane)
            cible += 1
    return seuils


def quart(mediane: int | None, seuils: list[int]) -> str:
    if mediane is None:
        return INCONNU
    return QUARTS[sum(mediane > s for s in seuils)]


def repartition(etiquettes: list[str], poids: list[float] | None = None) -> dict:
    """Part de chaque étiquette, pondérée (habitants) ou non (cahiers)."""
    poids = poids or [1.0] * len(etiquettes)
    somme = sum(poids)
    total = defaultdict(float)
    for e, w in zip(etiquettes, poids):
        total[e] += w / somme
    return dict(total)
