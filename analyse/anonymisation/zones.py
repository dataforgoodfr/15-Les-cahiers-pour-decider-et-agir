"""Zones de signature d'une contribution, à cacher en entier (issue #128).

Le repérage manque surtout des données au bord des contributions : une
signature (« T.S. », « B. LOYER »), parfois suivie d'une adresse, sur les
dernières lignes ; un en-tête (« Dupont Jean, Montendre, le 7.01.2019 »)
sur la première. Ces lignes sont courtes : on les cache en entier, sans
chercher à les lire.

Une zone de fin : les dernières lignes non vides, en partant de la fin,
tant qu'elles sont courtes. Une zone de début : les premières lignes, de
même ; une ligne qui n'est qu'une date ne compte pas. Une ligne longue
arrête la zone : c'est le corps de la contribution.
"""

import re

MOTS = 12  # mots au plus d'une ligne courte
# une ligne qui n'est qu'une date (« 29/01/19 », « Le 7 janvier 2019 ») : elle
# entre dans la zone de début sans compter, l'en-tête suit souvent
DATE = re.compile(
    r"^\s*(?:le\s+)?(?:\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|"
    r"\d{1,2}(?:er)?\s+[a-zéû]+\s+\d{4})\s*[.,]?\s*$",
    re.IGNORECASE,
)


def _lignes(texte: str) -> list[tuple[int, int, str]]:
    """Les lignes non vides : (début, fin, texte), positions dans le texte."""
    sortie, debut = [], 0
    for ligne in texte.split("\n"):
        if ligne.strip():
            sortie.append((debut, debut + len(ligne), ligne))
        debut += len(ligne) + 1
    return sortie


def zones(
    texte: str, fin: int = 2, debut: int = 1, mots: int = MOTS
) -> list[tuple[int, int, str]]:
    """Les zones à cacher : (début, fin, « fin » ou « début »), au plus `fin`
    lignes courtes à la fin et `debut` au début. Une contribution faite
    seulement de lignes courtes n'a pas de zone de début : sa fin suffit."""
    lignes = _lignes(texte)
    sortie = []
    queue = []
    for ligne in reversed(lignes):
        if len(queue) == fin or len(ligne[2].split()) > mots:
            break
        queue.append(ligne)
    sortie += [(a, b, "fin") for a, b, _ in queue]
    restantes = lignes[: len(lignes) - len(queue)]
    tete, comptees = [], 0
    for ligne in restantes:
        date = bool(DATE.match(ligne[2]))
        if (comptees == debut and not date) or len(ligne[2].split()) > mots:
            break
        tete.append(ligne)
        comptees += not date
    if len(tete) < len(restantes):
        sortie += [(a, b, "début") for a, b, _ in tete]
    return sorted(sortie)
