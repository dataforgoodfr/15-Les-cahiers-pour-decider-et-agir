"""Pages qui ouvrent une contribution, sur des pages construites pour le test."""

import numpy as np
import pymupdf

from decoupage.contributions.pages import (
    INDICES,
    RANGS,
    Ligne,
    Logistique,
    indices,
    matrice,
    ouvre,
    validation_croisee,
)


def page(*lignes, y=72, police="Times", taille=11.0, x=72):
    return [
        Ligne(t, pymupdf.Rect(x, y + 14 * k, x + 400, y + 14 * k + 12), police, taille)
        for k, t in enumerate(lignes)
    ]


def test_indices_d_une_lettre_qui_suit_une_autre():
    precedente = page("doléances sur les impôts", "Veuillez agréer, cordialement")
    lettre = page("Le 12 janvier 2019", "Madame, monsieur", police="Arial", x=100)
    d = indices(precedente, lettre, 842, 595, 842, contigue=True)
    assert set(d) == set(INDICES)
    assert d["police"] == d["date"] == d["politesse"] == d["premiere_courte"] == 1
    assert d["mots_communs"] == 0 and d["marge"] > 0
    assert d["contigue"] == 1 and d["suite"] == 0


def test_une_page_qui_continue_la_precedente():
    precedente = page("nous demandons la baisse des impôts locaux")
    suite = page("et des impôts sur le revenu, page 2 sur 3")
    d = indices(precedente, suite, 842, 595, 842, contigue=False)
    assert d["minuscule"] == d["suite"] == 1 and d["mots_communs"] > 0
    assert indices([], suite, 842, 595, 842, contigue=True) is None


def test_ouvre_en_haut_de_page_seulement():
    lignes = page("titre", y=300)
    assert ouvre(lignes, 842, [310])  # près de la première ligne
    assert ouvre(lignes, 842, [50])  # dans le premier cinquième
    assert not ouvre(lignes, 842, [600])
    assert not ouvre(lignes, 842, [])


def test_rangs_dans_le_cahier():
    d = dict.fromkeys(INDICES, 0.0)
    lignes = [d | {"taille": t} for t in (1.0, 3.0, 2.0, 5.0)]
    x = matrice(lignes, ["a", "a", "a", "b"])
    rang = x[:, len(INDICES) + RANGS.index("taille")]
    assert list(rang) == [0.0, 1.0, 0.5, 0.5]  # seul dans son cahier : 0,5


def test_logistique_et_validation_croisee_par_cahier():
    rng = np.random.default_rng(0)
    x = rng.normal(size=(200, 2))
    y = (x[:, 0] > 0).astype(float)
    modele = Logistique().entrainer(x, y)
    assert ((modele.probabilites(x) >= 0.5) == y).mean() > 0.95
    cahiers = [f"c{k % 10}" for k in range(200)]
    p = validation_croisee(x, y, cahiers)
    assert ((p >= 0.5) == y).mean() > 0.9
