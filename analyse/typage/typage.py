"""Type de chaque page : vierge, dactylographiée ou manuscrite (issue #17).

Deux signaux, lus dans le PDF sans OCR :

- l'**encre** : part de pixels sombres au centre de la page, rendue à 50 dpi.
  Sous 0,3 %, la page est vierge, même si le recto transparaît en miroir
  (sa couche texte est alors du bruit). Le seuil de gris (160) garde les
  écritures pâles, qu'un seuil à 128 perd à cette résolution ;
- la **couche texte** : part de mots français connus (wordfreq), comme le
  score du POC. Une page encrée sans texte lisible est manuscrite.

Les pages mixtes (dactylographiées complétées à la main) ne sont pas
distinguées : l'encre hors du texte vient surtout des logos, tampons et bords
de scan, pas de l'écriture. Elles sortent en `dactylographiée`.

Les pages ajoutées à la numérisation sont signalées (`page_de_service`) :
l'intercalaire « Fin des pages écrites » est vierge, la page de garde garde
son type, car la commune y est parfois écrite à la main.
"""

import re
from dataclasses import dataclass

import pymupdf
from wordfreq import zipf_frequency

VIERGE = "vierge"
DACTYLOGRAPHIEE = "dactylographiée"
MANUSCRITE = "manuscrite"

DPI = 50
SEUIL_SOMBRE = 160  # niveau de gris sous lequel un pixel est de l'encre
MARGE = 0.08  # part de chaque bord ignorée : bords de scan, ombres, reliure
SEUIL_ENCRE = 0.003
SEUIL_QUALITE = 0.5
MOTS_MIN = 5

# Pages ajoutées à la numérisation : intercalaires et pages de garde
_INTERCALAIRE = re.compile(r"fin\s+des\s+pages\s+[ée]crites", re.IGNORECASE)
_PAGE_DE_GARDE = re.compile(
    r"grand\s+d[ée]bat\s+national.*cahier\s+citoyen", re.IGNORECASE | re.DOTALL
)
MOTS_MAX_SERVICE = 30

# Table de traduction : 1 pour un pixel sombre, 0 sinon
_SOMBRE = bytes(1 if niveau < SEUIL_SOMBRE else 0 for niveau in range(256))


@dataclass
class Typage:
    type_page: str
    encre: float
    qualite: float
    mots: int
    page_de_service: bool


def qualite(texte: str) -> tuple[float, int]:
    """Part de mots français connus parmi les mots de plus de deux lettres."""
    mots = [re.sub(r"[^a-zà-ÿ]", "", m.lower()) for m in texte.split()]
    mots = [m for m in mots if len(m) > 2]
    if not mots:
        return 0.0, 0
    return sum(zipf_frequency(m, "fr") >= 2 for m in mots) / len(mots), len(mots)


def encre(page: pymupdf.Page) -> float:
    """Part de pixels sombres dans le centre de la page, traits exclus.

    Une ligne ou une colonne de pixels sombre sur plus de la moitié de sa
    longueur est un trait (bord de scan, reliure, filet), pas de l'écriture.
    """
    pix = page.get_pixmap(dpi=DPI, colorspace=pymupdf.csGRAY)
    x0, x1 = int(pix.width * MARGE), int(pix.width * (1 - MARGE))
    y0, y1 = int(pix.height * MARGE), int(pix.height * (1 - MARGE))
    lignes = [
        pix.samples[y * pix.stride + x0 : y * pix.stride + x1].translate(_SOMBRE)
        for y in range(y0, y1)
    ]
    colonnes = _traits([sum(c) for c in zip(*lignes)], len(lignes))
    rangees = _traits([ligne.count(1) for ligne in lignes], x1 - x0)
    sombres = sum(
        ligne.count(1) - sum(ligne[x] for x in colonnes)
        for y, ligne in enumerate(lignes)
        if y not in rangees
    )
    return sombres / ((x1 - x0) * (y1 - y0))


def _traits(comptes: list[int], longueur: int, voisinage: int = 2) -> set[int]:
    """Positions des traits, et de leurs bords adoucis par le rendu."""
    traits = set()
    for i, n in enumerate(comptes):
        if n > longueur / 2:
            traits.update(
                range(max(0, i - voisinage), min(len(comptes), i + voisinage + 1))
            )
    return traits


def typer(page: pymupdf.Page) -> Typage:
    texte = page.get_text()
    q, mots = qualite(texte)
    e = encre(page)
    court = mots <= MOTS_MAX_SERVICE
    intercalaire = court and bool(_INTERCALAIRE.search(texte))
    garde = court and bool(_PAGE_DE_GARDE.search(texte))
    if e < SEUIL_ENCRE or intercalaire:
        type_page = VIERGE
    elif mots >= MOTS_MIN and q >= SEUIL_QUALITE:
        type_page = DACTYLOGRAPHIEE
    else:
        type_page = MANUSCRITE
    return Typage(type_page, e, q, mots, intercalaire or garde)
