"""Pages tournées, sur des pages construites pour le test (aucun cahier)."""

import pymupdf
import pytest

from orientation.orientation import pages_tournees, rapport, rapport_brut, tournee
from typage.typage import _zone

PARAGRAPHE = (
    "Nous demandons le retour des services publics dans les petites communes, "
    "une meilleure desserte des transports et une fiscalité plus juste. "
) * 12


@pytest.fixture
def doc():
    with pymupdf.open() as d:
        yield d


def page_texte(doc, rotation):
    page = doc.new_page()
    page.insert_textbox(
        pymupdf.Rect(60, 80, 540, 780), PARAGRAPHE, fontsize=11, rotate=rotation
    )
    return page


def test_page_droite(doc):
    assert not tournee(page_texte(doc, 0))


@pytest.mark.parametrize("rotation", [90, 270])
def test_page_tournee_d_un_quart_de_tour(doc, rotation):
    assert tournee(page_texte(doc, rotation))


def test_ombre_de_reliure_masquee(doc):
    # page droite, bande sombre verticale sur une partie de la hauteur
    page = doc.new_page()
    page.insert_textbox(pymupdf.Rect(150, 80, 540, 780), PARAGRAPHE, fontsize=11)
    page.draw_rect(pymupdf.Rect(70, 100, 120, 400), color=(0, 0, 0), fill=(0, 0, 0))
    assert rapport_brut(_zone(page)[3]) < 0.6
    assert not tournee(page)


def test_page_vierge(doc):
    assert rapport(doc.new_page()) is None


def test_pages_tournees_d_un_fichier(tmp_path, doc):
    for rotation in (0, 90, 90, 0):
        page_texte(doc, rotation)
    doc.new_page()
    chemin = tmp_path / "CC_01800_190301_01450_MD_1.pdf"
    doc.save(chemin)
    assert pages_tournees(chemin) == ("CC_01800_190301_01450_MD_1.pdf", 5, [2, 3])
