"""Liste blanche du texte, sur des mots construits."""

import numpy as np

from anonymisation.blanche import (
    debuts_de_phrase,
    formulaires,
    hors_du_texte,
    raison,
    reperes_blancs,
    texte_seul,
)
from anonymisation.publics import Publics

LEXIQUE = {"le", "petit", "chat", "l", "etat", "doit", "payer", "pierre", "president"}
PRENOMS = {"pierre", "jean"}
NOMS = Publics(frozenset({"macron", "france"}), frozenset())


def mot(texte, bloc=0, ligne=0, rang=0):
    return (
        10 * rang,
        10 * ligne,
        10 * rang + 8,
        10 * ligne + 8,
        texte,
        bloc,
        ligne,
        rang,
    )


def cache(texte):
    return raison(texte, LEXIQUE, PRENOMS, NOMS)


def test_mots_du_lexique_lieux_et_noms_publics_gardes():
    assert cache("chat") is None
    assert cache("l'État") is None
    assert cache("Macron") is None
    assert cache("France") is None
    assert cache("—") is None


def test_hors_liste_cache():
    assert cache("Dupont") == "majuscule hors liste"
    assert cache("xqzt") == "minuscule hors liste"
    assert cache("06") == "nombre"


def test_prenom_a_majuscule_cache_meme_dans_le_lexique():
    assert cache("Pierre") == "prénom"
    assert cache("pierre") is None


def test_debuts_de_phrase():
    mots = [
        mot("Le", rang=0),
        mot("chat.", rang=1),
        mot("Il", ligne=1, rang=0),
        mot("Nom", bloc=1, ligne=2, rang=0),
        mot("Petit", bloc=1, ligne=2, rang=1),
    ]
    assert debuts_de_phrase(mots) == {0, 2, 3}


def test_reperes_blancs():
    mots = [mot("Le", rang=0), mot("chat", rang=1), mot("Dupont", rang=2)]
    reperes = reperes_blancs(mots, LEXIQUE, PRENOMS, NOMS)
    assert [(r["x0"], r["raison"]) for r in reperes] == [(20, "majuscule hors liste")]


def test_texte_seul_oublie_l_encre():
    donnees = [
        {"x0": 0, "y0": 0, "x1": 30, "y1": 8, "encre": np.ones((2, 2), bool)},
        {"x0": 0, "y0": 50, "x1": 30, "y1": 60, "encre": np.ones((2, 2), bool)},
    ]
    pages = {("f.pdf", 1): {"mots": [mot("Dupont")], "reperes": [], "donnees": donnees}}
    seul = texte_seul(pages)
    assert [d["encre"] for d in seul["f.pdf", 1]["donnees"]] == [None, None]
    assert pages["f.pdf", 1]["donnees"][0]["encre"] is not None
    assert hors_du_texte(pages) == 1  # la seconde n'a aucun mot


def test_formulaires_appris_sur_les_autres_pages():
    imprime = {
        "vos coordonnees facultatif": (50, 100),
        "vos propositions ici": (50, 400),
    }
    lignes = {"f.pdf": {n: dict(imprime) for n in (1, 2, 3, 4)}}
    bloc = {"x0": 50, "y0": 110, "x1": 500, "y1": 200, "etiquette": "bloc"}
    pages = {
        ("f.pdf", n): {"mots": [], "reperes": [], "donnees": [bloc] if n < 4 else []}
        for n in (1, 2, 3, 4)
    }
    zones = formulaires(pages, lignes, 2, "formulaire")
    # la page 1 apprend des pages 2 et 3 ; la 4, sans donnée, des deux plus proches
    assert sorted(zones) == [("f.pdf", n) for n in (1, 2, 3, 4)]
    assert zones["f.pdf", 4][0]["source"] == "formulaire"
    seul = {k: v for k, v in pages.items() if k[1] in (1, 2)}
    assert formulaires(seul, lignes, None, "f") == {}  # une seule autre page


def test_mot_du_lexique_en_un_seul_jeton():
    lexique = LEXIQUE | {"aujourdhui", "oeuvre", "et", "ou"}
    assert raison("aujourd'hui", lexique, PRENOMS, NOMS) is None
    assert raison("œuvre", lexique, PRENOMS, NOMS) is None
    assert raison("et/ou", lexique, PRENOMS, NOMS) is None
    assert raison("Aujourd'hui", lexique, PRENOMS, NOMS) is not None
    assert raison("Et/Ou", lexique, PRENOMS, NOMS) is not None
