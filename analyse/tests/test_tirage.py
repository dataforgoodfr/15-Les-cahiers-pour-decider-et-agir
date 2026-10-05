"""Tirage pour l'association, sur des communes construites pour le test."""

import random
from collections import defaultdict

from panel.panel import dans_panel
from tirage import profil
from tirage.tirage import (
    allouer,
    arrondir,
    caler,
    choisir_contributions,
    garantir,
    tirer_communes,
)


def test_allouer_aux_plus_forts_restes():
    assert allouer({"a": 0.5, "b": 0.3, "c": 0.2}, 10) == {"a": 5, "b": 3, "c": 2}
    assert allouer({"a": 1, "b": 1, "c": 1}, 10) == {"a": 4, "b": 3, "c": 3}
    assert sum(allouer({"a": 0.71, "b": 0.29}, 7).values()) == 7


def test_arrondir_tient_les_cases_et_les_deux_marges():
    rng = random.Random(4)
    for _ in range(50):
        cases = {(i, j): rng.random() ** 3 for i in range(7) for j in range(18)}
        cases[(0, 0)] = 0
        n = 100
        allocation = arrondir(cases, n)
        total = sum(cases.values())
        assert sum(allocation.values()) == n
        for c, k in allocation.items():
            assert abs(k - n * cases[c] / total) < 1
        for axe in (0, 1):
            exactes, tirees = defaultdict(float), defaultdict(int)
            for c, k in allocation.items():
                exactes[c[axe]] += n * cases[c] / total
                tirees[c[axe]] += k
            assert all(abs(tirees[m] - e) < 1 for m, e in exactes.items())
        assert allocation[(0, 0)] == 0


def test_garantir_une_unite_au_groupe():
    cases = {("t", "Paris"): 90, ("t", "Lyon"): 9, ("t", "Guyane"): 1}
    allocation = garantir(arrondir(cases, 10), cases, lambda c: c[1] == "Guyane")
    # Lyon (0,9) avait été arrondi au-dessus : c'est lui qui cède son unité
    assert allocation == {("t", "Paris"): 9, ("t", "Lyon"): 0, ("t", "Guyane"): 1}
    # déjà servi : rien ne bouge
    assert garantir(allocation, cases, lambda c: c[1] == "Guyane") == allocation


def test_caler_sur_deux_marges():
    communes = {
        "a": {"population": 10, "taille": "petite", "region": "nord"},
        "b": {"population": 10, "taille": "grande", "region": "nord"},
        "c": {"population": 10, "taille": "petite", "region": "sud"},
        "d": {"population": 70, "taille": "grande", "region": "sud"},
    }
    cibles = {
        "taille": {"petite": 40, "grande": 60},
        "region": {"nord": 50, "sud": 50, "absente": 10},
    }
    poids = caler(communes, cibles)
    assert abs(poids["a"] + poids["c"] - 0.4) < 1e-6
    assert abs(poids["a"] + poids["b"] - 0.5) < 1e-6


def test_tirer_communes_proportionnel_a_la_population():
    communes = [("grande", 900, ("t", "r1")), ("petite", 100, ("t", "r2"))]
    tirees = tirer_communes(communes, 10, random.Random(1))
    assert len(tirees) == 10
    assert tirees.count("grande") == 9
    assert tirees.count("petite") == 1


def test_tirer_communes_se_refait_avec_la_meme_graine():
    communes = [(f"c{i}", i + 1, ("t", f"r{i % 3}")) for i in range(50)]
    assert tirer_communes(communes, 7, random.Random(3)) == tirer_communes(
        communes, 7, random.Random(3)
    )
    assert tirer_communes(communes, 0, random.Random(3)) == []


def test_une_contribution_par_tirage_de_commune():
    cahiers = {"ville": {"v1": 1, "v2": 0}, "village": {"w1": 3}}
    choisies = choisir_contributions(
        ["ville", "ville", "village", "village"], cahiers, random.Random(0)
    )
    # une grande ville tirée deux fois donne deux contributions, même avec un
    # seul cahier retenu
    assert [f for f, _ in choisies] == ["v1", "v1", "w1", "w1"]
    assert all(0 < position <= 1 for _, position in choisies)


def test_cahier_choisi_selon_ses_pages():
    cahiers = {"ville": {"gros": 9, "mince": 1}}
    choisies = choisir_contributions(["ville"] * 1000, cahiers, random.Random(0))
    assert 850 < sum(f == "gros" for f, _ in choisies) < 950


def test_dans_panel_sans_departements_garde_toute_la_france():
    assert dans_panel("23096", None, ())
    assert not dans_panel(None, None, ())


def test_profil_france_somme_les_comptes_moyenne_les_parts():
    groupes = {"A": "a", "B": "b"}
    structure = {"c1": {"A": "90", "B": "10"}, "c2": {"A": "0", "B": "900"}}
    # la France somme les habitants : la grande commune pèse plus
    assert profil.france(structure, ["c1", "c2"], groupes) == {"a": 0.09, "b": 0.91}
    # un ensemble de cahiers moyenne les parts : un cahier compte pour un
    assert profil.moyenne(structure, ["c1", "c2", "absente"], groupes) == {
        "a": 0.45,
        "b": 0.55,
    }


def test_profil_quarts_de_revenu_pondérés_par_la_population():
    medianes = {"pauvre": 15000, "moyenne": 20000, "riche": 30000}
    populations = {"pauvre": 50, "moyenne": 25, "riche": 25, "secret": 10}
    seuils = profil.seuils_quarts(medianes, populations)
    assert seuils == [15000, 15000, 20000]
    assert profil.quart(15000, seuils) == profil.QUARTS[0]
    assert profil.quart(30000, seuils) == profil.QUARTS[3]
    assert profil.quart(None, seuils) == profil.INCONNU
    assert profil.repartition(["x", "y"], [3, 1]) == {"x": 0.75, "y": 0.25}
