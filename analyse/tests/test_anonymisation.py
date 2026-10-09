"""Repérages de données personnelles, sur des mots construits pour le test."""

import pytest

from anonymisation.__main__ import zones_reportees
from anonymisation.detection import (
    modele_appris,
    mots_personnels,
    recouvrement,
    retirer_repandues,
    zones,
)
from anonymisation.modeles import (
    Cache,
    Ollama,
    _morceaux,
    localiser,
    texte_de_la_page,
)


def mot(x0, texte, bloc=0, ligne=0, rang=0, y0=100):
    return (x0, y0, x0 + 10 * len(texte), y0 + 10, texte, bloc, ligne, rang)


def test_courriels_personnels_et_publics():
    mots = [
        mot(0, "jean.villeneuve@exemple.com", ligne=0),
        mot(0, "contact@mairie-exemple.fr", ligne=1),
        mot(0, "infos@granddebat.fr", ligne=2),
    ]
    reperes = mots_personnels(mots)
    assert [(r["etiquette"], r["x1"]) for r in reperes] == [("courriel", 270)]


def test_telephone_coupe_en_plusieurs_mots():
    mots = [
        mot(0, "Tél", rang=0),
        mot(40, "06", rang=1),
        mot(70, "12", rang=2),
        mot(100, "34", rang=3),
        mot(130, "56", rang=4),
        mot(160, "78", rang=5),
        mot(200, "merci", rang=6),
    ]
    (r,) = mots_personnels(mots)
    assert r["etiquette"] == "téléphone"
    assert (r["x0"], r["x1"]) == (40, 180)
    # une date ou un code postal ne sont pas des téléphones
    assert mots_personnels([mot(0, "12/02/2019"), mot(0, "75011", rang=1)]) == []


def test_recouvrement_d_un_point():
    rect = {"x0": 0, "y0": 0, "x1": 10, "y1": 10}
    assert recouvrement({"x0": 5, "y0": 5, "x1": 5, "y1": 5}, rect) == 1.0
    assert recouvrement({"x0": 50, "y0": 5, "x1": 50, "y1": 5}, rect) == 0.0


def test_zone_apprise_sur_deux_exemplaires():
    annotees = [
        {"x0": 0, "y0": 80, "x1": 500, "y1": 180, "etiquette": "adresse", "page": 1},
        {"x0": 4, "y0": 84, "x1": 505, "y1": 184, "etiquette": "adresse", "page": 2},
        # un seul exemplaire : pas de zone
        {"x0": 0, "y0": 400, "x1": 50, "y1": 410, "etiquette": "nom", "page": 1},
    ]
    (zone,) = zones(annotees)
    assert zone["etiquette"] == "adresse" and zone["exemplaires"] == 2
    assert (zone["x0"], zone["y0"], zone["x1"], zone["y1"]) == (-4, 76, 509, 188)


def test_zones_reportees_sur_chaque_formulaire():
    debuts = [
        {
            "fichier": "a.pdf",
            "page": str(p),
            "x0": "100",
            "y0": str(y),
            "regle": "gabarit",
        }
        for p, y in ((1, 50), (2, 60), (3, 40))
    ]
    notes = [
        {
            "fichier": "a.pdf",
            "page": 1,
            "x0": 100,
            "y0": 150,
            "x1": 300,
            "y1": 200,
            "etiquette": "adresse",
        },
        {
            "fichier": "a.pdf",
            "page": 2,
            "x0": 100,
            "y0": 160,
            "x1": 300,
            "y1": 210,
            "etiquette": "adresse",
        },
    ]
    reperes = zones_reportees(debuts, notes)
    assert [(r["page"], r["source"]) for r in reperes] == [
        (1, "zone apprise"),
        (2, "zone apprise"),
        (3, "zone"),
    ]
    # la zone suit l'en-tête de chaque exemplaire
    assert reperes[2]["y0"] == 40 + 100 - 4


def test_courriels_abimes_par_l_ocr():
    for texte in (
        "[mailto:jeandupont(g)orange.fr]",
        "<jean.dupont(5>gmail.com>",
        "<jeandupont@orangefr>;",
    ):
        assert [r["etiquette"] for r in mots_personnels([mot(0, texte)])] == [
            "courriel"
        ], texte
    # « (a) » dans une phrase n'est pas un arobase
    assert mots_personnels([mot(0, "article(a)suivant")]) == []


def test_seuls_les_noms_repandus_sont_ecartes():
    def repere(etiquette, cle):
        return {
            "page": 1,
            "x0": 0,
            "y0": 0,
            "x1": 1,
            "y1": 1,
            "etiquette": etiquette,
            "cle": cle,
        }

    par_cahier = {
        f"c{i}.pdf": [repere("nom", "emmanuelmacron"), repere("courriel", "militant")]
        for i in range(3)
    }
    par_cahier["c0.pdf"].append(repere("nom", "jeandupont"))
    garde = retirer_repandues(par_cahier)
    # la personnalité part ; l'adresse du militant, présente partout, reste cachée
    assert sorted(r["etiquette"] for r in garde) == ["courriel"] * 3 + ["nom"]
    assert all("cle" not in r for r in garde)


def test_localiser_un_passage_mot_a_mot():
    mots = [
        mot(0, "Signé", rang=0),
        mot(70, "Jean-Paul", rang=1),
        mot(170, "DUPONT,", rang=2),
        mot(0, "Duponteau", ligne=1, y0=120),
        mot(0, "dupont", ligne=2, y0=140),
    ]
    reperes = localiser([("jean paul Dupont", "nom"), ("Dupont", "nom")], mots)
    # le passage entier, puis « Dupont » à chacune de ses deux places, pas
    # dans « Duponteau »
    assert [(r["x0"], r["y0"], r["x1"]) for r in reperes] == [
        (70, 100, 240),
        (170, 100, 240),
        (0, 140, 60),
    ]
    assert localiser([("Martin", "nom"), ("", "nom")], mots) == []


def test_localiser_un_passage_sur_deux_lignes():
    mots = [mot(300, "12", rang=0), mot(0, "rue", ligne=1, y0=120, rang=0)]
    reperes = localiser([("12 rue", "adresse")], mots)
    assert [r["y0"] for r in reperes] == [100, 120]


def test_texte_de_la_page_ligne_par_ligne():
    mots = [mot(50, "b", rang=1), mot(0, "a", rang=0), mot(0, "c", ligne=1)]
    assert texte_de_la_page(mots) == "a b\nc"


def test_cache_n_appelle_le_modele_qu_une_fois(tmp_path):
    appels = []

    def modele(texte):
        appels.append(texte)
        return [("Jean Dupont", "nom")]

    cache = Cache(tmp_path / "m.jsonl")
    assert cache.obtenir("a.pdf", 1, modele, "x") == [("Jean Dupont", "nom")]
    cache.obtenir("a.pdf", 1, modele, "x")
    relu = Cache(tmp_path / "m.jsonl")
    assert relu.obtenir("a.pdf", 1, modele, "x") == [("Jean Dupont", "nom")]
    assert len(appels) == 1


def test_le_modele_tourne_sur_cette_machine():
    with pytest.raises(ValueError):
        Ollama("qwen3.5:9b", url="https://api.exemple.com")


def test_morceaux_coupes_aux_fins_de_ligne():
    assert _morceaux("a b\nc d\ne f", 4, 1) == ["a b\nc d\n", "e f\n"]


def test_morceaux_coupent_une_ligne_trop_longue_avec_chevauchement():
    ligne = " ".join(f"m{i}" for i in range(10))
    morceaux = _morceaux(f"x\n{ligne}\ny", 4, 1)
    assert morceaux == [
        "x\n",
        "m0 m1 m2 m3\n",
        "m3 m4 m5 m6\n",
        "m6 m7 m8 m9\n",
        "y\n",
    ]
    # aucun morceau ne dépasse la fenêtre
    assert all(len(m.split()) <= 4 for m in morceaux)


def test_modele_appris_reporte_sur_les_exemplaires_remplis_a_la_main():
    imprime = {
        "vos coordonnees facultatif": (50, 100),
        "vos propositions ici": (50, 400),
    }
    pages = {
        # exemplaires annotés, puis un exemplaire numérisé 30 points plus bas
        1: {**imprime, "jean dupont rue x": (60, 130)},
        2: dict(imprime),
        3: {x: (a, b + 30) for x, (a, b) in imprime.items()},
        4: {"une lettre sans formulaire": (50, 100)},
    }
    bloc = {"x0": 50, "y0": 110, "x1": 500, "y1": 200, "etiquette": "bloc"}
    annotees = [{**bloc, "page": 1}, {**bloc, "page": 2, "y1": 210}]
    reperes = modele_appris(pages, annotees)
    assert [r["page"] for r in reperes] == [1, 2, 3]
    assert [r["source"] for r in reperes] == ["modèle appris"] * 2 + ["modèle"]
    trois = reperes[2]
    assert (trois["y0"], trois["y1"]) == (110 - 4 + 30, 210 + 4 + 30)


def test_modele_appris_demande_deux_exemplaires():
    pages = {1: {"vos coordonnees facultatif": (50, 100), "autre ligne longue": (0, 0)}}
    bloc = {"x0": 0, "y0": 0, "x1": 10, "y1": 10, "etiquette": "bloc", "page": 1}
    assert modele_appris(pages, [bloc]) == []
