"""Sélection du panel, sur des lignes de typage construites pour le test."""

import csv

import pytest

from panel.panel import (
    cahiers,
    code_insee,
    communes_du_panel,
    dans_panel,
    departement,
    par_departement,
)


def page(fichier, type_page="manuscrite", service="0"):
    return {"fichier": fichier, "type_page": type_page, "page_de_service": service}


@pytest.mark.parametrize(
    ("fichier", "attendu"),
    [
        ("CC_23000_190225_23096_MD_00001.pdf", "23096"),
        ("CC_97200_190225_97209_MD_00002.pdf", "97209"),
        ("CC_00000_190225_00000_MD_00490.pdf", None),
        ("CC_99999_190405_99999_MD_19341.pdf", None),
        ("CO_23000_190215_D_02389.pdf", None),
    ],
)
def test_code_insee(fichier, attendu):
    assert code_insee(fichier) == attendu


def test_departement_outre_mer_sur_trois_chiffres():
    assert departement("23096") == "23"
    assert departement("2A004") == "2A"
    assert departement("97209") == "972"


def test_dans_panel_par_departement_ou_par_commune():
    assert dans_panel("23096", {"23"}, set())
    assert dans_panel("33063", {"23"}, {"33063"})
    assert not dans_panel("33039", {"23"}, {"33063"})
    assert not dans_panel(None, {"23"}, set())


def test_cahiers_compte_les_pages_par_type():
    lignes = [
        page("CC_23000_190225_23096_MD_1.pdf", "dactylographiée", service="1"),
        page("CC_23000_190225_23096_MD_1.pdf", "manuscrite"),
        page("CC_23000_190225_23096_MD_1.pdf", "dactylographiée"),
        page("CC_23000_190225_23096_MD_1.pdf", "vierge"),
        page("CC_33000_190225_33063_MD_2.pdf", "manuscrite"),
        page("CC_33000_190225_33039_MD_3.pdf", "manuscrite"),  # hors panel
        page("CO_23000_190215_D_4.pdf", "manuscrite"),  # pas un cahier citoyen
    ]
    panel = cahiers(lignes, {"23"}, {"33063"})
    assert [c["fichier"] for c in panel] == [
        "CC_23000_190225_23096_MD_1.pdf",
        "CC_33000_190225_33063_MD_2.pdf",
    ]
    creuse = panel[0]
    assert (creuse["pages"], creuse["dactylographiees"], creuse["manuscrites"]) == (
        4,
        1,
        1,
    )
    assert par_departement(panel, {"33063"}) == {
        "23": {"cahiers": 1, "pages": 4, "ecrites": 2},
        "33063": {"cahiers": 1, "pages": 1, "ecrites": 1},
    }


def test_communes_du_panel_garde_le_format_de_la_table(tmp_path):
    table = tmp_path / "communes.csv"
    with table.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(["code_insee", "pages", "type_2019"])
        ecrivain.writerows(
            [["23096", "4", "COM"], ["33063", "1", "COM"], ["33039", "2", "COM"]]
        )
    lignes = communes_du_panel(table, {"23"}, {"33063"})
    assert [ligne["code_insee"] for ligne in lignes] == ["23096", "33063"]
    assert list(lignes[0]) == ["code_insee", "pages", "type_2019"]
