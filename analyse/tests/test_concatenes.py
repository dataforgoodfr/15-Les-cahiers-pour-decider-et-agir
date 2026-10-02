"""Cahiers concaténés, sur des pages de garde construites pour le test."""

import pymupdf
import pytest

from concatenes.concatenes import (
    COMMUNE_RETROUVEE,
    CONCATENE,
    CONFORME,
    MAL_RATTACHE,
    Fichier,
    classer,
    codes_du_nom,
    communes_nommees,
    lire,
    pages_d_autres_communes,
)

NOMS = {
    "01450": "Villieu-Loyes-Mollon",
    "01451": "Viriat",
    "01440": "Ambutrix",  # un code postal qui est aussi un code INSEE
    "14542": "Rosel",
    "51288": "Heiltz-le-Hutier",
    "13055": "Marseille",
    "13210": "Marseille 10e Arrondissement",
    "17204": "Léoville",
}
PARENTES = {"13210": "13055"}


def garde(commune):
    return f"Le grand débat national Cahier citoyen {commune}"


@pytest.mark.parametrize(
    ("texte", "insee", "attendu"),
    [
        (garde("Viriat - 01451 01440"), "01450", {"01451"}),
        (garde("ROSEL- 14 542 14 740"), "14542", {"14542"}),
        (garde("Heiltz-le-Hutier - 288 51300"), "51232", {"51288"}),
        (garde("« Ville » - « Code INSEE » « Code postal »"), "01450", set()),
        (garde("Mairie - 01451"), "01450", set()),  # code sans le nom
    ],
)
def test_communes_nommees(texte, insee, attendu):
    assert communes_nommees(texte, insee, NOMS) == attendu


def test_codes_du_nom():
    assert codes_du_nom("CC_01800_190301_01450_MD_15590.pdf") == ("01450", "01800")
    assert codes_du_nom("CC_31270_190228_31588s_MD_15982.pdf") == ("31588", "31270")
    assert codes_du_nom("CC_00000_190225_00000_MD_01603.pdf") == ("", "00000")


def fichier(insee, *gardes, pages=60, postal="01800"):
    return Fichier(f"CC_{postal}_190301_{insee}_MD_1.pdf", pages, list(gardes))


def test_cahier_d_une_autre_commune_a_la_suite():
    f = fichier(
        "01450",
        (1, garde("Villieu-Loyes-Mollon - 01450")),
        (41, garde("VIRIAT- 01451 01440")),
    )
    categorie, trouvees = classer(f, NOMS, PARENTES)
    assert (categorie, trouvees) == (CONCATENE, {41: ["01451"]})
    assert pages_d_autres_communes(f, trouvees) == 20


def test_code_du_nom_de_fichier_faux():
    f = fichier("17024", (1, garde("Léoville - 17204 17500")), postal="17470")
    assert classer(f, NOMS, PARENTES)[0] == MAL_RATTACHE


def test_code_postal_et_code_insee_inverses():
    f = fichier("14740", (1, garde("ROSEL- 14 542 14 740")), postal="14542")
    assert classer(f, NOMS, PARENTES)[0] == CONFORME


def test_arrondissement_et_commune_parente():
    f = fichier("13210", (1, garde("Marseille - 13055")), postal="13010")
    assert classer(f, NOMS, PARENTES)[0] == CONFORME


def test_fichier_sans_commune():
    f = fichier("00000", (1, garde("Viriat - 01451 01440")), postal="00000")
    assert classer(f, NOMS, PARENTES)[0] == COMMUNE_RETROUVEE


def test_page_de_garde_illisible():
    f = fichier("01450", (1, garde("« Ville » - « Code INSEE »")))
    assert classer(f, NOMS, PARENTES) == (CONFORME, {})


def test_lire_repere_les_pages_de_garde(tmp_path):
    chemin = tmp_path / "CC_01800_190301_01450_MD_1.pdf"
    with pymupdf.open() as doc:
        for texte in [
            "Cahier citoyen\nViriat - 01451\n01440",
            "Nous demandons " * 40 + "un cahier citoyen pour tous",  # trop longue
            "Fin des pages écrites",
        ]:
            doc.new_page().insert_textbox(pymupdf.Rect(50, 50, 550, 800), texte)
        doc.save(chemin)
    f = lire(chemin)
    assert (f.nom, f.pages) == ("CC_01800_190301_01450_MD_1.pdf", 3)
    assert [p for p, _ in f.gardes] == [1]
