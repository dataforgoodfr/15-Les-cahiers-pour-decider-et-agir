"""Erreurs de l'OCR contre une transcription, sur des textes construits pour le test."""

import pymupdf
import pytest

from ocr.anomalies import signaux
from ocr.chabin import distance_semi_globale, erreurs


def test_distance_semi_globale():
    assert distance_semi_globale(list("abc"), list("abcxyz")) == (0, 3)
    assert distance_semi_globale(list("kitten"), list("sitting")) == (2, 6)
    # à égalité, la fin la plus courte
    assert distance_semi_globale(["le", "chat"], ["le", "chien", "dort"]) == (1, 1)
    assert distance_semi_globale([], list("ab")) == (0, 0)


def test_erreurs_ignore_la_suite_de_l_ocr():
    e = erreurs("Le chat dort.", "le chat d0rt. Suite manuscrite illisible")
    assert e["cer brute"] == pytest.approx(2 / 13)
    assert e["cer normalisée"] == pytest.approx(1 / 12)
    assert e["wer normalisée"] == pytest.approx(1 / 3)
    assert (
        e["cer sans accents"]
        == erreurs("Le chât dort.", "le chat d0rt.")["cer sans accents"]
    )


def _page(*blocs):
    """Une page construite : des blocs de texte (texte, cadre)."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    for texte, cadre in blocs:
        page.insert_textbox(pymupdf.Rect(*cadre), texte, fontsize=11)
    return doc, page


LEXIQUE = {"la", "démocratie", "demande", "du", "temps", "les", "services", "publics"}


def test_deux_colonnes_ne_sont_pas_un_retour():
    _doc, page = _page(
        ("La démocratie demande du temps. " * 8, (50, 50, 280, 400)),
        ("Les services publics. " * 8, (310, 50, 540, 400)),
    )
    s = signaux(page, LEXIQUE)
    assert s["retours"] == 0 and s["encre_hors_mots"] < 0.05
    assert s["hors_lexique"] == 0 and s["mots_sans_encre"] == 0


def test_encre_non_lue_et_mots_abimes():
    _doc, page = _page(("La d0mocratie Ã©tait l1bre grumpf", (50, 50, 540, 100)))
    page.draw_rect(pymupdf.Rect(50, 300, 300, 400), color=(0, 0, 0), fill=(0, 0, 0))
    s = signaux(page, LEXIQUE)
    assert s["encre_hors_mots"] > 0.9  # le pavé noir n'est pas lu
    assert s["mal_encodes"] == 1 and s["chiffres_lettres"] > 0
    assert s["hors_lexique"] > 0


def test_mot_pose_sur_du_blanc():
    _doc, page = _page(("La démocratie demande du temps.", (50, 50, 540, 100)))
    # un mot invisible (couche texte seule), comme une couche décalée
    page.insert_text((50, 600), "services publics", fontsize=11, render_mode=3)
    assert signaux(page, LEXIQUE)["mots_sans_encre"] > 0.2
