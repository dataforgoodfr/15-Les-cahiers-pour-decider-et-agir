"""L'ordre des cahiers à délimiter dans la liste « selection ».

Le tirage suit la population par taille de commune et par région, mais
seulement une fois les 100 cahiers délimités. Pris dans l'ordre des fichiers
(par département), un recueil intermédiaire penche vers les premiers
départements. La liste propose donc d'abord le cahier dont la région et la
taille de commune manquent le plus au regard du tirage complet : à chaque
étape, les cahiers délimités restent à peu près représentatifs.

Des régions, des tailles et des noms de fichiers, jamais de texte.
"""

from collections import Counter

AXES = ("region", "taille")


def ordre(tirage: list[dict], faits: set[str]) -> list[dict]:
    """Les cahiers du tirage non faits, dans l'ordre où les délimiter.

    `faits` : fichiers des cahiers déjà délimités. Chaque étape prend le
    cahier dont la région et la taille ont le plus grand manque : part dans le
    tirage × (cahiers faits + 1) − cahiers faits de cette région, plus de même
    pour la taille. À égalité, l'ordre des fichiers."""
    parts = {a: Counter(t[a] for t in tirage) for a in AXES}
    comptes = {a: Counter(t[a] for t in tirage if t["fichier"] in faits) for a in AXES}
    fait = sum(1 for t in tirage if t["fichier"] in faits)
    reste = sorted(
        (t for t in tirage if t["fichier"] not in faits), key=lambda t: t["fichier"]
    )
    rangs = []
    while reste:
        # max garde le premier à égalité
        choisi = max(reste, key=lambda t, k=fait + 1: manque(t, k, parts, comptes))
        reste.remove(choisi)
        rangs.append(choisi)
        for a in AXES:
            comptes[a][choisi[a]] += 1
        fait += 1
    return rangs


def manque(t: dict, k: int, parts: dict, comptes: dict) -> float:
    """Ce qui manque à la région et à la taille de `t` pour que `k` cahiers
    suivent le tirage complet."""
    total = sum(parts[AXES[0]].values())
    return sum(parts[a][t[a]] / total * k - comptes[a][t[a]] for a in AXES)


def reordonner(liste: dict, tirage: list[dict], faits: set[str]) -> dict:
    """La liste « selection », ses cahiers à délimiter dans l'`ordre`, puis les
    cahiers faits (pour les revoir). Les éléments gardent leurs commentaires."""
    elements = {e["fichier"]: e for e in liste["elements"]}
    rangs = [t["fichier"] for t in ordre(tirage, faits)]
    rangs += sorted(f for f in elements if f in faits)
    rangs = [f for f in rangs if f in elements]
    rangs += [f for f in elements if f not in rangs]
    return {**liste, "elements": [elements[f] for f in rangs]}
