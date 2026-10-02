"""Pages manquantes, sur des courriers types inventés pour le test."""

import pytest

from manquantes import manquantes
from manquantes.manquantes import (
    COMPLET_,
    INCOMPLET,
    VERSION,
    Exemplaire,
    classer,
    commence_en_cours,
    coupure,
    decrire,
    exemplaires,
    finit_en_cours,
    illisible,
    lignes,
    modele,
    paires,
    regrouper,
    structurer,
)

PAGE_1 = (
    "Monsieur le Président de la République,\n"
    "nous vous écrivons au nom des artisans de la commune\n"
    "pour demander une baisse des charges sur les petites entreprises\n"
    "et la simplification des démarches administratives qui"
)
PAGE_2 = (
    "pèsent sur les indépendants et les commerçants de proximité.\n"
    "Nous demandons aussi le maintien des services publics\n"
    "dans les bourgs et les villages de nos campagnes.\n"
    "Veuillez agréer nos salutations respectueuses."
)
AUTRE = "Je souhaite que la route départementale soit réparée avant l'hiver prochain."
COURRIER = modele(0, [lignes(PAGE_1), lignes(PAGE_2)])


def test_les_paires_de_mots_resistent_au_decoupage_des_lignes():
    assert paires("baisse des\ncharges sur") == paires("baisse des charges sur")


def test_exemplaires_dans_l_ordre_du_modele():
    pages = [PAGE_1, "", PAGE_2, AUTRE, PAGE_1, PAGE_2, PAGE_2]
    trouves = exemplaires([paires(t) for t in pages], COURRIER)
    assert trouves == [[(0, 0), (2, 1)], [(4, 0), (5, 1)], [(6, 1)]]


def test_exemplaire_mal_lu_reste_reconnu():
    mal_lu = PAGE_1.replace("artisans", "artlsans").replace("baisse", "ba1sse")
    assert exemplaires([paires(mal_lu)], COURRIER) == [[(0, 0)]]


def test_ponctuation():
    assert commence_en_cours(PAGE_2)
    assert not commence_en_cours(PAGE_1)
    assert finit_en_cours(PAGE_1)
    assert not finit_en_cours(PAGE_2)


def exemplaire(portees, derniers_mots, **coupes):
    return Exemplaire(
        "f.pdf",
        0,
        [k + 1 for k in portees],
        portees,
        derniers_mots,
        coupes.get("debut", False),
        coupes.get("fin", False),
        coupes.get("avant", False),
        coupes.get("apres", False),
    )


def test_version_courte_ou_exemplaire_incomplet():
    complets = [exemplaire([0, 1], "salutations respectueuses")] * 3
    courts = [exemplaire([0], "de nos campagnes")] * 5
    seconde_seule = [exemplaire([1], "salutations respectueuses")] * 5
    tronque = [exemplaire([0], "administratives qui")]
    statuts = [
        (s, m)
        for _, s, m in classer(complets + courts + seconde_seule + tronque, {0: 2})
    ]
    assert statuts == [(COMPLET_, [])] * 3 + [(VERSION, [])] * 5 + [
        (INCOMPLET, [0])
    ] * 5 + [(INCOMPLET, [1])]


def test_coupure_et_voisine_illisible():
    e = exemplaire([0], "administratives qui", fin=True, apres=True)
    assert coupure(e, [1]) and illisible(e, [1])
    e = exemplaire([1], "salutations respectueuses")
    assert not coupure(e, [0]) and not illisible(e, [0])


def test_decrire():
    textes = [AUTRE, PAGE_1, AUTRE * 3, ""]
    (e,) = decrire("f.pdf", textes, COURRIER)
    assert (e.pages, e.portees) == ([2], [0])
    assert e.fin == "demarches administratives qui"
    assert e.fin_coupee and not e.debut_coupe and not e.apres_illisible


@pytest.fixture
def peu_de_fichiers(monkeypatch):
    monkeypatch.setattr(manquantes, "FICHIERS_MIN", 2)
    monkeypatch.setattr(manquantes, "LIGNES_MIN", 4)


def test_apprendre_un_modele_sur_deux_pages(peu_de_fichiers):
    pages = {
        "a.pdf": [lignes(AUTRE), lignes(PAGE_1), lignes(PAGE_2)],
        "b.pdf": [lignes(PAGE_1), set(), lignes(PAGE_2)],
        "c.pdf": [lignes(PAGE_1), lignes(PAGE_2)],
    }
    (groupe,) = regrouper({nom: set().union(*ps) for nom, ps in pages.items()})
    structure = structurer(groupe, pages)
    assert structure == [lignes(PAGE_1), lignes(PAGE_2)]
