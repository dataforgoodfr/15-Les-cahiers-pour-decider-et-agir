"""Toutes les contributions d'un cahier, ramenées au repère du PDF."""

from delimitation.__main__ import lignes_du_cahier
from selection.contribution import Sens, en_colonnes, toutes, vers_pdf


def test_vers_pdf_defait_la_rotation_et_les_colonnes():
    sens = Sens(90, 600.0, 800.0)  # lue en 800 × 600
    u, v = sens.vers_lecture(100.0, 200.0)
    assert vers_pdf(sens, v, u) == (100.0, 200.0)
    # page de droite d'une double page : lue une hauteur plus bas
    double = Sens(0, 1200.0, 800.0)
    point = en_colonnes((1, 50.0, 700.0), 600.0, 800.0)
    assert vers_pdf(double, point[1], point[2]) == (700.0, 50.0)


def test_toutes_les_contributions_dans_l_ordre():
    debuts = [(2, 30.0, 10.0), (1, 100.0, 10.0), (1, 400.0, 10.0)]
    fins = [(1, 300.0, 500.0)]
    rangs = [(c.rang, c.page_debut, c.fin_notee) for c in toutes(debuts, fins, 4)]
    assert rangs == [(1, 1, True), (2, 1, False), (3, 2, False)]


def test_lignes_du_cahier_fins_et_publiable():
    sens = {n: Sens(0, 600.0, 800.0) for n in (1, 2, 3)}
    debuts = [(1, 100.0, 50.0), (1, 400.0, 60.0), (2, 30.0, 70.0)]
    fins = [(1, 300.0, 500.0)]
    qualifications = {("a.pdf", 3): {"problemes": {"à écarter": True}}}
    lignes = lignes_du_cahier("a.pdf", sens, debuts, fins, qualifications)
    assert [x["fin"] for x in lignes] == ["notée", "début suivant", "fin du cahier"]
    assert (lignes[0]["x_fin"], lignes[0]["y_fin"]) == (500.0, 300.0)
    # fin déduite : le point du début suivant
    assert (lignes[1]["page_fin"], lignes[1]["x_fin"], lignes[1]["y_fin"]) == (
        2,
        70.0,
        30.0,
    )
    assert (lignes[2]["page_fin"], lignes[2]["y_fin"]) == (3, "")
    assert [x["publiable"] for x in lignes] == [1, 1, 0]
