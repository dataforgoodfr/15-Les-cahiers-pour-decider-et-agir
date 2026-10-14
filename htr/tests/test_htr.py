import json

import pymupdf
import pytest

from htr import modeles
from htr.__main__ import chemins, pages_typees, scans_extraction
from htr.lecture import cadre, image, zoom


def page_avec_image(largeur_px: int, hauteur_px: int, rotation: int = 0):
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    pix = pymupdf.Pixmap(pymupdf.csGRAY, pymupdf.IRect(0, 0, largeur_px, hauteur_px), 0)
    pix.clear_with(255)
    page.insert_image(page.rect, pixmap=pix)
    page.set_rotation(rotation)
    return doc, page


def test_zoom_retrouve_la_resolution_du_scan():
    doc, page = page_avec_image(1240, 1754)
    assert zoom(page) == pytest.approx(1754 / 842)
    doc.close()


def test_zoom_sans_image():
    doc = pymupdf.open()
    assert zoom(doc.new_page()) == 2.0


def test_image_page_tournee_dans_le_sens_affiche():
    doc, page = page_avec_image(620, 877, rotation=90)
    im = image(page, 1.0)
    assert im.size == (842, 595)
    assert im.mode == "L"
    doc.close()


def test_cadre_en_points():
    assert cadre([(10, 20), (110, 25), (100, 60)], 2.0) == [5.0, 10.0, 55.0, 30.0]


def test_pages_typees(tmp_path):
    (tmp_path / "d.csv").write_text(
        "fichier,page,type_page\n"
        "a.pdf,2,manuscrite\na.pdf,1,manuscrite\na.pdf,3,vierge\nb.pdf,1,manuscrite\n",
        encoding="utf-8",
    )
    assert pages_typees(tmp_path, {"a.pdf"}, {"manuscrite"}) == {"a.pdf": [1, 2]}


def test_scans_extraction(tmp_path):
    chemin = tmp_path / "e.json"
    chemin.write_text(
        json.dumps(
            [None, {"pdf_files": ["x/b.pdf", "y/a.pdf"]}, {"pdf_files": ["b.pdf"]}]
        ),
        encoding="utf-8",
    )
    assert scans_extraction(chemin) == ["a.pdf", "b.pdf"]


def test_chemins_suit_les_liens(tmp_path):
    (tmp_path / "vrai").mkdir()
    (tmp_path / "vrai" / "a.pdf").write_bytes(b"")
    (tmp_path / "versement").mkdir()
    (tmp_path / "versement" / "lien").symlink_to(tmp_path / "vrai")
    assert chemins(tmp_path / "versement") == {
        "a.pdf": tmp_path / "versement/lien/a.pdf"
    }


def test_modele_refuse_une_somme_inattendue(tmp_path, monkeypatch):
    monkeypatch.setitem(modeles.MODELES, "essai", ("m.mlmodel", "inutile", "0" * 32))
    (tmp_path / "m.mlmodel").write_bytes(b"pas le bon")
    with pytest.raises(ValueError):
        modeles.modele("essai", tmp_path)


def test_modele_deja_present(tmp_path, monkeypatch):
    (tmp_path / "m.mlmodel").write_bytes(b"contenu")
    somme = modeles.md5(tmp_path / "m.mlmodel")
    monkeypatch.setitem(modeles.MODELES, "essai", ("m.mlmodel", "inutile", somme))
    assert modeles.modele("essai", tmp_path) == tmp_path / "m.mlmodel"
