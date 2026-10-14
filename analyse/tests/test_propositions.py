"""Découpage des contributions de l'édition Chabin en propositions."""

from propositions.__main__ import echantillon, lignes
from propositions.decoupage import Proposition, decouper


def textes(texte: str) -> list[str]:
    return [p.texte for p in decouper(texte)]


def test_lignes_coupees_par_la_mise_en_page():
    texte = (
        "Que la taxe d'habitation soit supprimée pour tous les foyers de la commune et\n"
        "que les recettes soient compensées.\n"
        "Arrêtons les privilèges des élus."
    )
    assert textes(texte) == [
        (
            "Que la taxe d'habitation soit supprimée pour tous les foyers de la "
            "commune et que les recettes soient compensées."
        ),
        "Arrêtons les privilèges des élus.",
    ]


def test_puces_et_numeros():
    texte = "− Suppression du Sénat.\n• Moins de députés.\n2) Le RIC.\nb) La proportionnelle."
    assert [p.forme for p in decouper(texte)] == ["puce"] * 4
    assert textes(texte)[2] == "Le RIC."


def test_la_prose_est_coupee_en_phrases_sauf_apres_une_initiale():
    assert textes("Que M. MACRON écoute. Rétablir l'ISF ! Moins de taxes.") == [
        "Que M. MACRON écoute.",
        "Rétablir l'ISF !",
        "Moins de taxes.",
    ]


def test_intitules_et_sous_puces():
    texte = (
        "Réformes constitutionnelles.\n"
        "• Suppression du Sénat.\n"
        "• Limitation du nombre de députés :\n"
        "− 1 par département\n"
        "• Instauration du RIC.\n"
        "TVA :\n"
        "− Baisse sur les produits de base."
    )
    assert decouper(texte) == [
        Proposition("Suppression du Sénat.", "Réformes constitutionnelles", "puce"),
        Proposition("1 par département", "Limitation du nombre de députés", "puce"),
        # la puce « • » suivante clôt l'intitulé à puce
        Proposition("Instauration du RIC.", "Réformes constitutionnelles", "puce"),
        Proposition("Baisse sur les produits de base.", "TVA", "puce"),
    ]


def test_une_ligne_courte_seule_est_une_proposition():
    texte = "21/12/18\nSuppression de la CSG.\nRIC.\nLe 16 janvier 2019\n[Signature]"
    assert textes(texte) == ["Suppression de la CSG.", "RIC."]


def test_lignes_et_echantillon():
    extraction = [
        None,
        {
            "city": {"insee": "17008", "commune": "Andilly"},
            "contributions": [
                {"title": "1.", "text": "RIC.\nMoins de taxes."},
                {"title": "2.", "text": "[Néant]"},
            ],
        },
    ]
    toutes = lignes(extraction)
    assert [(x["rang"], x["numero"], x["texte"]) for x in toutes] == [
        (1, 1, "RIC."),
        (1, 2, "Moins de taxes."),
        (2, "", ""),
    ]
    tirees = echantillon(toutes, 1, 0)
    assert len({x["rang"] for x in tirees}) == 1
    assert all(x["decoupage"] == x["nature"] == "" for x in tirees)
