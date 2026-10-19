"""Mesure du repérage sur les cahiers délimités, sur des pages construites."""

import numpy as np

from anonymisation.delimites import (
    contribution_de,
    couverte,
    encre_de,
    gabarit,
    lignes_de_la_page,
    mesurer,
    reperes_de_zones,
    texte_du_cadre,
)
from anonymisation.publics import Publics


def mot(x0, y0, texte, ligne=0, rang=0):
    return (x0, y0, x0 + 10 * len(texte), y0 + 10, texte, 0, ligne, rang)


def cadre(x0, y0, x1, y1, **reste):
    return {"x0": x0, "y0": y0, "x1": x1, "y1": y1} | reste


MOTS = [
    mot(0, 0, "Signé", rang=0),
    mot(60, 0, "Jean", rang=1),
    mot(110, 0, "Dupont", rang=2),
    mot(0, 20, "Merci", ligne=1),
]


def test_texte_du_cadre():
    assert texte_du_cadre(MOTS, cadre(55, 0, 175, 10)) == "Jean Dupont"


def test_lignes_de_la_page():
    lignes = lignes_de_la_page(MOTS)
    assert [li["texte"] for li in lignes] == ["Signé Jean Dupont", "Merci"]
    assert (lignes[0]["x1"], lignes[1]["y0"]) == (170, 20)


def test_contribution_de():
    debuts = [(1, 0, 1, 100, 1), (1, 100, 2, 50, 2)]
    assert contribution_de(debuts, 1, 50) == 1
    assert contribution_de(debuts, 2, 10) == 2
    assert contribution_de(debuts, 2, 80) is None  # après la fin notée


def test_reperes_de_zones():
    long = " ".join(["mot"] * 20)
    lignes = {
        1: [
            {"texte": long, **cadre(0, 0, 500, 10)},
            {"texte": "Cordialement", **cadre(0, 20, 100, 30)},
            {"texte": "J. Dupont", **cadre(0, 40, 90, 50)},
        ]
    }
    zones = reperes_de_zones(lignes, [(1, 0, 1, 100, 1)])
    assert sorted(z["y0"] for z in zones) == [20, 40]
    assert {z["source"] for z in zones} == {"zones"}


def test_couverte_par_les_mots_et_par_l_encre():
    donnee = cadre(55, 0, 175, 10)
    assert couverte(donnee, MOTS, [cadre(60, 0, 170, 10)])
    assert not couverte(donnee, MOTS, [cadre(60, 0, 100, 10)])  # « Dupont » visible
    gris = np.full((60, 400), 255, np.uint8)
    gris[5:15, 300:340] = 0  # une signature à la main, sans couche texte
    signature = cadre(290, 0, 350, 20)
    signature["encre"] = encre_de(gris, MOTS, signature)
    assert signature["encre"].sum() == 400
    assert couverte(signature, MOTS, [cadre(298, 3, 345, 18)])
    assert not couverte(signature, MOTS, [cadre(300, 5, 320, 15)])  # la moitié


def test_les_mots_du_gabarit_n_ont_pas_a_etre_caches():
    donnee = cadre(0, 0, 175, 10)  # « Signé Jean Dupont »
    gardes = [cadre(60, 0, 170, 10)]  # « Jean Dupont »
    assert not couverte(donnee, MOTS, gardes)
    assert couverte(donnee, MOTS, gardes, {"signe"})  # « Signé » est imprimé
    pages = {("a.pdf", n): {"mots": [mot(0, 0, "Nom")]} for n in (1, 2, 3)}
    assert gabarit(pages) == {"a.pdf": {"nom"}}


def test_mesurer():
    pages = {
        ("a.pdf", 1): {
            "mots": MOTS,
            "donnees": [cadre(55, 0, 175, 10, etiquette="nom", contribution=1)],
            "reperes": [
                cadre(
                    60,
                    0,
                    170,
                    10,
                    etiquette="nom",
                    texte="Jean Dupont",
                    source="modèle",
                ),
                cadre(0, 20, 50, 30, etiquette="nom", texte="Merci", source="règles"),
            ],
        }
    }
    noms = {"a.pdf": Publics(frozenset(), frozenset())}
    m = mesurer(pages, noms, set())
    modele = m["modèle", 0]
    assert modele["rappel"]["nom"] == {"donnees": 1, "couvertes": 1}
    assert modele["ensemble"]["fuites"] == 0
    regles = m["règles", 0]
    assert regles["ensemble"]["fuites"] == 1 and regles["ensemble"]["avec_donnees"] == 1
    assert (regles["ensemble"]["justes"], regles["ensemble"]["reperes"]) == (0, 1)
    assert (regles["ensemble"]["masques"], regles["ensemble"]["hors_donnees"]) == (1, 2)
