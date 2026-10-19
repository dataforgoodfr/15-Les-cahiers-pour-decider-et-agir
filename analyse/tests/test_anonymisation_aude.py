"""Mesure du repérage sur l'étalon de l'Aude, sur des pages construites."""

import csv

import numpy as np

from anonymisation.aude import charger_etalon, encre_cachee, sur


def cadre(x0, y0, x1, y1, **reste):
    return {"x0": x0, "y0": y0, "x1": x1, "y1": y1} | reste


def ecrire(chemin, lignes):
    with chemin.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, list(lignes[0]))
        ecrivain.writeheader()
        ecrivain.writerows(lignes)


def page(fichier, n, type_page="manuscrite", a_verifier="0"):
    return {
        "fichier": fichier,
        "page_bnf": n,
        "type_page": type_page,
        "a_verifier": a_verifier,
    }


def masque(fichier, n, x0, accord="0.9"):
    return (
        {"fichier": fichier, "page_bnf": n}
        | cadre(x0, 0, x0 + 50, 20)
        | {"accord": accord}
    )


def test_sur():
    assert sur({"accord": ""})  # entourage blanc
    assert sur({"accord": "0.5"})
    assert not sur({"accord": "0.2"})


def test_charger_etalon(tmp_path):
    ecrire(
        tmp_path / "pages_etalon.csv",
        [
            page("a.pdf", 1),
            page("a.pdf", 1),  # publiée deux fois
            page("a.pdf", 2, "dactylographiée"),
            page("a.pdf", 3),
            page("a.pdf", 4, a_verifier="1"),
            page("a.pdf", 5, "vierge"),
        ],
    )
    ecrire(
        tmp_path / "etalon.csv",
        [
            masque("a.pdf", 1, 0),
            masque("a.pdf", 1, 2),  # le même masque, de l'autre publication
            masque("a.pdf", 1, 100),
            masque("a.pdf", 3, 0, accord="0.1"),
            masque("a.pdf", 4, 0),
        ],
    )
    pages, douteuses = charger_etalon(tmp_path)
    assert sorted(pages) == [("a.pdf", 1), ("a.pdf", 2)]
    assert douteuses == 1
    assert len(pages["a.pdf", 1]["masques"]) == 2
    assert pages["a.pdf", 2] == {"type": "dactylographiée", "masques": []}


def test_encre_cachee():
    gris = np.full((40, 100), 255, np.uint8)
    gris[0:10, 0:10] = 0  # sous le masque
    gris[20:30, 0:10] = 0  # hors masque, caché par un repérage
    gris[20:30, 50:60] = 0  # hors masque, visible
    p = {"gris": gris, "donnees": [cadre(0, 0, 20, 15)]}
    assert encre_cachee(p, [cadre(0, 18, 15, 35)]) == (100, 200)
    assert encre_cachee(p, []) == (0, 200)
