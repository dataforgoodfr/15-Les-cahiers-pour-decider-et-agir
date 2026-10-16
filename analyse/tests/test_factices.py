"""Fausses coordonnées dans l'édition Chabin, et mesure du repérage."""

from anonymisation.factices import (
    Faussaire,
    garde,
    injecter,
    localiser,
    mesurer,
    regles,
    repandus,
)
from anonymisation.publics import Publics, publics


def faussaire():
    return Faussaire(
        {"Marie": 1},
        ["DE LA FONTAINE"],
        {"17300": [("12 rue des Lilas", "17000", "La Rochelle")]},
        graine=0,
    )


def test_injecter_garde_la_forme_du_crochet():
    texte, donnees = injecter(
        "Signé [Prénom NOM, Adresse] [Signature] [sic] c[om]mune [Téléphone]",
        "17300",
        faussaire(),
        set(),
    )
    assert texte.startswith("Signé Marie DE LA FONTAINE, 12 rue des Lilas")
    assert "Signature" not in texte and "sic" not in texte and "commune" in texte
    assert [d["etiquette"] for d in donnees] == [
        "prénom",
        "nom",
        "adresse",
        "téléphone",
    ]
    prenom, nom = donnees[0], donnees[1]
    assert texte[prenom["debut"] : prenom["fin"]] == "Marie"
    assert texte[nom["debut"] : nom["fin"]] == "DE LA FONTAINE"


def test_injecter_initiales_et_casse():
    texte, donnees = injecter("[P. Nom] et [Initiales]", "17300", faussaire(), set())
    assert texte == "M. De la Fontaine et M.D."
    assert [d["etiquette"] for d in donnees] == ["initiale", "nom", "initiale"]


def test_injecter_un_couple_a_deux_prenoms():
    f = Faussaire({"Marie": 1, "Paul": 1}, ["DUPONT"], {}, graine=0)
    texte, _ = injecter("[Prénom et Prénom NOM]", "17300", f, set())
    assert texte in ("Marie et Paul DUPONT", "Paul et Marie DUPONT")


def test_injecter_ecarte_les_noms_exclus():
    f = Faussaire({"Marie": 1}, ["DUPONT", "MARTIN"], {}, graine=0)
    for _ in range(20):
        texte, _ = injecter("[Nom]", "17300", f, {"dupont"})
        assert texte == "Martin"


def test_localiser_toutes_les_places():
    places = localiser([("Martin", "nom"), ("x", "nom")], "Martin et martin")
    assert [(p["debut"], p["fin"]) for p in places] == [(0, 6), (10, 16)]


def test_regles_rendent_des_places_dans_le_texte():
    texte = "Bonjour\nappelez le 06.12.34.56.78 ou Marie Dupont"
    reperes = regles(texte, "", frozenset({"marie"}))
    assert {(r["texte"], r["etiquette"]) for r in reperes} == {
        ("06.12.34.56.78", "téléphone"),
        ("Marie Dupont", "nom"),
    }


def test_garde_par_etape():
    noms = publics([("Emmanuel", "Macron")], [], set())
    vous = {"texte": "vous", "etiquette": "nom"}
    macron = {"texte": "M. le Président Macron", "etiquette": "nom"}
    dupont = {"texte": "Dupont", "etiquette": "nom"}
    assert garde(macron, 0, noms, set()) and not garde(macron, 1, noms, set())
    assert garde(vous, 1, noms, set()) and not garde(vous, 2, noms, set())
    assert garde(dupont, 2, noms, {"dupont"}) and not garde(dupont, 3, noms, {"dupont"})


def test_repandus():
    textes = [
        {"insee": i, "reperes": [{"texte": "M. Cahuzac", "etiquette": "nom"}]}
        for i in ("1", "2", "3")
    ] + [{"insee": "1", "reperes": [{"texte": "Dupont", "etiquette": "nom"}]}]
    assert repandus(textes) == {"cahuzac"}


def test_mesurer():
    noms = {"17300": Publics(frozenset({"macron"}), frozenset())}
    textes = [
        {
            "insee": "17300",
            "texte": "Marie Dupont écrit à Macron.",
            "donnees": [
                {"debut": 0, "fin": 5, "etiquette": "prénom"},
                {"debut": 6, "fin": 12, "etiquette": "nom"},
            ],
            "reperes": [
                {
                    "debut": 0,
                    "fin": 3,
                    "etiquette": "nom",
                    "texte": "Mar",
                    "source": "modèle",
                },
                {
                    "debut": 21,
                    "fin": 27,
                    "etiquette": "nom",
                    "texte": "Macron",
                    "source": "modèle",
                },
                {
                    "debut": 0,
                    "fin": 12,
                    "etiquette": "nom",
                    "texte": "Marie Dupont",
                    "source": "règles",
                },
            ],
        }
    ]
    m = mesurer(textes, noms)
    brut = m["modèle", 0]
    assert brut["rappel"]["prénom"] == {"donnees": 1, "entieres": 0, "touchees": 1}
    assert brut["rappel"]["nom"]["touchees"] == 0
    assert brut["precision"]["nom"] == {"reperes": 2, "justes": 1}
    assert m["modèle", 1]["precision"]["nom"]["reperes"] == 1
    assert m["les deux", 0]["rappel"]["nom"]["entieres"] == 1
