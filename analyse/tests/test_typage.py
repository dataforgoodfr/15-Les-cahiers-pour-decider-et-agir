"""Typage des pages, sur des pages construites pour le test (aucun cahier)."""

import pymupdf
import pytest

from typage.typage import (
    DACTYLOGRAPHIEE,
    MANUSCRITE,
    MIXTE,
    VIERGE,
    qualite,
    typer,
)

PARAGRAPHE = (
    "Nous demandons le retour des services publics dans les petites communes, "
    "une meilleure desserte des transports et une fiscalité plus juste pour "
    "les familles qui travaillent et vivent loin des villes."
)


@pytest.fixture
def doc():
    with pymupdf.open() as d:
        yield d


def page_texte(doc, texte, taille=14):
    page = doc.new_page()
    page.insert_textbox(pymupdf.Rect(60, 80, 540, 780), texte, fontsize=taille)
    return page


def test_page_blanche_est_vierge(doc):
    assert typer(doc.new_page()).type_page == VIERGE


def test_bord_de_scan_noir_ne_rend_pas_la_page_encree(doc):
    page = doc.new_page()
    page.draw_rect(pymupdf.Rect(0, 0, 20, page.rect.height), fill=(0, 0, 0))
    assert typer(page).type_page == VIERGE


def test_trait_vertical_dans_la_page_n_est_pas_de_l_encre(doc):
    page = doc.new_page()
    page.draw_rect(pymupdf.Rect(120, 0, 135, page.rect.height), fill=(0, 0, 0))
    page.draw_rect(pymupdf.Rect(0, 400, page.rect.width, 408), fill=(0, 0, 0))
    assert typer(page).type_page == VIERGE


def test_trait_au_bord_de_la_zone_mesuree(doc):
    page = doc.new_page()
    # juste à l'intérieur de la marge de droite : le voisinage déborde la zone
    x = page.rect.width * 0.915
    page.draw_rect(pymupdf.Rect(x, 0, x + 4, page.rect.height), fill=(0, 0, 0))
    assert typer(page).type_page == VIERGE


def test_texte_francais_est_dactylographie(doc):
    t = typer(page_texte(doc, PARAGRAPHE * 3))
    assert t.type_page == DACTYLOGRAPHIEE
    assert t.qualite > 0.8
    assert not t.page_de_service


def ecriture(page, lignes, x=80, y=100, pas=16):
    """Des zigzags, comme une écriture à la main, sans couche texte."""
    for i in range(lignes):
        page.draw_polyline(
            [(x + k * 12, y + i * pas + (4 if k % 2 else -4)) for k in range(36)],
            width=1.5,
        )


def formulaire(doc):
    """Un gabarit imprimé : intitulés et lignes de champ.

    Les lignes couvrent moins de la moitié de la page : ce ne sont pas des traits.
    """
    page = doc.new_page()
    intitules = [
        "Cahier de doléances à l'attention des pouvoirs publics",
        "Demande :",
        "Propose :",
        "Souhaite que soient traités, par ordre de priorité, les problèmes suivants :",
    ]
    for i, intitule in enumerate(intitules):
        page.insert_text((60, 90 + i * 190), intitule, fontsize=12)
        for k in range(1, 6):
            y = 90 + i * 190 + k * 30
            page.draw_line((70, y), (270, y), width=3)
    return page


def test_encre_sans_couche_texte_est_manuscrite(doc):
    page = doc.new_page()
    ecriture(page, 40)
    assert typer(page).type_page == MANUSCRITE


def test_formulaire_rempli_a_la_main_est_mixte(doc):
    page = formulaire(doc)
    for i in range(3):
        ecriture(page, 4, y=110 + i * 190, pas=30)
    assert typer(page).type_page == MIXTE


def test_formulaire_vide_n_est_pas_mixte(doc):
    assert typer(formulaire(doc)).type_page == DACTYLOGRAPHIEE


def test_couche_texte_illisible_est_manuscrite(doc):
    bruit = "rjx'v qzhk ,lmwp tbnd vvqx hjkr zzpl wqxm " * 30
    assert typer(page_texte(doc, bruit)).type_page == MANUSCRITE


def test_intercalaire_est_une_page_vierge_de_service(doc):
    t = typer(page_texte(doc, "Fin des pages écrites", taille=40))
    assert t.encre > 0.003
    assert (t.type_page, t.page_de_service) == (VIERGE, True)


def test_page_de_garde_garde_son_type(doc):
    garde = "Le grand débat national\nCahier citoyen\nAmbérieu-en-Bugey - 01004\n01500"
    t = typer(page_texte(doc, garde, taille=28))
    assert t.page_de_service
    assert t.type_page == DACTYLOGRAPHIEE


def test_qualite_ignore_mots_courts_et_ponctuation():
    assert qualite("le la de, les maisons !") == (1.0, 2)
    assert qualite("") == (0.0, 0)
