"""Repérage des sous-thèmes, sur des phrases construites pour le test."""

from classement.themes.lecture import lignes_imprimees
from classement.themes.sous_themes import normaliser, sous_themes


def test_normaliser_sans_accents_ni_ponctuation():
    assert normaliser("Référendum d'Initiative Citoyenne !") == (
        "referendum d initiative citoyenne"
    )


def test_sous_themes_reperes():
    trouves = sous_themes("Nous voulons le RIC et la prise en compte du vote blanc.")
    assert {"RIC", "Vote blanc et nul"} <= trouves
    assert "RIC" in sous_themes("Instaurer le référendum d'initiative citoyenne")
    assert "Vote blanc et nul" in sous_themes("Compter les bulletins blancs")


def test_un_mot_pris_dans_un_autre_ne_compte_pas():
    assert "RIC" not in sous_themes("Une fabrication très ricin")
    assert sous_themes("Bonjour à tous") == set()


def test_lignes_imprimees_d_un_formulaire():
    question = "Quelles sont vos propositions pour la fiscalité ?"
    pages = [[question, f"réponse {k}"] for k in range(3)]
    assert lignes_imprimees(pages) == {normaliser(question)}


def test_grille_thematiques_v2():
    assert "Mobilité, carburant" in sous_themes("Le prix du gazole augmente")
    assert "Salaires et retraites" in sous_themes("Revaloriser les retraites")
    assert "Qualité de l'eau" in sous_themes("L'eau potable coûte trop cher")
