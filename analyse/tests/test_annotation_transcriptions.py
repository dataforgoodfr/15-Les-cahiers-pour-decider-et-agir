"""Transcrire un étalon HTR dans l'outil d'annotation : liste et export."""

import pytest

from annotation import listes
from annotation.carnet import Carnet
from annotation.transcriptions import ecrire_liste, exporter, pages_de_l_etalon


@pytest.fixture
def etalon(tmp_path):
    pages = tmp_path / "etalon" / "pages"
    pages.mkdir(parents=True)
    for nom in ("CC_b_p3", "CC_a_p12", "CC_a_p2", "sans-numero"):
        (pages / f"{nom}.jpg").write_bytes(b"")
    (pages / "CC_a_p2.autre.txt").write_text("lecture d'un autre\n")
    return tmp_path / "etalon"


def test_pages_de_l_etalon(etalon):
    assert pages_de_l_etalon(etalon) == [
        ("CC_a.pdf", 2, "CC_a_p2"),
        ("CC_a.pdf", 12, "CC_a_p12"),
        ("CC_b.pdf", 3, "CC_b_p3"),
    ]


def test_ecrire_liste(etalon, tmp_path):
    assert ecrire_liste(etalon, tmp_path / "annotation", "transcription-essai") == 3
    liste = listes.lire(tmp_path / "annotation" / "listes", "transcription-essai")
    assert liste["mode"] == "transcrire" and liste["tache"] == "transcription"
    assert liste["elements"][0] == {"fichier": "CC_a.pdf", "page": 2}


def test_exporter(etalon, tmp_path):
    carnet = Carnet(tmp_path / "notes.jsonl")
    carnet.transcrire("CC_a.pdf", 2, "Ma lecture")
    carnet.transcrire("CC_a.pdf", 12, "Ma lecture\n")
    carnet.transcrire("CC_b.pdf", 3, "   ")  # rien d'écrit : sautée
    carnet.transcrire("CC_c.pdf", 1, "hors de l'étalon")
    (etalon / "pages" / "CC_a_p2.hugo.txt").write_text("ancienne\n")
    assert exporter(etalon, carnet, "hugo") == (1, 1)
    assert (etalon / "pages" / "CC_a_p12.hugo.txt").read_text() == "Ma lecture\n"
    assert (etalon / "pages" / "CC_a_p2.hugo.txt").read_text() == "ancienne\n"
    assert not (etalon / "pages" / "CC_b_p3.hugo.txt").exists()
    assert exporter(etalon, carnet, "hugo", remplacer=True) == (2, 0)
    assert (etalon / "pages" / "CC_a_p2.hugo.txt").read_text() == "Ma lecture\n"
    with pytest.raises(ValueError):
        exporter(etalon, carnet, "../hugo")
