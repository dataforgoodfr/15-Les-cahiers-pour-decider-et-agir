"""Contribution tirée d'après les débuts notés, et ce qui l'entoure."""

import pytest

from selection.contribution import MARGE, Sens, doublons, hors_contribution, tiree


def test_tiree_prend_le_rang_de_la_position():
    debuts = [(3, 50.0, 0.0), (1, 100.0, 0.0), (1, 400.0, 0.0), (5, 20.0, 0.0)]
    t = tiree(0.6, debuts, [], derniere_page=8)
    # 0,6 × 4 = 2,4 → 3e début dans l'ordre de lecture
    assert (t.rang, t.n, t.page_debut, t.y_debut) == (3, 4, 3, 50.0)
    # sans fin notée : jusqu'au début suivant
    assert (t.page_fin, t.y_fin, t.fin_notee) == (5, 20.0, False)
    assert t.pages == [3, 4, 5]


def test_tiree_s_arrete_a_sa_fin_notee():
    debuts = [(1, 100.0, 0.0), (4, 80.0, 0.0)]
    t = tiree(0.1, debuts, [(2, 300.0, 0.0), (6, 10.0, 0.0)], 8)
    assert (t.rang, t.page_fin, t.y_fin, t.fin_notee) == (1, 2, 300.0, True)
    # une fin après le début suivant n'est pas la sienne
    t = tiree(0.1, debuts, [(6, 10.0, 0.0)], 8)
    assert (t.page_fin, t.fin_notee) == (4, False)


def test_la_derniere_contribution_va_jusqu_a_la_fin_du_cahier():
    debuts = [(1, 100.0, 0.0), (4, 80.0, 0.0)]
    t = tiree(1.0, debuts, [], 8)
    assert (t.rang, t.page_fin, t.y_fin) == (2, 8, None)
    assert tiree(0.5, [], [], 8) is None
    # une position nulle prend la première
    assert tiree(0.0, debuts, [], 8).rang == 1


def test_un_debut_pose_deux_fois_ne_compte_qu_une_fois():
    debuts = [
        (1, 50.0, 40.0),
        (2, 30.0, 40.0),
        (2, 800.0, 40.0),
        (2, 803.0, 42.0),
        (2, 805.0, 39.0),
        (3, 40.0, 40.0),
    ]
    t = tiree(0.5, debuts, [], 8)
    assert (t.rang, t.n, t.page_debut, t.y_debut) == (2, 4, 2, 30.0)
    # signalé une fois, à vérifier
    assert doublons(debuts)[1] == [(2, 800.0, 40.0)]


def test_les_cases_d_une_grille_ne_sont_pas_des_doublons():
    # même hauteur, cases voisines : trois contributions
    cases = [(19, 100.0, 40.0), (19, 104.0, 200.0), (19, 98.0, 360.0)]
    assert doublons(cases) == (sorted(cases), [])


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_sens_de_lecture_aller_retour(rotation):
    sens = Sens(rotation, 600.0, 800.0)
    u, v = sens.vers_lecture(100.0, 50.0)
    assert sens.vers_pdf(u, v) == (100.0, 50.0)
    largeur, hauteur = sens.dimensions
    assert 0 <= u <= largeur and 0 <= v <= hauteur


def test_une_page_tournee_se_lit_de_gauche_a_droite_du_pdf():
    # page numérisée couchée, lue après un quart de tour horaire : le haut de
    # la page lue est le bord gauche du PDF
    sens = Sens(90, 600.0, 800.0)
    gauche, droite = sens.vers_lecture(50.0, 400.0), sens.vers_lecture(500.0, 400.0)
    assert gauche[1] < droite[1]
    assert sens.dimensions == (800.0, 600.0)
    # le dessus de la page lue repart vers la gauche du PDF
    assert sens.cadre_pdf(0.0, 0.0, 800.0, 44.0) == (0.0, 0.0, 44.0, 800.0)


def test_hors_contribution_couvre_le_dessus_du_debut_et_le_dessous_de_la_fin():
    t = tiree(0.1, [(2, 100.0, 0.0), (3, 500.0, 0.0)], [(3, 200.0, 0.0)], 8)
    assert hors_contribution(t, 2, 600, 800) == [(0.0, 0.0, 600, 100.0 - MARGE)]
    # la fin notée garde sa ligne
    assert hors_contribution(t, 3, 600, 800) == [(0.0, 200.0 + MARGE, 600, 800)]
    # sans fin notée, le début suivant n'est pas gardé
    t = tiree(0.1, [(2, 100.0, 0.0), (2, 500.0, 0.0)], [], 8)
    assert hors_contribution(t, 2, 600, 800) == [
        (0.0, 0.0, 600, 100.0 - MARGE),
        (0.0, 500.0 - MARGE, 600, 800),
    ]
    # une contribution en haut de page, jusqu'à la fin du cahier : rien à couvrir
    t = tiree(1.0, [(2, 3.0, 0.0)], [], 8)
    assert hors_contribution(t, 2, 600, 800) == []
