"""Erreurs de l'OCR contre une transcription, sur des textes construits pour le test."""

import pytest

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
