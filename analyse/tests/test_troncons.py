"""Tronçons de test du découpage, sur des cahiers construits pour le test."""

import random

from decoupage.troncons.troncons import tirer

D, M = "dactylographiée", "manuscrite"


def cahier(departement, types):
    return {"departement": departement, "pages": list(enumerate(types, start=1))}


def test_un_troncon_par_departement_non_couvert():
    cahiers = {
        "a.pdf": cahier("01", [D] * 30),
        "b.pdf": cahier("02", [M, D, M]),
        "c.pdf": cahier("03", [D] * 5),
        "d.pdf": cahier("04", [M] * 12),
    }
    troncons = tirer(cahiers, {"03"}, random.Random(1), longueur=10)
    assert [t["departement"] for t in troncons] == ["01", "02"]
    a, b = troncons
    assert a["pages"] == 10 and a["derniere"] - a["premiere"] == 9
    assert (b["premiere"], b["derniere"], b["dactylographiees"]) == (1, 3, 1)


def test_le_troncon_recule_en_fin_de_cahier():
    cahiers = {"a.pdf": cahier("01", [M] * 9 + [D])}
    (t,) = tirer(cahiers, set(), random.Random(0), longueur=4)
    assert (t["premiere"], t["derniere"]) == (7, 10)


def test_une_page_dactylographiee_au_hasard_du_departement():
    cahiers = {"a.pdf": cahier("01", [D] * 9), "b.pdf": cahier("01", [D])}
    tires = [
        tirer(cahiers, set(), random.Random(k), longueur=1)[0]["fichier"]
        for k in range(1000)
    ]
    assert 50 < tires.count("b.pdf") < 150
    assert (
        tirer(cahiers, set(), random.Random(0))[0]["dactylographiees_departement"] == 10
    )
