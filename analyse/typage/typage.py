"""Type de chaque page : vierge, dactylographiée, manuscrite ou mixte (issue #17).

Deux signaux, lus dans le PDF sans OCR :

- l'**encre** : part de pixels sombres au centre de la page, rendue à 50 dpi.
  Sous 0,3 %, la page est vierge, même si le recto transparaît en miroir
  (sa couche texte est alors du bruit). Le seuil de gris (160) garde les
  écritures pâles, qu'un seuil à 128 perd à cette résolution ;
- la **couche texte** : part de mots français connus (wordfreq), comme le
  score du POC. Une page encrée sans texte lisible est manuscrite.

Une page est **mixte** quand une partie de son contenu est manuscrite, donc à
passer au HTR : en pratique, les formulaires imprimés (AMIF, mairies…) remplis
à la main. Leur gabarit est reconnu dans la couche texte (« Souhaite que
soient traités… ») ; la page est mixte si l'essentiel de l'encre est hors des
mots du gabarit, lignes de champ et pointillés exclus. Signatures, coordonnées,
tampons et annotations ne font pas une page mixte : sur une page quelconque,
l'encre hors du texte vient surtout des logos et des bords de scan, et ne
distingue pas l'écriture. Une page tournée, dont la couche texte est du bruit,
n'a pas de gabarit reconnu.

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
MIXTE = "mixte"

DPI = 50
SEUIL_SOMBRE = 160  # niveau de gris sous lequel un pixel est de l'encre
MARGE = 0.08  # part de chaque bord ignorée : bords de scan, ombres, reliure
SEUIL_ENCRE = 0.003
SEUIL_QUALITE = 0.5
MOTS_MIN = 5

# Formulaires remplis à la main : gabarit dans la couche texte, part de l'encre
# hors de ses mots. Réglé sur 75 pages à gabarit vérifiées à la main.
_GABARIT = re.compile(r"souhaite\s+que\s+soi", re.IGNORECASE)
_POINTILLES = re.compile(r"[._\-…:·•]{3,}")
SEUIL_MIXTE = 0.45
TRAIT_HORIZONTAL = 20  # pixels d'affilée (1 cm à 50 dpi) : une ligne de champ

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


def _normaliser(mot: str) -> str:
    return re.sub(r"[^a-zà-ÿ]", "", mot.lower())


def _connu(mot: str) -> bool:
    return len(mot) > 2 and zipf_frequency(mot, "fr") >= 2


def qualite(texte: str) -> tuple[float, int]:
    """Part de mots français connus parmi les mots de plus de deux lettres."""
    mots = [m for m in map(_normaliser, texte.split()) if len(m) > 2]
    if not mots:
        return 0.0, 0
    return sum(map(_connu, mots)) / len(mots), len(mots)


def _zone(page: pymupdf.Page) -> tuple[pymupdf.Pixmap, int, int, list[bytes]]:
    """Le centre de la page, en lignes de pixels : 1 pour l'encre, 0 sinon."""
    pix = page.get_pixmap(dpi=DPI, colorspace=pymupdf.csGRAY)
    x0, x1 = int(pix.width * MARGE), int(pix.width * (1 - MARGE))
    y0, y1 = int(pix.height * MARGE), int(pix.height * (1 - MARGE))
    lignes = [
        pix.samples[y * pix.stride + x0 : y * pix.stride + x1].translate(_SOMBRE)
        for y in range(y0, y1)
    ]
    return pix, x0, y0, lignes


def _hors_traits(lignes: list[bytes]):
    """Les lignes de pixels hors des traits, avec les colonnes des traits.

    Une ligne ou une colonne de pixels sombre sur plus de la moitié de sa
    longueur est un trait (bord de scan, reliure, filet), pas de l'écriture.
    """
    largeur = len(lignes[0]) if lignes else 0
    colonnes = _traits([sum(c) for c in zip(*lignes)], len(lignes))
    rangees = _traits([ligne.count(1) for ligne in lignes], largeur)
    return ((y, ligne) for y, ligne in enumerate(lignes) if y not in rangees), colonnes


def encre(page: pymupdf.Page) -> float:
    """Part de pixels sombres dans le centre de la page, traits exclus."""
    _, _, _, lignes = _zone(page)
    if not lignes:
        return 0.0
    gardees, colonnes = _hors_traits(lignes)
    sombres = sum(
        ligne.count(1) - sum(ligne[x] for x in colonnes) for _, ligne in gardees
    )
    return sombres / (len(lignes) * len(lignes[0]))


def part_hors_texte(page: pymupdf.Page) -> float:
    """Part de l'encre hors des mots connus et des pointillés de la couche texte.

    Les suites horizontales de plus de `TRAIT_HORIZONTAL` pixels (lignes de
    champ d'un formulaire) ne comptent pas comme hors du texte.
    """
    pix, x0, y0, lignes = _zone(page)
    echelle, marge = DPI / 72, 2
    masque = [bytearray(pix.width) for _ in range(pix.height)]
    for a, b, c, d, mot, *_ in page.get_text("words"):
        if not (_POINTILLES.fullmatch(mot) or _connu(_normaliser(mot))):
            continue
        g, dr = (
            max(0, int(a * echelle) - marge),
            min(pix.width, int(c * echelle) + marge),
        )
        for y in range(
            max(0, int(b * echelle) - marge), min(pix.height, int(d * echelle) + marge)
        ):
            masque[y][g:dr] = b"\x01" * (dr - g)
    gardees, colonnes = _hors_traits(lignes)
    total = hors = 0
    for y, ligne in gardees:
        longues = _suites(ligne, TRAIT_HORIZONTAL)
        dans_texte = masque[y0 + y]
        for x, sombre in enumerate(ligne):
            if sombre and x not in colonnes:
                total += 1
                hors += x not in longues and not dans_texte[x0 + x]
    return hors / total if total else 0.0


def _suites(ligne: bytes, longueur: int) -> set[int]:
    """Positions des suites d'au moins `longueur` pixels sombres."""
    positions, debut = set(), None
    for x, sombre in enumerate([*ligne, 0]):
        if sombre and debut is None:
            debut = x
        elif not sombre and debut is not None:
            if x - debut >= longueur:
                positions.update(range(debut, x))
            debut = None
    return positions


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
    elif _GABARIT.search(texte) and part_hors_texte(page) >= SEUIL_MIXTE:
        type_page = MIXTE
    elif mots >= MOTS_MIN and q >= SEUIL_QUALITE:
        type_page = DACTYLOGRAPHIEE
    else:
        type_page = MANUSCRITE
    return Typage(type_page, e, q, mots, intercalaire or garde)
