"""Tirage des paires de propositions à annoter."""

import numpy as np
import pytest

from paires.tirage import HASARD, REGLAGE, TEST, lots, normaliser, tirer, voisins


def normes(n: int, graine: int = 0) -> np.ndarray:
    x = np.random.default_rng(graine).normal(size=(n, 8)).astype(np.float32)
    return x / np.linalg.norm(x, axis=1, keepdims=True)


def test_les_voisins_ne_sont_pas_du_meme_groupe():
    x = normes(4)
    x[1] = x[0]  # même contribution : jamais une paire
    x[2] = x[0]
    paires = voisins(x, ["a", "a", "b", "c"], k=1)
    assert (0, 1) not in paires
    assert paires[0, 2] == pytest.approx(1) and paires[1, 2] == pytest.approx(1)


def test_normaliser_ignore_casse_et_ponctuation():
    assert normaliser("Le RIC !") == normaliser("le ric.")


def test_une_proposition_n_entre_que_dans_une_paire():
    x = normes(60)
    textes = [f"proposition {i}" for i in range(60)]
    tirees = tirer(x, list(range(60)), textes, n_tranches=3, par_tranche=5, hasard=5)
    vues = [i for p in tirees for i in (p["i"], p["j"])]
    assert len(vues) == len(set(vues))
    assert sum(p["tranche"] == HASARD for p in tirees) == 5
    assert {p["tranche"] for p in tirees} == {"1", "2", "3", HASARD}


def test_les_tranches_vont_du_moins_au_plus_semblable():
    x = normes(200)
    textes = [str(i) for i in range(200)]
    tirees = tirer(x, list(range(200)), textes, n_tranches=4, par_tranche=10, hasard=0)
    moyennes = [
        np.mean([p["similarite"] for p in tirees if p["tranche"] == str(t)])
        for t in range(1, 5)
    ]
    assert moyennes == sorted(moyennes)


def test_deux_textes_identiques_ne_font_pas_une_paire():
    x = normes(3)
    x[1] = x[0]
    tirees = tirer(x, [0, 1, 2], ["Le RIC.", "le RIC !", "Moins de taxes."], 1, 5, 5)
    assert all({p["i"], p["j"]} != {0, 1} for p in tirees)


def test_meme_part_de_reglage_dans_chaque_tranche():
    tirees = [{"tranche": t} for t in ["1"] * 9 + ["2"] * 3]
    lots(tirees, reglage=1 / 3)
    assert sum(p["lot"] == REGLAGE for p in tirees if p["tranche"] == "1") == 3
    assert sum(p["lot"] == REGLAGE for p in tirees if p["tranche"] == "2") == 1
    assert {p["lot"] for p in tirees} == {REGLAGE, TEST}
