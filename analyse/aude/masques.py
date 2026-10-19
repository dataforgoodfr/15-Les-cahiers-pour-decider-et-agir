"""Zones caviardées par les Archives départementales de l'Aude, reportées sur les pages BnF.

Sur les pages publiées par le CESE, les données personnelles sont cachées
par des rectangles gris : des aplats parfaitement uniformes, sans le grain du
papier ni le bruit du scan. On les repère comme les zones non blanches dont
l'écart-type local est presque nul et qui remplissent leur rectangle.

Les carreaux d'un papier quadrillé sont aussi des aplats, de 12 à 25 pixels
de côté à la largeur de travail ; les vrais masques font au moins 40 pixels
de large et 15 de haut. Une page qui garde plus de MASQUES_MAX zones est
signalée à vérifier (quadrillage plus grand, fond uniforme).

La similitude trouvée au rapprochement (`rapprochement`) envoie ensuite
chaque rectangle sur la page BnF, en points PDF. Elle vaut pour toute la
page ; le papier, lui, n'est pas plat, et localement l'écart atteint 6 pixels
(1 mm environ). On recale donc chaque masque : on ramène la page BnF dans le
cadre de la page publiée, et on cherche le petit décalage qui fait le mieux
coïncider les deux images autour du masque. Cette corrélation, l'accord, dit
si le report est sûr ; elle n'a pas de sens quand l'entourage est blanc,
sans même une réglure.

On obtient ainsi ce que des archivistes ont caché, page par page, sur nos
scans, manuscrits compris : un étalon pour l'anonymisation (#128).

Ce que les Archives ont retiré par découpe (une signature coupée en bas de
page) ne laisse pas d'aplat : ces zones manquent à l'étalon.
"""

import cv2
import numpy as np
import pymupdf

from aude.rapprochement import (
    SEUIL,
    descripteurs,
    image_bnf_vers_page,
    image_publiee,
    similitude,
)

FENETRE = 5  # pixels : côté de la fenêtre de l'écart-type local
ECART_TYPE = 1.5  # niveaux de gris : en deçà, la zone est un aplat
GRIS_MIN = 100  # un aplat plus sombre est de l'encre, pas un masque
LARGEUR_MIN = 40  # pixels, à la largeur de travail (environ 8 mm)
HAUTEUR_MIN = 15  # pixels (environ 3 mm)
REMPLISSAGE = 0.85  # part du rectangle englobant couverte par l'aplat
MASQUES_MAX = 10  # au-delà, la page est à vérifier

BLANC_PAPIER = 245  # au-dessus : du fond, pas un masque

ANNEAU = 20  # pixels autour du masque où l'on compare les deux images
DECALAGE_MAX = 6  # pixels : recalage local cherché de part et d'autre
PAS = 2
CONTRASTE_MIN = 5  # écart-type de l'anneau sans lequel on ne recale pas


def masques(image: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Rectangles (x, y, largeur, hauteur) gris et uniformes de l'image."""
    f = image.astype(np.float32)
    moyenne = cv2.blur(f, (FENETRE, FENETRE))
    variance = cv2.blur(f * f, (FENETRE, FENETRE)) - moyenne * moyenne
    aplat = (
        (variance < ECART_TYPE**2) & (image < BLANC_PAPIER) & (image > GRIS_MIN)
    ).astype(np.uint8)
    n, etiquettes, stats, _ = cv2.connectedComponentsWithStats(aplat, connectivity=8)
    rectangles = []
    for i, (x, y, w, h, aire) in enumerate(stats[1:n], start=1):
        if w >= LARGEUR_MIN and h >= HAUTEUR_MIN and aire >= REMPLISSAGE * w * h:
            gris = int(np.median(image[etiquettes == i]))
            rectangles.append(_au_bord(image, (int(x), int(y), int(w), int(h)), gris))
    return rectangles


def _au_bord(image, rectangle, gris) -> tuple[int, int, int, int]:
    """Le rectangle étendu jusqu'au bord du masque : la fenêtre de l'écart-type
    mord sur ce bord, l'aplat s'arrête une demi-fenêtre avant lui. On garde
    les rangées et colonnes voisines qui ont, en majorité, le gris du masque."""
    x, y, w, h = rectangle
    r = FENETRE // 2
    x0, y0 = max(x - r, 0), max(y - r, 0)
    zone = np.abs(image[y0 : y + h + r, x0 : x + w + r].astype(int) - gris) <= 1
    rangees = np.flatnonzero(zone.mean(axis=1) > 0.5)
    colonnes = np.flatnonzero(zone.mean(axis=0) > 0.5)
    return (
        x0 + int(colonnes[0]),
        y0 + int(rangees[0]),
        int(colonnes[-1] - colonnes[0]) + 1,
        int(rangees[-1] - rangees[0]) + 1,
    )


def _composer(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """La transformation a, puis b (matrices 2 × 3)."""
    return b[:, :2] @ a + np.hstack([np.zeros((2, 2)), b[:, 2:]])


def reporter(
    rectangle: tuple[int, int, int, int], transformation: np.ndarray
) -> tuple[float, float, float, float]:
    """Rectangle englobant (x0, y0, x1, y1) de l'image d'un rectangle."""
    x, y, w, h = rectangle
    coins = np.array([[x, y, 1], [x + w, y, 1], [x, y + h, 1], [x + w, y + h, 1]])
    image = coins @ transformation.T
    x0, y0 = image.min(axis=0)
    x1, y1 = image.max(axis=0)
    return tuple(round(float(v), 1) for v in (x0, y0, x1, y1))


def _correlation(a: np.ndarray, b: np.ndarray) -> float:
    a = a.astype(float) - a.mean()
    b = b.astype(float) - b.mean()
    norme = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / norme) if norme else 0.0


def recaler(
    publiee: np.ndarray,
    ramenee: np.ndarray,
    rectangle: tuple[int, int, int, int],
    hors_masques: np.ndarray,
) -> tuple[int, int, float | None]:
    """Décalage (dx, dy) qui fait coïncider la page BnF ramenée avec la page
    publiée autour du masque : ce qui est en (x, y) sur la page publiée est
    en (x - dx, y - dy) sur la page ramenée. Avec l'accord obtenu ; (0, 0,
    None) si l'entourage est trop blanc pour juger."""
    x, y, w, h = rectangle
    hauteur, largeur = publiee.shape
    # l'anneau reste à DECALAGE_MAX du bord, pour que toute fenêtre décalée
    # tienne dans l'image
    y0, x0 = max(y - ANNEAU, DECALAGE_MAX), max(x - ANNEAU, DECALAGE_MAX)
    y1 = min(y + h + ANNEAU, hauteur - DECALAGE_MAX)
    x1 = min(x + w + ANNEAU, largeur - DECALAGE_MAX)
    if y1 <= y0 or x1 <= x0:
        return 0, 0, None
    garde = hors_masques[y0:y1, x0:x1]
    reference = publiee[y0:y1, x0:x1][garde]
    if reference.size == 0 or reference.std() < CONTRASTE_MIN:
        return 0, 0, None
    accord, dx, dy = max(
        (
            _correlation(
                reference, ramenee[y0 - dy : y1 - dy, x0 - dx : x1 - dx][garde]
            ),
            dx,
            dy,
        )
        for dy in range(-DECALAGE_MAX, DECALAGE_MAX + 1, PAS)
        for dx in range(-DECALAGE_MAX, DECALAGE_MAX + 1, PAS)
    )
    return dx, dy, round(accord, 2)


def zones(args) -> tuple[tuple, int, list[tuple] | None]:
    """Les masques d'une page publiée, en points de sa page BnF.

    args : (PDF du canton, page, PDF BnF, page BnF), numéros à partir de 1.
    Renvoie args, le nombre d'appariements et les masques (x0, y0, x1, y1,
    accord) ; None si la similitude ne se retrouve pas.
    """
    canton, page, fichier, page_bnf = args
    with pymupdf.open(canton) as doc:
        publiee = image_publiee(doc[page - 1])
    with pymupdf.open(fichier) as doc:
        bnf = image_bnf_vers_page(doc[page_bnf - 1])
    if publiee is None or bnf is None:
        return args, 0, None
    image, vers_page = bnf
    matrice, n = similitude(descripteurs(publiee), descripteurs(image))
    if matrice is None or n < SEUIL:
        return args, n, None
    transformation = _composer(matrice, vers_page)
    hauteur, largeur = publiee.shape
    # la page BnF dans le cadre de la page publiée
    ramenee = cv2.warpAffine(
        image, cv2.invertAffineTransform(matrice), (largeur, hauteur), borderValue=255
    )
    rectangles = masques(publiee)
    hors_masques = np.ones(publiee.shape, bool)
    for x, y, w, h in rectangles:
        hors_masques[y : y + h, x : x + w] = False
    resultat = []
    for x, y, w, h in rectangles:
        dx, dy, accord = recaler(publiee, ramenee, (x, y, w, h), hors_masques)
        resultat.append((*reporter((x - dx, y - dy, w, h), transformation), accord))
    return args, n, resultat
