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

Une double page (deux pages d'un cahier ouvert, numérisées ensemble) se lit
page de gauche puis page de droite. Elle est qualifiée à la main dans l'outil
d'annotation (« double page »), ou reconnue à ses notes : lue à
l'horizontale, elle porte un début de contribution vers le milieu de sa
largeur, le haut de la page de droite. Sur une page simple, les débuts sont au
bord gauche. Les points de la page de droite passent alors sous ceux de la
page de gauche, une hauteur de page plus bas (`en_colonnes`).

Des pages et des positions en points PDF, jamais de texte.
"""

import math
from dataclasses import dataclass

MARGE = 6  # points : le début est un point posé sur la première ligne
CENTRE = (0.35, 0.65)  # part de la largeur où un début ouvre la page de droite
DOUBLON = 10  # points : deux débuts si proches sont le même, posé deux fois


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


Point = tuple[int, float, float]  # page, y, x dans le sens de lecture


def coupure(sens: Sens, debuts: list[float], double: bool | None) -> float | None:
    """L'abscisse, dans la page lue, entre les deux pages d'une double page ;
    None pour une page simple.

    `debuts` : les abscisses des débuts notés sur la page, dans le sens de
    lecture. `double` : la qualification « double page », None si personne
    ne l'a tranchée. La coupure passe juste avant le plus à gauche des débuts
    du milieu, sinon au milieu de la page."""
    largeur, hauteur = sens.dimensions
    milieu = [x for x in debuts if CENTRE[0] * largeur < x < CENTRE[1] * largeur]
    if double is False or (double is None and not (largeur > hauteur and milieu)):
        return None
    return min(milieu) - MARGE if milieu else largeur / 2


def en_colonnes(point: Point, coupure: float | None, hauteur: float) -> Point:
    """Le point dans l'ordre de lecture d'une double page : la page de
    droite est lue sous la page de gauche, une hauteur de page plus bas."""
    page, y, x = point
    if coupure is not None and x >= coupure:
        return page, y + hauteur, x
    return point


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
    fin = next(
        (f for f in fins if f >= debut and (suivant is None or f <= suivant)), None
    )
    if fin is not None:
        page_fin, y_fin = fin[:2]
    elif suivant is not None:
        page_fin, y_fin = suivant[:2]
    else:
        page_fin, y_fin = derniere_page, None
    return Tiree(rang, n, debut[0], debut[1], page_fin, y_fin, fin is not None)


def hors_contribution(
    t: Tiree,
    page: int,
    largeur: float,
    hauteur: float,
    coupure: float | None = None,
) -> list[tuple[float, float, float, float]]:
    """Cadres (x0, y0, x1, y1) de la page lue, de `largeur` × `hauteur`, qui
    n'appartiennent pas à la contribution tirée : au-dessus de son début, en
    dessous de sa fin. Une fin notée garde sa ligne ; un début suivant, non.
    Sur une double page (`coupure`), chaque page est couverte à part."""
    colonnes = (
        [(0.0, largeur)] if coupure is None else [(0.0, coupure), (coupure, largeur)]
    )
    total = len(colonnes) * hauteur
    hors = []  # intervalles de hauteur dans l'ordre de lecture (`en_colonnes`)
    if page == t.page_debut and t.y_debut - MARGE > 0:
        hors.append((0.0, t.y_debut - MARGE))
    if page == t.page_fin and t.y_fin is not None:
        bas = t.y_fin + MARGE if t.fin_notee else t.y_fin - MARGE
        if bas < total:
            hors.append((max(0.0, bas), total))
    cadres = []
    for haut, bas in hors:
        for k, (x0, x1) in enumerate(colonnes):
            y0, y1 = max(haut, k * hauteur), min(bas, (k + 1) * hauteur)
            if y0 < y1:
                cadres.append((x0, y0 - k * hauteur, x1, y1 - k * hauteur))
    return cadres


PAS = 2.0  # points : hauteur des bandes qui couvrent le dehors d'un polygone


def _dedans(points: list, y: float) -> list[tuple[float, float]]:
    """Les intervalles de x à l'intérieur du polygone, à la hauteur y."""
    xs = sorted(
        x0 + (y - y0) * (x1 - x0) / (y1 - y0)
        for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1])
        if min(y0, y1) <= y < max(y0, y1)
    )
    return list(zip(xs[::2], xs[1::2]))


def _intersection(a: list, b: list) -> list[tuple[float, float]]:
    return [
        (max(a0, b0), min(a1, b1))
        for a0, a1 in a
        for b0, b1 in b
        if max(a0, b0) < min(a1, b1)
    ]


def hors_polygone(
    points: list, largeur: float, hauteur: float
) -> list[tuple[float, float, float, float]]:
    """Cadres (x0, y0, x1, y1) qui couvrent la page hors du polygone, dans son
    repère. Par bandes de PAS points : n'est gardé d'une bande que ce qui est
    dedans en haut et en bas, pour qu'un bord penché ne laisse rien passer."""
    cadres: list[tuple[float, float, float, float]] = []
    precedents: list[tuple[float, float]] | None = None
    y = 0.0
    while y < hauteur:
        bas = min(y + PAS, hauteur)
        # le bas de la bande pris juste au-dessus : un bord du polygone posé
        # sur la limite de deux bandes appartient à celle du dessous
        dedans = _intersection(_dedans(points, y), _dedans(points, bas - 1e-3))
        bords = [0.0, *(x for i in dedans for x in i), largeur]
        dehors = [
            (max(0.0, x0), min(largeur, x1))
            for x0, x1 in zip(bords[::2], bords[1::2])
            if min(largeur, x1) > max(0.0, x0)
        ]
        if dehors == precedents:
            # la même découpe que la bande d'avant : on prolonge ses cadres
            for i in range(len(dehors)):
                x0, y0, x1, _ = cadres[-len(dehors) + i]
                cadres[-len(dehors) + i] = (x0, y0, x1, bas)
        else:
            cadres.extend((x0, y, x1, bas) for x0, x1 in dehors)
        precedents = dehors
        y = bas
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


def delimites(
    fichiers, pages: dict[str, list[dict]], vues: set[tuple[str, int]], qualifications
) -> set[str]:
    """Les cahiers délimités : une page vue atteint leur dernière page montrée.

    Une page vue plus loin compte aussi : le typage ou un type vérifié peut
    rendre vierge, donc cachée, une page que le lecteur a vue et marquée."""
    plus_loin: dict[str, int] = {}
    for f, page in vues:
        plus_loin[f] = max(page, plus_loin.get(f, 0))
    return {
        f
        for f in fichiers
        if f in pages
        and plus_loin.get(f, 0) >= derniere_page(pages[f], f, qualifications)
    }


ECARTER = "à écarter"


def ecartee(fichier: str, pages: list[int], qualifications: dict) -> bool:
    """Une page de la contribution porte un contenu à ne pas publier."""
    return any(
        qualifications.get((fichier, n), {}).get("problemes", {}).get(ECARTER)
        for n in pages
    )
