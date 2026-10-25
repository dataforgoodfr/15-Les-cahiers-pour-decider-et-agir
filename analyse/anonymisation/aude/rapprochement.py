"""Pages des cahiers de l'Aude publiés par le CESE, rapprochées des pages BnF.

Le CESE de l'Aude a publié en 2024 les cahiers de 95 communes, regroupés par
canton (`../aude/`), anonymisés par les Archives départementales : rectangles
gris ou découpe, images contrastées et agrandies. Les mêmes cahiers sont dans
le versement BnF, non anonymisés. Rapprocher les deux donne la commune de
chaque page publiée (le code INSEE du nom de fichier BnF) et, page par page,
une version caviardée par des humains de nos scans.

On compare des images, sans rien lire. Une vignette de la page entière ne
suffit pas : le CESE recadre, agrandit, pose l'image sur une page A4 blanche,
et deux pages réglées se ressemblent plus qu'une page et sa copie recadrée.
On prend donc des points d'intérêt SIFT, insensibles à l'échelle et au
contraste ; deux images de la même page en partagent des centaines qu'une
même similitude (translation, rotation, échelle) envoie les uns sur les
autres, deux pages différentes quelques dizaines au plus.

Pour ne pas comparer chaque page publiée aux 1 300 pages BnF, un index des
descripteurs de toutes les pages BnF vote d'abord pour quelques candidates ;
seules celles-ci sont vérifiées par la géométrie (RANSAC). Les pages BnF
vierges sont écartées : leur grain attire des appariements de hasard.
"""

from typing import NamedTuple

import cv2
import numpy as np
import pymupdf

LARGEUR = 1000  # pixels : les images sont ramenées à cette largeur
DPI = 110  # rendu, avant mise à la largeur
POINTS = 1500  # points d'intérêt gardés par page
LOWE = 0.8  # test du rapport des deux plus proches voisins
CANDIDATES = 5  # pages BnF vérifiées par la géométrie
TOLERANCE = 8  # pixels : écart admis après la similitude
BLANC = 245  # niveau de gris au-dessus duquel un pixel est du fond
IMAGE_MIN = 500  # pixels : en deçà, l'image d'une page du CESE est un logo
TEXTE_MAX = 100  # caractères : au-delà, la page est un texte du CESE

# une page publiée est rapprochée si elle partage au moins SEUIL points avec
# une page BnF ; douteuse si une page d'une autre commune en partage plus du
# ECART-ième (un imprimé type, rempli dans plusieurs communes). Les autres
# pages de la même commune au-dessus du seuil sont des doublons du versement :
# un même cahier y est parfois déposé deux ou trois fois.
SEUIL = 100
ECART = 3


def _gris(pix: pymupdf.Pixmap) -> np.ndarray:
    a = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.stride)
    return a[:, : pix.w].copy()


def _cadrer(a: np.ndarray) -> tuple[np.ndarray, tuple[int, int, float]] | None:
    """L'image recadrée sur ce qui n'est pas du fond, à LARGEUR ; et le
    cadrage (x0, y0, facteur) pour revenir à l'image d'origine."""
    ys, xs = np.where(a < BLANC)
    if len(ys) == 0:
        return None
    x0, y0 = int(xs.min()), int(ys.min())
    a = a[y0 : ys.max() + 1, x0 : xs.max() + 1]
    f = LARGEUR / a.shape[1]
    return cv2.resize(a, None, fx=f, fy=f, interpolation=cv2.INTER_AREA), (x0, y0, f)


def _a_la_largeur(a: np.ndarray) -> np.ndarray | None:
    cadree = _cadrer(a)
    return None if cadree is None else cadree[0]


def nature(page: pymupdf.Page) -> str:
    """« scan » pour une page de cahier, « cese » pour les textes du CESE."""
    grandes = [im for im in page.get_images() if max(im[2], im[3]) >= IMAGE_MIN]
    if grandes and len(page.get_text().strip()) <= TEXTE_MAX:
        return "scan"
    return "cese"


def image_publiee(page: pymupdf.Page) -> np.ndarray | None:
    """L'image du scan, sans la page A4 autour ni le numéro de page."""
    xref = max(page.get_images(), key=lambda im: im[2] * im[3])[0]
    zone = page.get_image_rects(xref)[0] & page.rect
    pix = page.get_pixmap(dpi=DPI, colorspace=pymupdf.csGRAY, clip=zone)
    return _a_la_largeur(_gris(pix))


def image_bnf(page: pymupdf.Page) -> np.ndarray | None:
    return _a_la_largeur(_gris(page.get_pixmap(dpi=DPI, colorspace=pymupdf.csGRAY)))


def image_bnf_vers_page(page: pymupdf.Page) -> tuple[np.ndarray, np.ndarray] | None:
    """L'image d'une page BnF, et la transformation (2 × 3) de ses pixels
    vers les points de la page PDF."""
    cadree = _cadrer(_gris(page.get_pixmap(dpi=DPI, colorspace=pymupdf.csGRAY)))
    if cadree is None:
        return None
    image, (x0, y0, f) = cadree
    k = 72 / DPI
    return image, np.array([[k / f, 0, k * x0], [0, k / f, k * y0]])


def descripteurs(image: np.ndarray | None) -> tuple[np.ndarray, np.ndarray]:
    """Positions (n, 2) et descripteurs SIFT (n, 128) ; vides sans image."""
    vide = np.empty((0, 2), np.float32), np.empty((0, 128), np.float32)
    if image is None:
        return vide
    points, desc = cv2.SIFT_create(POINTS).detectAndCompute(image, None)
    if desc is None:
        return vide
    return np.float32([p.pt for p in points]), desc


def _lowe(paires) -> list:
    return [
        a
        for a, b in (p for p in paires if len(p) == 2)
        if a.distance < LOWE * b.distance
    ]


def similitude(a, b) -> tuple[np.ndarray | None, int]:
    """La similitude (2 × 3) qui envoie la page a sur la page b, et le nombre
    d'appariements qu'elle explique."""
    (pa, da), (pb, db) = a, b
    if len(da) < 2 or len(db) < 2:
        return None, 0
    bons = _lowe(cv2.BFMatcher(cv2.NORM_L2).knnMatch(da, db, k=2))
    if len(bons) < 4:
        return None, 0
    source = pa[[m.queryIdx for m in bons]]
    cible = pb[[m.trainIdx for m in bons]]
    matrice, gardes = cv2.estimateAffinePartial2D(
        source, cible, method=cv2.RANSAC, ransacReprojThreshold=TOLERANCE
    )
    return (None, 0) if gardes is None else (matrice, int(gardes.sum()))


def points_communs(a, b) -> int:
    """Appariements de deux pages qu'une même similitude explique."""
    return similitude(a, b)[1]


class Index:
    """Les descripteurs de toutes les pages BnF, pour voter vite."""

    def __init__(self, pages: list[tuple[np.ndarray, np.ndarray]], communes: list[str]):
        self.pages, self.communes = pages, communes
        self.proprietaire = np.concatenate(
            [np.full(len(d), i) for i, (_, d) in enumerate(pages)]
        )
        self.flann = cv2.FlannBasedMatcher({"algorithm": 1, "trees": 4}, {"checks": 32})
        self.flann.add([np.concatenate([d for _, d in pages])])
        self.flann.train()

    def candidates(self, desc: np.ndarray) -> list[int]:
        if len(desc) < 2:
            return []
        bons = _lowe(self.flann.knnMatch(desc, k=2))
        votes = np.bincount(
            self.proprietaire[[m.trainIdx for m in bons]], minlength=len(self.pages)
        )
        return [int(i) for i in np.argsort(votes)[::-1][:CANDIDATES] if votes[i]]

    def rapprocher(self, page) -> Rapprochement:
        verifiees = sorted(
            (
                (points_communs(page, self.pages[i]), i)
                for i in self.candidates(page[1])
            ),
            reverse=True,
        )
        return Rapprochement.depuis(verifiees, self.communes)


class Rapprochement(NamedTuple):
    page: int | None  # indice de la page BnF retenue
    score: int
    autre_commune: int  # meilleur score d'une page d'une autre commune
    doublons: list[int]  # autres pages de la même commune au-dessus du seuil
    douteuse: bool

    @classmethod
    def depuis(cls, verifiees: list[tuple[int, int]], communes: list[str]):
        """Décide à partir des (score, page) vérifiés, du meilleur au moins bon."""
        if not verifiees:
            return cls(None, 0, 0, [], False)
        score, i = verifiees[0]
        autre = max((s for s, j in verifiees if communes[j] != communes[i]), default=0)
        if score < SEUIL:
            return cls(None, score, autre, [], False)
        doublons = [
            j for s, j in verifiees[1:] if s >= SEUIL and communes[j] == communes[i]
        ]
        return cls(i, score, autre, doublons, ECART * autre > score)


def pages_bnf(args) -> list[tuple[str, int, tuple]]:
    """Nom, numéro et descripteurs des pages non vierges d'un fichier BnF."""
    chemin, vierges = args
    with pymupdf.open(chemin) as doc:
        return [
            (chemin.name, numero, descripteurs(image_bnf(page)))
            for numero, page in enumerate(doc, start=1)
            if numero not in vierges
        ]


def pages_publiees(chemin) -> list[tuple[str, int, str, tuple | None]]:
    """Canton, numéro, nature et descripteurs (scans seulement) des pages."""
    with pymupdf.open(chemin) as doc:
        lignes = []
        for numero, page in enumerate(doc, start=1):
            n = nature(page)
            d = descripteurs(image_publiee(page)) if n == "scan" else None
            lignes.append((chemin.stem, numero, n, d))
        return lignes
