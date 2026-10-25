"""Rapprochement des pages de l'Aude, sur des images construites pour le test (aucun cahier)."""

import numpy as np
import pymupdf
import pytest

cv2 = pytest.importorskip("cv2")

from anonymisation.aude.__main__ import _plages, commune
from anonymisation.aude.rapprochement import (
    SEUIL,
    Index,
    Rapprochement,
    descripteurs,
    image_publiee,
    nature,
    points_communs,
)

LETTRES = "abcdefghijklmnopqrstuvwxyz"


def feuille(graine: int) -> np.ndarray:
    """Une page de faux texte : des lettres au hasard, de taille variable."""
    hasard = np.random.default_rng(graine)
    a = np.full((1400, 1000), 255, np.uint8)
    for y in range(80, 1350, 45):
        x = 60
        while x < 850:
            mot = "".join(hasard.choice(list(LETTRES), hasard.integers(3, 9)))
            taille = hasard.uniform(0.7, 1.1)
            cv2.putText(
                a,
                mot,
                (x, y + int(hasard.integers(-4, 5))),
                cv2.FONT_HERSHEY_SCRIPT_SIMPLEX,
                taille,
                0,
                2,
            )
            x += int(22 * taille * len(mot)) + int(hasard.integers(10, 40))
    return a


def publiee(a: np.ndarray) -> np.ndarray:
    """Ce qu'en fait le CESE : recadrée, agrandie, contrastée, un nom masqué."""
    b = a[60:1300, 40:960]
    b = cv2.resize(b, None, fx=1.4, fy=1.4)
    b = np.clip((b.astype(float) - 30) * 1.3, 0, 255).astype(np.uint8)
    b[200:260, 300:600] = 160
    return b


def test_meme_page_retrouvee_malgre_recadrage_et_masque():
    a = feuille(1)
    assert points_communs(descripteurs(a), descripteurs(publiee(a))) >= SEUIL


def test_pages_differentes_ecartees():
    assert points_communs(descripteurs(feuille(1)), descripteurs(feuille(2))) < SEUIL


def test_index_choisit_la_bonne_page():
    bnf = [descripteurs(feuille(g)) for g in range(4)]
    r = Index(bnf, ["a", "b", "c", "d"]).rapprocher(descripteurs(publiee(feuille(2))))
    assert r.page == 2
    assert r.score >= SEUIL > r.autre_commune
    assert not r.douteuse


def test_page_absente_du_versement():
    bnf = [descripteurs(feuille(g)) for g in range(3)]
    assert Index(bnf, ["a", "b", "c"]).rapprocher(descripteurs(feuille(9))).page is None


def test_cahier_depose_deux_fois_dans_le_versement():
    # pages 0 et 2 : la même commune ; page 1 : une autre
    r = Rapprochement.depuis([(700, 0), (690, 2), (40, 1)], ["a", "b", "a"])
    assert (r.page, r.doublons, r.autre_commune, r.douteuse) == (0, [2], 40, False)


def test_imprime_type_d_une_autre_commune_douteux():
    r = Rapprochement.depuis([(400, 0), (300, 1)], ["a", "b"])
    assert r.page == 0 and r.douteuse


def test_sous_le_seuil():
    r = Rapprochement.depuis([(SEUIL - 1, 0)], ["a"])
    assert r.page is None and r.score == SEUIL - 1


@pytest.fixture
def doc():
    with pymupdf.open() as d:
        yield d


def test_nature_et_image_d_une_page_du_cese(doc):
    texte = doc.new_page()
    texte.insert_textbox(pymupdf.Rect(60, 80, 540, 780), "Le CESE de l'Aude. " * 20)
    assert nature(texte) == "cese"

    scan = doc.new_page()
    png = cv2.imencode(".png", feuille(3))[1].tobytes()
    scan.insert_image(pymupdf.Rect(100, 100, 450, 590), stream=png)
    scan.insert_text((290, 820), "12")  # numéro de page, hors de l'image
    assert nature(scan) == "scan"
    image = image_publiee(scan)
    assert image.shape[1] == 1000
    # l'image seule, recadrée sur son encre : le numéro de page, 230 points
    # plus bas, porterait le rapport hauteur sur largeur au-delà de 2
    assert 1.3 < image.shape[0] / image.shape[1] < 1.6


def test_commune_et_plages():
    assert commune("CC_11800_190225_11397_MD_01922.pdf") == "11397"
    concatenes = {"CC_11240_190322_11004_MD_18436.pdf": [(17, "11390")]}
    assert commune("CC_11240_190322_11004_MD_18436.pdf", 16, concatenes) == "11004"
    assert commune("CC_11240_190322_11004_MD_18436.pdf", 17, concatenes) == "11390"
    assert _plages([3, 4, 5, 9, 11, 12]) == "3-5 9 11-12"
    assert _plages([]) == ""
