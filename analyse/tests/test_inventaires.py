"""Documents manquants, sur des lignes d'inventaire inventées pour le test."""

from pathlib import Path

from inventaires.inventaires import (
    Entree,
    departement,
    entree,
    nom_de_fichier,
    rapprocher,
)

EN_TETE = [
    "Nom de la commune",
    "Code\npostal",
    "Code\nINSEE",
    "Catégorie",
    "Nombre\nde pages",
    "Nom du fichier",
]


def test_departement():
    assert departement(Path("BNF_GDN_01_Ain_inventaire_contributions.pdf")) == "01"
    assert departement(Path("GDN_BNF_00_Sans-provenance.pdf")) == "00"
    assert departement(Path("Bnf_GDN_65_PDF")) == "65"


def test_nom_de_fichier():
    assert nom_de_fichier("CC 01500 190318 01004 MD 16116.pdf") == (
        "CC_01500_190318_01004_MD_16116.pdf"
    )
    assert nom_de_fichier("_ _ _ _ _\nIL 01800 190326 D 01304.pdf") == (
        "IL_01800_190326_D_01304.pdf"
    )
    assert nom_de_fichier("CC 00000 190405 00000 MD 19350") == (
        "CC_00000_190405_00000_MD_19350.pdf"
    )


def test_lignes_du_tableau():
    assert entree(EN_TETE, "01") is None
    assert entree(["Cahiers citoyens", None, None, None, None, None], "01") is None
    e = entree(
        ["Ambléon", "01300", "01006", "CC", "36", "CC 01300 190304 01006 MD 15443.pdf"],
        "01",
    )
    assert e == Entree("CC_01300_190304_01006_MD_15443.pdf", "CC", "01", "01006", 36)
    e = entree(["", "01960", "", "CR", "7", "CR 01960 190228 MD 02278.pdf"], "01")
    assert (e.code_insee, e.pages) == ("", 7)


def test_rapprocher():
    entrees = [
        Entree("CC_a.pdf", "CC", "14", "14001", 10),
        Entree("CC_a.pdf", "CC", "22", "14001", 10),  # inventaire recopié
        Entree("CC_b.pdf", "CC", "39", "39042", 8),
    ]
    presents = {"CC_a.pdf": ("14", 12), "CO_c.pdf": ("00", 2)}
    a, b, c = rapprocher(entrees, presents)
    assert (a.departement, a.inventaires, a.present) == ("14", 2, True)
    assert (a.pages_attendues, a.pages_presentes) == (10, 12)
    assert (b.departement, b.present, b.pages_presentes) == ("39", False, None)
    assert (c.categorie, c.departement, c.inventaires, c.pages_attendues) == (
        "CO",
        "00",
        0,
        None,
    )
