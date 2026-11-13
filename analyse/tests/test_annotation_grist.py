"""Tâches « sous-thèmes » et « paires » dans Grist : choix codés et reversement."""

import pytest

from annotation.grist import (
    AUCUN,
    CHOIX_PAIRES,
    CHOIX_THEMES,
    jugement,
    reverser_paires,
    reverser_themes,
    sous_themes,
)
from annotation.paires import JUGEMENTS, Journal
from annotation.paires import etat as etat_paires
from annotation.themes import NOMS, JournalThemes
from annotation.themes import etat as etat_themes


def test_choix_codes_uniques():
    assert len({c.split(" · ")[0] for c in CHOIX_THEMES}) == len(NOMS) + 1
    assert [jugement(c) for c in CHOIX_PAIRES] == list(JUGEMENTS)


def test_sous_themes_quel_que_soit_l_export():
    a, b = CHOIX_THEMES[1], CHOIX_THEMES[2]
    attendu = sorted([NOMS[0], NOMS[1]])
    # Liste Grist exportée avec virgules, ou JSON, ou une par ligne.
    assert sous_themes(f"{a}, {b}") == attendu
    assert sous_themes(f'["{a}", "{b}"]') == attendu
    assert sous_themes(f"{a}\n{b}") == attendu
    assert sous_themes(AUCUN) == []
    assert sous_themes("") is None
    with pytest.raises(ValueError):
        sous_themes("S99 · inventé")


def test_jugement_avec_virgule():
    assert jugement("2 · même sujet, mesure différente") == JUGEMENTS[1]
    assert jugement("") is None
    with pytest.raises(ValueError):
        jugement("9 · inventé")


def test_reverser_themes(tmp_path):
    journal = JournalThemes(tmp_path / "themes.jsonl")
    lignes = [
        {"proposition": "1-1", "sous_themes": CHOIX_THEMES[3], "mal_coupee": "false"},
        {"proposition": "1-2", "sous_themes": "", "mal_coupee": ""},
        {"proposition": "1-3", "sous_themes": AUCUN, "mal_coupee": ""},
        {"proposition": "1-4", "sous_themes": "", "mal_coupee": "true"},
    ]
    assert reverser_themes(lignes, journal, "Alice") == 3
    annotations = etat_themes(journal.evenements())
    assert annotations["1-1"]["Alice"]["sous_themes"] == {NOMS[2]}
    assert "1-2" not in annotations
    assert annotations["1-3"]["Alice"]["sous_themes"] == set()
    assert annotations["1-4"]["Alice"]["mal_coupee"]


def test_reverser_paires(tmp_path):
    journal = Journal(tmp_path / "paires.jsonl")
    lignes = [
        {"paire": "p1", "jugement": CHOIX_PAIRES[0]},
        {"paire": "p2", "jugement": ""},
    ]
    assert reverser_paires(lignes, journal, "Bob") == 1
    jugements, _ = etat_paires(journal.evenements())
    assert jugements == {"p1": {"Bob": JUGEMENTS[0]}}
