"""Recueil : index des contributions exportées et représentativité."""

from recueil.recueil import comparaison, forme, index, page_de_titre

SELECTION = [
    {
        "fichier": "b.pdf",
        "commune": "Brest",
        "departement": "29",
        "statut": "exporté",
        "rang": "3",
        "contributions": "5",
        "page_debut": "4",
        "page_fin": "5",
        "caviardages": "0",
    },
    {
        "fichier": "a.pdf",
        "commune": "Alès",
        "departement": "30",
        "statut": "exporté",
        "rang": "1",
        "contributions": "1",
        "page_debut": "2",
        "page_fin": "2",
        "caviardages": "2",
    },
    {
        "fichier": "c.pdf",
        "commune": "Caen",
        "departement": "14",
        "statut": "à délimiter",
    },
]
TIRAGE = {
    "a.pdf": {
        "code_insee": "30007",
        "region": "Occitanie",
        "taille": "20 000 à 99 999",
        "population": "40000",
    },
    "b.pdf": {
        "code_insee": "29019",
        "region": "Bretagne",
        "taille": "100 000 et plus",
        "population": "140000",
    },
}


def test_forme_d_apres_les_pages_ecrites():
    assert forme(["manuscrite", "vierge", "manuscrite"]) == "manuscrite"
    assert forme(["dactylographiée", "manuscrite"]) == "mixte"
    assert forme(["vierge"]) == "inconnue"


def test_index_des_seules_contributions_exportees_par_region():
    types = {("b.pdf", 4): "dactylographiée", ("b.pdf", 5): "dactylographiée"}
    lignes = index(SELECTION, TIRAGE, types)
    assert [(x["numero"], x["commune"]) for x in lignes] == [(1, "Brest"), (2, "Alès")]
    assert (lignes[0]["pages"], lignes[0]["forme"]) == (2, "dactylographiée")
    assert lignes[1]["forme"] == "inconnue"
    assert "Contribution 3 sur 5" in page_de_titre(lignes[0])
    assert "pages 4 à 5" in page_de_titre(lignes[0])


def test_comparaison_a_la_population():
    lignes = index(SELECTION, TIRAGE, {})
    rangs = comparaison(
        lignes, "region", {"Bretagne": 1, "Occitanie": 3}, ["Bretagne", "Occitanie"]
    )
    assert rangs == [("Bretagne", 1, 0.5), ("Occitanie", 1, 1.5)]
