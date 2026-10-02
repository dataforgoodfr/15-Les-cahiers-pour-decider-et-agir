"""Pages numérisées de travers : contenu tourné d'un quart de tour (issue #43).

Un formulaire en paysage ou un cahier à spirale numérisé en portrait donne une
page dont les lignes d'écriture sont verticales. L'OCR du versement les lit
alors comme du bruit : la couche texte ne dit rien de l'orientation, et le
typage (#17) prend une page dactylographiée tournée pour une page manuscrite.

On lit donc l'image, rendue à 50 dpi comme pour le typage, bords de scan
exclus. Des lignes d'écriture horizontales font alterner les rangées de
pixels, encrées puis vides (l'interligne) ; leurs colonnes, elles, sont
encrées de façon à peu près régulière. On compare la variation des deux
profils (coefficient de variation de l'encre par rangée et par colonne) : un
rapport sous 0,6 signale une page tournée.

Les photocopies de cahiers débordent de la page : ombre de la reliure,
couverture vue de l'intérieur, page opposée, bandes tramées ajoutées à la
numérisation. Ces zones sombres, verticales, font croire à des lignes
d'écriture verticales. On les masque avant de mesurer : les blocs de 3 mm
encrés à plus de moitié (une écriture, même serrée, l'est moins) et les
traits fins de plus de 2 cm (réglure, bords de feuille). Ce masque coûte
cher ; on ne l'applique qu'aux pages dont le rapport brut est déjà bas.

Les pages tournées venant en série, un fichier qui en compte plusieurs est un
signal plus sûr qu'une page isolée. Restent signalées à tort quelques pages
presque vierges et des feuilles collées de travers ; restent manquées des
pages tournées à gros logo. Un demi-tour (page à l'envers) n'est pas détecté.
"""

import re
import statistics

import pymupdf

from typage.typage import _hors_traits, _zone

SEUIL_TOURNEE = 0.6
SEUIL_BRUT = 1.0  # au-dessus, la page est droite sans masquer les zones sombres
LISSAGE = 2  # pixels de part et d'autre : gomme le grain des lettres
PROFIL_MIN = 10  # rangées ou colonnes encrées sous lesquelles on ne juge pas
BLOC = 6  # pixels, 3 mm à 50 dpi
DENSITE_MAX = 0.5  # part encrée au-delà de laquelle un bloc n'est pas de l'écriture
_TRAIT = re.compile(rb"\x01{40,}")  # 2 cm à 50 dpi
EPAISSEUR_TRAIT = 3  # pixels : au-delà, c'est une ligne de texte


def _lisser(profil: list[int]) -> list[float]:
    return [
        statistics.fmean(profil[max(0, i - LISSAGE) : i + LISSAGE + 1])
        for i in range(len(profil))
    ]


def variation(profil: list[int]) -> float:
    """Coefficient de variation du profil lissé, sur l'étendue de l'encre."""
    encrees = [i for i, v in enumerate(profil) if v]
    if len(encrees) < PROFIL_MIN:
        return 0.0
    lisse = _lisser(profil[encrees[0] : encrees[-1] + 1])
    moyenne = statistics.fmean(lisse)
    return statistics.pstdev(lisse) / moyenne if moyenne else 0.0


def _rapport(rangees: list[int], colonnes: list[int]) -> float | None:
    par_rangee, par_colonne = variation(rangees), variation(colonnes)
    if not par_rangee or not par_colonne:
        return None
    return par_rangee / par_colonne


def rapport_brut(lignes: list[bytes]) -> float | None:
    """Variation par rangée sur variation par colonne ; None sans encre."""
    gardees, traits = _hors_traits(lignes)
    gardees = [ligne for _, ligne in gardees]
    if not gardees:
        return None
    rangees = [ligne.count(1) - sum(ligne[x] for x in traits) for ligne in gardees]
    colonnes = [0 if x in traits else sum(c) for x, c in enumerate(zip(*gardees))]
    return _rapport(rangees, colonnes)


def _sans_zones_denses(lignes: list[bytes]) -> list[bytearray]:
    """Les lignes de pixels, blocs encrés à plus de DENSITE_MAX effacés."""
    masque = [bytearray(ligne) for ligne in lignes]
    hauteur, largeur = len(lignes), len(lignes[0])
    for y0 in range(0, hauteur, BLOC):
        rangs = range(y0, min(y0 + BLOC, hauteur))
        for x0 in range(0, largeur, BLOC):
            x1 = min(x0 + BLOC, largeur)
            encre = sum(lignes[y][x0:x1].count(1) for y in rangs)
            if encre > DENSITE_MAX * len(rangs) * (x1 - x0):
                for y in rangs:
                    masque[y][x0:x1] = bytes(x1 - x0)
    return masque


def _sans_traits_fins(lignes: list[bytearray]) -> list[bytearray]:
    """Efface les traits longs et fins : rien à EPAISSEUR_TRAIT de part et d'autre."""
    resultat = [bytearray(ligne) for ligne in lignes]
    for y, ligne in enumerate(lignes):
        for m in _TRAIT.finditer(ligne):
            a, b = m.span()
            voisines = [
                lignes[v][a:b].count(1)
                for v in (y - EPAISSEUR_TRAIT, y + EPAISSEUR_TRAIT)
                if 0 <= v < len(lignes)
            ]
            if all(n < (b - a) / 4 for n in voisines):
                resultat[y][a:b] = bytes(b - a)
    return resultat


def _transposer(lignes: list[bytearray]) -> list[bytearray]:
    return [bytearray(colonne) for colonne in zip(*lignes)]


def rapport(page: pymupdf.Page) -> float | None:
    """Rapport des variations, zones sombres masquées si la page semble tournée."""
    _, _, _, lignes = _zone(page)
    brut = rapport_brut(lignes)
    if brut is None or brut >= SEUIL_BRUT:
        return brut
    masque = _sans_traits_fins(_sans_zones_denses(lignes))
    masque = _transposer(_sans_traits_fins(_transposer(masque)))
    return _rapport(
        [ligne.count(1) for ligne in masque], [sum(c) for c in zip(*masque)]
    )


def tournee(page: pymupdf.Page) -> bool:
    r = rapport(page)
    return r is not None and r < SEUIL_TOURNEE


def pages_tournees(chemin) -> tuple[str, int, list[int]]:
    """Nom du fichier, nombre de pages et pages tournées."""
    with pymupdf.open(chemin) as doc:
        tournees = [numero for numero, page in enumerate(doc, start=1) if tournee(page)]
        return chemin.name, doc.page_count, tournees
