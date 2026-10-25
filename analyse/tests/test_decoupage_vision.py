"""Le banc de découpage par un modèle de vision, sur des pages construites pour le test."""

import pymupdf
import pytest

from decoupage.vision.__main__ import haut, lire_sorties, lots, mesure, vers_affichage


def test_lots_range_les_gros_cahiers_d_abord():
    assert lots([("a", 30), ("b", 20), ("c", 20), ("d", 10)], taille=45) == [
        ["a", "d"],
        ["b", "c"],
    ]
    # un cahier plus gros qu'un lot en forme un à lui seul
    assert lots([("gros", 60), ("petit", 5)], taille=45) == [["gros"], ["petit"]]


@pytest.mark.parametrize(
    ("rotation", "attendu"), [(0, 100), (90, 50), (180, 742), (270, 495)]
)
def test_le_haut_d_une_note_suit_la_rotation_de_l_affichage(rotation, attendu):
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    matrice = vers_affichage(page, rotation)
    # une note de (50, 100) à (100, 100), dans le repère de la page non tournée
    assert haut(pymupdf.Rect(50, 100, 100, 100), matrice) == pytest.approx(attendu)


def test_lire_sorties(tmp_path):
    (tmp_path / "1").mkdir()
    (tmp_path / "1" / "CC_A.txt").write_text(
        "001_p1.jpg : aucun\n002_p3.jpg : 10, 50\n003_p4.jpg : [IMAGE NON VUE]\n"
        "004_p9.jpg : 20\nune remarque\n",
        encoding="utf-8",
    )
    hauteurs = {("CC_A.pdf", 1): 800, ("CC_A.pdf", 3): 800, ("CC_A.pdf", 4): 800}
    debuts, vues, non_vues = lire_sorties(tmp_path, hauteurs)
    assert debuts == [("CC_A.pdf", 3, 80.0), ("CC_A.pdf", 3, 400.0)]
    assert vues == {("CC_A.pdf", 1), ("CC_A.pdf", 3)}
    assert non_vues == 1


def test_mesure_a_la_page():
    reference = [("f", 1, 100.0), ("f", 2, 100.0)]
    m = mesure(
        [("f", 1, 110.0), ("f", 3, 50.0)], reference, {("f", 1), ("f", 2), ("f", 3)}
    )
    assert (m["precision"], m["rappel"]) == (0.5, 0.5)
    assert (m["precision_page"], m["rappel_page"]) == (0.5, 0.5)


def test_graduations_de_la_reponse():
    from decoupage.vision.__main__ import graduations

    assert graduations('<think>…</think>{"debuts": [58, 12]}') == [12.0, 58.0]
    assert graduations('Voici : {"debuts": []}') == []
    # hors de la règle : ignoré
    assert graduations('{"debuts": [120, -3, 40]}') == [40.0]
    with pytest.raises(ValueError):
        graduations("aucun début")


def test_la_consigne_par_page_reprend_la_definition():
    from decoupage.vision.__main__ import CONSIGNE, CONSIGNE_PAGE, DEFINITION

    assert DEFINITION.startswith("Une contribution est")
    assert "plusieurs personnes écrivent" in DEFINITION
    assert DEFINITION in CONSIGNE
    assert DEFINITION in CONSIGNE_PAGE.format(contexte="")
