"""Tirage pour l'association, sur des communes construites pour le test."""

import random

from panel.panel import dans_panel
from tirage.tirage import allouer, choisir_cahiers, tirer_communes


def test_allouer_aux_plus_forts_restes():
    assert allouer({"a": 0.5, "b": 0.3, "c": 0.2}, 10) == {"a": 5, "b": 3, "c": 2}
    assert allouer({"a": 1, "b": 1, "c": 1}, 10) == {"a": 4, "b": 3, "c": 3}
    assert sum(allouer({"a": 0.71, "b": 0.29}, 7).values()) == 7


def test_tirer_communes_proportionnel_a_la_population():
    communes = [("grande", 900, "r1"), ("petite", 100, "r2")]
    tirees = tirer_communes(communes, 10, random.Random(1))
    assert len(tirees) == 10
    assert tirees.count("grande") == 9
    assert tirees.count("petite") == 1


def test_tirer_communes_se_refait_avec_la_meme_graine():
    communes = [(f"c{i}", i + 1, f"r{i % 3}") for i in range(50)]
    assert tirer_communes(communes, 7, random.Random(3)) == tirer_communes(
        communes, 7, random.Random(3)
    )
    assert tirer_communes(communes, 0, random.Random(3)) == []


def test_choisir_autant_de_cahiers_distincts_que_de_tirages():
    cahiers = {"ville": ["v1", "v2", "v3"], "village": ["w1"]}
    choisis = choisir_cahiers(
        ["ville", "ville", "village", "village"], cahiers, random.Random(0)
    )
    assert len([c for c in choisis if c.startswith("v")]) == 2
    assert len(set(choisis)) == len(choisis)
    assert choisis.count("w1") == 1  # un seul cahier dans le village


def test_dans_panel_sans_departements_garde_toute_la_france():
    assert dans_panel("23096", None, ())
    assert not dans_panel(None, None, ())
