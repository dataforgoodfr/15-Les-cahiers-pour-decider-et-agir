"""Masques des Archives de l'Aude, sur des images construites pour le test (aucun cahier)."""

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from aude.masques import _composer, masques, recaler, reporter


def papier(graine: int = 0) -> np.ndarray:
    """Une feuille blanc cassé, avec le grain du scan."""
    hasard = np.random.default_rng(graine)
    return np.clip(hasard.normal(238, 6, (1400, 1000)), 0, 255).astype(np.uint8)


def test_rectangle_gris_uniforme_repere():
    a = papier()
    a[900:960, 300:620] = 236
    assert masques(a) == [(300, 900, 320, 60)]


def test_papier_seul_sans_masque():
    assert masques(papier()) == []


def test_carreaux_d_un_papier_quadrille_ignores():
    a = np.full((1400, 1000), 236, np.uint8)
    a[::24, :] = 120  # lignes du quadrillage, tous les 5 mm environ
    a[:, ::24] = 120
    assert masques(a) == []


def test_encre_sombre_ignoree():
    a = papier()
    a[100:200, 100:400] = 30  # un aplat noir : un tampon, pas un masque
    assert masques(a) == []


def test_report_par_la_similitude_puis_vers_la_page():
    # image publiée -> image BnF : moitié de taille, décalée de (10, 20)
    similitude = np.array([[0.5, 0, 10], [0, 0.5, 20]])
    # image BnF -> page PDF : facteur 0,6
    vers_page = np.array([[0.6, 0, 0], [0, 0.6, 0]])
    t = _composer(similitude, vers_page)
    assert reporter((100, 200, 40, 20), t) == (36.0, 72.0, 48.0, 78.0)


def test_report_d_un_rectangle_tourne():
    quart_de_tour = np.array([[0, -1, 100], [1, 0, 0]])
    identite = np.array([[1, 0, 0], [0, 1, 0]])
    x0, y0, x1, y1 = reporter((10, 20, 30, 10), _composer(quart_de_tour, identite))
    assert (x0, y0, x1, y1) == (70.0, 10.0, 80.0, 40.0)


def test_recalage_d_un_decalage_local():
    hasard = np.random.default_rng(3)
    publiee = np.full((300, 300), 240, np.uint8)
    for _ in range(300):  # des traits d'encre autour du masque
        x, y = hasard.integers(20, 280, 2)
        cv2.line(publiee, (int(x), int(y)), (int(x) + 8, int(y) + 3), 40, 2)
    publiee[120:160, 100:200] = 236  # le masque
    # sur la page ramenée, le contenu est 2 pixels plus à droite, 4 plus haut
    ramenee = np.roll(publiee, (-4, 2), axis=(0, 1))
    hors = np.ones(publiee.shape, bool)
    hors[120:160, 100:200] = False
    dx, dy, accord = recaler(publiee, ramenee, (100, 120, 100, 40), hors)
    assert (dx, dy) == (-2, 4)
    assert accord > 0.9


def test_pas_de_recalage_sur_un_entourage_blanc():
    publiee = np.full((300, 300), 250, np.uint8)
    publiee[120:160, 100:200] = 236
    hors = np.ones(publiee.shape, bool)
    hors[120:160, 100:200] = False
    assert recaler(publiee, publiee, (100, 120, 100, 40), hors) == (0, 0, None)
