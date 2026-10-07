"""La contribution tirée d'un cahier, d'après les débuts notés à la main.

Le tirage (`tirage`) donne pour chaque cahier une position entre 0 et 1. Le
lecteur note tous les débuts de contributions du cahier, et parfois leurs
fins ; la contribution tirée est la ⌈position × n⌉-ième dans l'ordre de
lecture. Elle s'arrête à sa fin notée, sinon juste avant le début suivant,
sinon à la dernière page du cahier.

L'ordre de lecture se prend dans le sens où la page se lit : une page
numérisée de travers a été tournée à l'affichage, rotation gardée dans le
carnet d'annotation. Les points (page, y, x) sont dans ce sens-là
(`Sens.vers_lecture`) ; les cadres repartent dans le repère du PDF
(`Sens.vers_pdf`).

Des pages et des positions en points PDF, jamais de texte.
"""

import math
from dataclasses import dataclass

MARGE = 6  # points : le début est un point posé sur la première ligne
DOUBLON = 10  # points : deux débuts si proches sont le même, posé deux fois
# points : une fin si près sous un début est sur sa ligne, celle de la
# contribution d'avant (fin cliquée un peu bas, début un peu haut)
MEME_LIGNE = 12


@dataclass(frozen=True)
class Sens:
    """Le sens de lecture d'une page : sa rotation à l'affichage (quart de
    tour horaire) et ses dimensions dans le repère du PDF."""

    rotation: int
    largeur: float
    hauteur: float

    @property
    def dimensions(self) -> tuple[float, float]:
        """Largeur et hauteur de la page lue."""
        if self.rotation % 180:
            return self.hauteur, self.largeur
        return self.largeur, self.hauteur

    def vers_lecture(self, x: float, y: float) -> tuple[float, float]:
        w, h = self.largeur, self.hauteur
        return {90: (h - y, x), 180: (w - x, h - y), 270: (y, w - x)}.get(
            self.rotation, (x, y)
        )

    def vers_pdf(self, u: float, v: float) -> tuple[float, float]:
        w, h = self.largeur, self.hauteur
        return {90: (v, h - u), 180: (w - u, h - v), 270: (w - v, u)}.get(
            self.rotation, (u, v)
        )

    def cadre_pdf(self, x0, y0, x1, y1) -> tuple[float, float, float, float]:
        """Un cadre de la page lue, dans le repère du PDF."""
        (a, b), (c, d) = self.vers_pdf(x0, y0), self.vers_pdf(x1, y1)
        return min(a, c), min(b, d), max(a, c), max(b, d)


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


Point = tuple[int, float, float]  # page, y, x dans le sens de lecture


def doublons(debuts: list[Point]) -> tuple[list[Point], list[Point]]:
    """Sépare les débuts posés plusieurs fois au même point d'une page. Un
    seul compte ; l'intention reste à vérifier (deux clics trop lents pour un
    double clic voulaient une fin). Des débuts proches mais distincts, comme
    les cases d'une grille, restent tous. Rend (débuts, points répétés)."""
    seuls: list[Point] = []
    repetes: list[Point] = []
    for p in sorted(debuts):
        meme = next(
            (
                s
                for s in seuls
                if s[0] == p[0] and math.hypot(p[1] - s[1], p[2] - s[2]) < DOUBLON
            ),
            None,
        )
        if meme is None:
            seuls.append(p)
        elif meme not in repetes:
            repetes.append(meme)
    return seuls, repetes


def tiree(
    position: float,
    debuts: list[Point],
    fins: list[Point],
    derniere_page: int,
) -> Tiree | None:
    """La contribution tirée parmi les débuts et fins (page, y, x)."""
    if not debuts:
        return None
    debuts, fins = doublons(debuts)[0], sorted(fins)
    n = len(debuts)
    rang = min(n, max(1, math.ceil(position * n)))
    debut = debuts[rang - 1]
    suivant = debuts[rang] if rang < n else None

    def apres(f: Point, d: Point) -> bool:
        return (f[0], f[1]) > (d[0], d[1] + MEME_LIGNE)

    fin = next(
        (
            f
            for f in fins
            if apres(f, debut) and (suivant is None or not apres(f, suivant))
        ),
        None,
    )
    if fin is not None:
        page_fin, y_fin = fin[:2]
    elif suivant is not None:
        page_fin, y_fin = suivant[:2]
    else:
        page_fin, y_fin = derniere_page, None
    return Tiree(rang, n, debut[0], debut[1], page_fin, y_fin, fin is not None)


def hors_contribution(
    t: Tiree, page: int, largeur: float, hauteur: float
) -> list[tuple[float, float, float, float]]:
    """Cadres (x0, y0, x1, y1) de la page lue, de `largeur` × `hauteur`, qui
    n'appartiennent pas à la contribution tirée : au-dessus de son début, en
    dessous de sa fin. Une fin notée garde sa ligne ; un début suivant, non."""
    cadres = []
    if page == t.page_debut and t.y_debut - MARGE > 0:
        cadres.append((0.0, 0.0, largeur, t.y_debut - MARGE))
    if page == t.page_fin and t.y_fin is not None:
        bas = t.y_fin + MARGE if t.fin_notee else t.y_fin - MARGE
        if bas < hauteur:
            cadres.append((0.0, max(0.0, bas), largeur, hauteur))
    return cadres


def derniere_page(pages: list[dict], fichier: str, qualifications: dict) -> int:
    """La dernière page que l'outil d'annotation montre : il cache les pages
    vierges (type vérifié s'il y en a un, sinon type du typage)."""
    montrees = [
        p["page"]
        for p in pages
        if (qualifications.get((fichier, p["page"]), {}).get("type") or p["type"])
        != "vierge"
    ]
    return max(montrees, default=len(pages))
