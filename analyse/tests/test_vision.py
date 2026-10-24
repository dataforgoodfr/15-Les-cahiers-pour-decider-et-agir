"""Boîtes d'un modèle de vision, sur des réponses et des pages construites pour le test."""

import numpy as np
import pytest

from anonymisation.vision import (
    FACTICES,
    boites,
    mesurer_page,
    page_factice,
    recouvrement,
)


def test_boites_dans_les_deux_formes():
    xyxy = '```json\n[{"bbox_2d": [100, 200, 300, 250], "label": "name"}]\n```'
    yxyx = '<think>…</think>[{"box_2d": [200, 100, 250, 300], "label": "phone"}]'
    a = boites(xyxy, "xyxy", 595, 842)[0]
    b = boites(yxyx, "yxyx", 595, 842)[0]
    assert a["x0"] == b["x0"] == pytest.approx(59.5)
    assert a["y1"] == b["y1"] == pytest.approx(210.5)
    assert (a["etiquette"], b["etiquette"]) == ("name", "phone")


def test_boites_mal_formees_ignorees():
    reponse = (
        '[{"bbox_2d": [1, 2, 3]}, {"bbox_2d": ["a", 1, 2, 3]}, "texte", '
        '{"bbox_2d": [10, 10, 0, 0], "label": "inconnue", "text": "Dupont"}]'
    )
    (b,) = boites(reponse, "xyxy", 1000, 1000)
    assert (b["x0"], b["x1"], b["etiquette"]) == (0, 10, "other")
    assert "text" not in b
    assert boites("[]", "xyxy", 1000, 1000) == []
    with pytest.raises(ValueError):
        boites("aucune donnée", "xyxy", 1000, 1000)


def test_recouvrement():
    a = {"x0": 0, "y0": 0, "x1": 10, "y1": 10}
    assert recouvrement(a, a) == 1
    assert recouvrement(a, {"x0": 5, "y0": 0, "x1": 15, "y1": 10}) == pytest.approx(
        1 / 3
    )
    assert recouvrement(a, {"x0": 20, "y0": 20, "x1": 30, "y1": 30}) == 0


def test_mesurer_page_a_l_encre():
    gris = np.full((100, 100), 255, np.uint8)
    gris[10:20, 10:50] = 0  # une signature, sous un masque
    gris[60:70, 10:90] = 0  # le corps du texte
    masque = {"x0": 5, "y0": 5, "x1": 55, "y1": 25}
    juste = {"x0": 10, "y0": 10, "x1": 45, "y1": 20}  # 90 % de l'encre
    r = mesurer_page(gris, [masque], [juste])
    assert (r["masques"], r["couverts"], r["encre_cachee"]) == (1, 1, 0)
    r = mesurer_page(gris, [masque], [{"x0": 10, "y0": 60, "x1": 90, "y1": 70}])
    assert r["couverts"] == 0 and r["encre_cachee"] == r["encre"]


def test_page_factice():
    page = page_factice()[0]
    assert len(page.get_text("words")) > 50
    assert all(page.rect.contains((x0, y0)) for _, _, (x0, y0, _, _) in FACTICES)
