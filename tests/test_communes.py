"""Rattachement des codes INSEE, sur de petits extraits des référentiels.

Les lignes reprennent de vrais cas du COG, sans aucune donnée des cahiers.
"""

import pytest

from communes.rattachement import Referentiel, raison_non_rattache, rattacher


def commune(typecom, com, libelle, dep="", reg="", comparent=""):
    return {
        "typecom": typecom,
        "com": com,
        "libelle": libelle,
        "dep": dep,
        "reg": reg,
        "comparent": comparent,
    }


def mouvement(date, av, lib_av, ap, lib_ap, type_ap="COM"):
    return {
        "DATE_EFF": date,
        "TYPECOM_AV": "COM",
        "COM_AV": av,
        "LIBELLE_AV": lib_av,
        "TYPECOM_AP": type_ap,
        "COM_AP": ap,
        "LIBELLE_AP": lib_ap,
    }


@pytest.fixture
def ref():
    return Referentiel.depuis_lignes(
        communes=[
            commune("COM", "01004", "Ambérieu-en-Bugey", "01", "84"),
            # Dommartin, déléguée de Bâgé-Dommartin depuis 2018 : pas de département
            commune("COM", "01025", "Bâgé-Dommartin", "01", "84"),
            commune("COMD", "01025", "Bâgé-la-Ville", comparent="01025"),
            commune("COMD", "01144", "Dommartin", comparent="01025"),
            commune("COM", "13055", "Marseille", "13", "93"),
            commune(
                "ARM", "13201", "Marseille 1er Arrondissement", "13", "93", "13055"
            ),
            commune("ARM", "13202", "Marseille 2e Arrondissement", "13", "93", "13055"),
            commune("COM", "21213", "Crimolois", "21", "27"),
            commune("COM", "07103", "Saint-Julien-d'Intres", "07", "84"),
            commune("COM", "97611", "Mamoudzou", "976", "06"),
        ],
        departements=[
            {"dep": "01", "libelle": "Ain"},
            {"dep": "07", "libelle": "Ardèche"},
            {"dep": "13", "libelle": "Bouches-du-Rhône"},
            {"dep": "21", "libelle": "Côte-d'Or"},
            {"dep": "976", "libelle": "Mayotte"},
        ],
        regions=[
            {"reg": "84", "libelle": "Auvergne-Rhône-Alpes"},
            {"reg": "93", "libelle": "Provence-Alpes-Côte d'Azur"},
            {"reg": "27", "libelle": "Bourgogne-Franche-Comté"},
            {"reg": "06", "libelle": "Mayotte"},
        ],
        populations=[
            {"DEPCOM": "01004", "PMUN": "14035"},
            {"DEPCOM": "01025", "PMUN": "4057"},
            # Marseille n'a de ligne que par arrondissement
            {"DEPCOM": "13201", "PMUN": "39786"},
            {"DEPCOM": "13202", "PMUN": "24153"},
            {"DEPCOM": "21213", "PMUN": "1068"},
            {"DEPCOM": "07103", "PMUN": "613"},
            # Communes_associees_ou_deleguees.csv, lu après Communes.csv
            {"DEPCOM": "01025", "PMUN": "3100"},
            {"DEPCOM": "01144", "PMUN": "957"},
        ],
        grille={"01004": 2, "01025": 3, "13055": 1, "21452": 3, "07103": 4, "97611": 2},
        mouvements=[
            mouvement(
                "2019-01-01",
                "07252",
                "Saint-Julien-Boutières",
                "07103",
                "Saint-Julien-d'Intres",
            ),
            mouvement("2019-02-28", "21213", "Crimolois", "21213", "Crimolois", "COMD"),
            mouvement("2019-02-28", "21213", "Crimolois", "21452", "Neuilly-Crimolois"),
            mouvement("1968-01-01", "78270", "Genainville", "95270", "Genainville"),
        ],
    )


def test_commune_simple(ref):
    c = rattacher("01004", ref)
    assert c["nom_2019"] == "Ambérieu-en-Bugey"
    assert c["type_2019"] == "COM"
    assert (c["departement"], c["nom_departement"]) == ("01", "Ain")
    assert c["nom_region"] == "Auvergne-Rhône-Alpes"
    assert c["population_2017"] == "14035"
    assert c["population_incluse_dans"] == ""
    assert (c["densite"], c["libelle_densite"], c["espace"]) == (
        "2",
        "densité intermédiaire",
        "urbain",
    )
    assert c["note"] == ""


def test_commune_de_plein_exercice_prime_sur_deleguee_de_meme_code(ref):
    c = rattacher("01025", ref)
    assert c["type_2019"] == "COM"
    assert c["population_2017"] == "4057"


def test_deleguee_prend_departement_et_densite_de_sa_parente(ref):
    c = rattacher("01144", ref)
    assert c["type_2019"] == "COMD"
    assert (c["departement"], c["region"]) == ("01", "84")
    assert c["population_2017"] == "957"
    assert c["population_incluse_dans"] == "01025"
    assert c["densite"] == "3"
    assert "commune parente 01025" in c["note"]


def test_arrondissement_municipal(ref):
    c = rattacher("13201", ref)
    assert c["type_2019"] == "ARM"
    assert c["population_incluse_dans"] == "13055"
    assert c["densite"] == "1"


def test_population_de_la_ville_somme_ses_arrondissements(ref):
    assert rattacher("13055", ref)["population_2017"] == str(39786 + 24153)


def test_fusion_apres_2019_prend_la_densite_de_la_commune_nouvelle(ref):
    c = rattacher("21213", ref)
    assert c["type_2019"] == "COM"
    assert c["population_2017"] == "1068"
    assert c["code_grille"] == "21452"
    assert "Neuilly-Crimolois" in c["note"]


def test_code_supprime_au_1er_janvier_2019_suit_la_commune_nouvelle(ref):
    c = rattacher("07252", ref)
    assert c["type_2019"] == "supprimée"
    assert c["nom_2019"] == "Saint-Julien-Boutières"
    assert c["population_2017"] == ""
    assert c["population_incluse_dans"] == "07103"
    assert c["densite"] == "4"


def test_mayotte_sans_population(ref):
    c = rattacher("97611", ref)
    assert c["population_2017"] == ""
    assert "Mayotte" in c["note"]


@pytest.mark.parametrize(
    ("code", "raison"),
    [
        ("00000", "non renseignée"),
        ("99999", "étranger"),
        ("98817", "outre-mer"),
        ("78270", "1968"),
        ("12345", "inconnu"),
    ],
)
def test_non_rattaches(ref, code, raison):
    assert rattacher(code, ref) is None
    assert raison in raison_non_rattache(code, ref)
