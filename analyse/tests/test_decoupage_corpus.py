"""Contributions d'un cahier découpé automatiquement, coupées au manuscrit."""

from decoupage.corpus.contributions import Debut, contributions

D, M, X = "dactylographiée", "manuscrite", "mixte"


def fins(debuts, ecrites):
    return [
        (c["page_fin"], c["y_fin"], c["fin"]) for c in contributions(debuts, ecrites)
    ]


def test_une_contribution_court_jusqu_au_debut_suivant():
    debuts = [Debut(1, 50, 100, "lettre"), Debut(3, 50, 400, "courriel")]
    assert fins(debuts, [(1, D), (2, X), (3, D)]) == [
        (3, 400, "début suivant"),
        (3, None, "fin du cahier"),
    ]


def test_une_contribution_s_arrete_avant_le_manuscrit():
    debuts = [Debut(1, 50, 100, "lettre"), Debut(4, 50, 100, "lettre")]
    assert fins(debuts, [(1, D), (2, D), (3, M), (4, D), (5, M)]) == [
        (2, None, "avant le manuscrit"),
        (4, None, "avant le manuscrit"),
    ]


def test_les_rangs_suivent_l_ordre_des_debuts():
    debuts = [Debut(2, 0, 10, "page"), Debut(2, 0, 300, "gabarit")]
    rangs = [c["rang"] for c in contributions(debuts, [(2, D)])]
    assert rangs == [1, 2]
