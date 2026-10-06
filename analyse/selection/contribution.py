"""La contribution tirée d'un cahier, d'après les débuts notés à la main.

Le tirage (`tirage`) donne pour chaque cahier une position entre 0 et 1. Le
lecteur note tous les débuts de contributions du cahier, et parfois leurs
fins ; la contribution tirée est la ⌈position × n⌉-ième dans l'ordre de
lecture. Elle s'arrête à sa fin notée, sinon juste avant le début suivant,
sinon à la dernière page du cahier.

Des pages et des ordonnées en points PDF, jamais de texte.
"""

import math
from dataclasses import dataclass

MARGE = 6  # points : le début est un point posé sur la première ligne
DOUBLON = 10  # points : deux débuts si proches sont le même, posé deux fois


@dataclass(frozen=True)
class Tiree:
    rang: int  # 1 à n
    n: int
    page_debut: int
    y_debut: float
    page_fin: int
    y_fin: float | None  # None : jusqu'en bas de la page de fin
    fin_notee: bool

    @property
    def pages(self) -> list[int]:
        return list(range(self.page_debut, self.page_fin + 1))


def doublons(
    debuts: list[tuple[int, float]],
) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    """Sépare les débuts posés plusieurs fois au même endroit d'une page. Un
    seul compte ; l'intention reste à vérifier (deux clics trop lents pour un
    double clic voulaient une fin). Rend (débuts, endroits répétés)."""
    seuls: list[tuple[int, float]] = []
    repetes: list[tuple[int, float]] = []
    for p in sorted(debuts):
        if seuls and seuls[-1][0] == p[0] and p[1] - seuls[-1][1] < DOUBLON:
            if not repetes or repetes[-1] != seuls[-1]:
                repetes.append(seuls[-1])
        else:
            seuls.append(p)
    return seuls, repetes


def tiree(
    position: float,
    debuts: list[tuple[int, float]],
    fins: list[tuple[int, float]],
    derniere_page: int,
) -> Tiree | None:
    """La contribution tirée parmi les débuts et fins (page, ordonnée)."""
    if not debuts:
        return None
    debuts, fins = doublons(debuts)[0], sorted(fins)
    n = len(debuts)
    rang = min(n, max(1, math.ceil(position * n)))
    debut = debuts[rang - 1]
    suivant = debuts[rang] if rang < n else None
    fin = next(
        (f for f in fins if f >= debut and (suivant is None or f <= suivant)), None
    )
    if fin is not None:
        page_fin, y_fin = fin
    elif suivant is not None:
        page_fin, y_fin = suivant
    else:
        page_fin, y_fin = derniere_page, None
    return Tiree(rang, n, debut[0], debut[1], page_fin, y_fin, fin is not None)


def hors_contribution(
    t: Tiree, page: int, largeur: float, hauteur: float
) -> list[tuple[float, float, float, float]]:
    """Cadres (x0, y0, x1, y1) d'une page qui n'appartiennent pas à la
    contribution tirée : au-dessus de son début, en dessous de sa fin. Une
    fin notée garde sa ligne ; un début suivant, non."""
    cadres = []
    if page == t.page_debut and t.y_debut - MARGE > 0:
        cadres.append((0.0, 0.0, largeur, t.y_debut - MARGE))
    if page == t.page_fin and t.y_fin is not None:
        bas = t.y_fin + MARGE if t.fin_notee else t.y_fin - MARGE
        if bas < hauteur:
            cadres.append((0.0, max(0.0, bas), largeur, hauteur))
    return cadres
