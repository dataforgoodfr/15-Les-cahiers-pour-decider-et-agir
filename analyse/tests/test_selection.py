"""Contribution tirée d'après les débuts notés, et ce qui l'entoure."""

import pymupdf
import pytest

from selection.__main__ import caviarder
from selection.contribution import (
    MARGE,
    Sens,
    coupure,
    delimites,
    derniere_page,
    doublons,
    ecartee,
    en_colonnes,
    hors_contribution,
    hors_polygone,
    tiree,
)


def test_tiree_prend_le_rang_de_la_position():
    debuts = [(3, 50.0, 0.0), (1, 100.0, 0.0), (1, 400.0, 0.0), (5, 20.0, 0.0)]
    t = tiree(0.6, debuts, [], derniere_page=8)
    # 0,6 × 4 = 2,4 → 3e début dans l'ordre de lecture
    assert (t.rang, t.n, t.page_debut, t.y_debut) == (3, 4, 3, 50.0)
    # sans fin notée : jusqu'au début suivant
    assert (t.page_fin, t.y_fin, t.fin_notee) == (5, 20.0, False)
    assert t.pages == [3, 4, 5]


def test_tiree_s_arrete_a_sa_fin_notee():
    debuts = [(1, 100.0, 0.0), (4, 80.0, 0.0)]
    t = tiree(0.1, debuts, [(2, 300.0, 0.0), (6, 10.0, 0.0)], 8)
    assert (t.rang, t.page_fin, t.y_fin, t.fin_notee) == (1, 2, 300.0, True)
    # une fin après le début suivant n'est pas la sienne
    t = tiree(0.1, debuts, [(6, 10.0, 0.0)], 8)
    assert (t.page_fin, t.fin_notee) == (4, False)


def test_la_derniere_contribution_va_jusqu_a_la_fin_du_cahier():
    debuts = [(1, 100.0, 0.0), (4, 80.0, 0.0)]
    t = tiree(1.0, debuts, [], 8)
    assert (t.rang, t.page_fin, t.y_fin) == (2, 8, None)
    assert tiree(0.5, [], [], 8) is None
    # une position nulle prend la première
    assert tiree(0.0, debuts, [], 8).rang == 1


def test_un_debut_pose_deux_fois_ne_compte_qu_une_fois():
    debuts = [
        (1, 50.0, 40.0),
        (2, 30.0, 40.0),
        (2, 800.0, 40.0),
        (2, 803.0, 42.0),
        (2, 805.0, 39.0),
        (3, 40.0, 40.0),
    ]
    t = tiree(0.5, debuts, [], 8)
    assert (t.rang, t.n, t.page_debut, t.y_debut) == (2, 4, 2, 30.0)
    # signalé une fois, à vérifier
    assert doublons(debuts)[1] == [(2, 800.0, 40.0)]


def test_les_cases_d_une_grille_ne_sont_pas_des_doublons():
    # même hauteur, cases voisines : trois contributions
    cases = [(19, 100.0, 40.0), (19, 104.0, 200.0), (19, 98.0, 360.0)]
    assert doublons(cases) == (sorted(cases), [])


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_sens_de_lecture_aller_retour(rotation):
    sens = Sens(rotation, 600.0, 800.0)
    u, v = sens.vers_lecture(100.0, 50.0)
    assert sens.vers_pdf(u, v) == (100.0, 50.0)
    largeur, hauteur = sens.dimensions
    assert 0 <= u <= largeur and 0 <= v <= hauteur


def test_une_page_tournee_se_lit_de_gauche_a_droite_du_pdf():
    # page numérisée couchée, lue après un quart de tour horaire : le haut de
    # la page lue est le bord gauche du PDF
    sens = Sens(90, 600.0, 800.0)
    gauche, droite = sens.vers_lecture(50.0, 400.0), sens.vers_lecture(500.0, 400.0)
    assert gauche[1] < droite[1]
    assert sens.dimensions == (800.0, 600.0)
    # le dessus de la page lue repart vers la gauche du PDF
    assert sens.cadre_pdf(0.0, 0.0, 800.0, 44.0) == (0.0, 0.0, 44.0, 800.0)


def test_une_double_page_se_reconnait_a_un_debut_au_milieu():
    couchee = Sens(90, 600.0, 840.0)  # lue en 840 × 600
    # le haut de la page de droite : la coupure passe juste avant
    assert coupure(couchee, [40.0, 421.0, 438.0], None) == 421.0 - MARGE
    # débuts au bord gauche : une page simple à l'horizontale
    assert coupure(couchee, [40.0, 45.0], None) is None
    # une page en hauteur n'est pas une double page, sauf qualifiée
    debout = Sens(0, 600.0, 840.0)
    assert coupure(debout, [300.0], None) is None
    assert coupure(debout, [300.0], True) == 300.0 - MARGE
    # qualifiée sans début au milieu : coupée au milieu ; décochée : simple
    assert coupure(couchee, [40.0], True) == 420.0
    assert coupure(couchee, [40.0, 421.0], False) is None


def test_une_double_page_se_lit_a_gauche_puis_a_droite():
    # p. 43 : la fin de la contribution de la p. 42 est en haut de la page de
    # gauche, plus bas que le début de la page de droite
    c, h = 432.0, 600.0
    debuts = [(42, 663.0, 50.0), (43, 72.0, 438.0)]
    fins = [(43, 96.0, 346.0), (43, 210.0, 797.0)]
    debuts = [en_colonnes(p, c if p[0] == 43 else None, h) for p in debuts]
    fins = [en_colonnes(p, c if p[0] == 43 else None, h) for p in fins]
    t = tiree(0.1, debuts, fins, 50)
    assert (t.page_fin, t.y_fin, t.fin_notee) == (43, 96.0, True)
    t = tiree(1.0, debuts, fins, 50)
    assert (t.page_debut, t.y_debut, t.y_fin) == (43, 72.0 + h, 210.0 + h)
    # gris : toute la page de gauche, le haut et le bas de celle de droite
    assert hors_contribution(t, 43, 840.0, h, c) == [
        (0.0, 0.0, c, h),
        (c, 0.0, 840.0, 72.0 - MARGE),
        (c, 210.0 + MARGE, 840.0, h),
    ]


def test_hors_contribution_couvre_le_dessus_du_debut_et_le_dessous_de_la_fin():
    t = tiree(0.1, [(2, 100.0, 0.0), (3, 500.0, 0.0)], [(3, 200.0, 590.0)], 8)
    assert hors_contribution(t, 2, 600, 800) == [(0.0, 0.0, 600, 100.0 - MARGE)]
    # la fin notée garde sa ligne
    assert hors_contribution(t, 3, 600, 800) == [(0.0, 200.0 + MARGE, 600, 800)]
    # sans fin notée, le début suivant n'est pas gardé
    t = tiree(0.1, [(2, 100.0, 0.0), (2, 500.0, 0.0)], [], 8)
    assert hors_contribution(t, 2, 600, 800) == [
        (0.0, 0.0, 600, 100.0 - MARGE),
        (0.0, 500.0 - MARGE, 600, 800),
    ]
    # une contribution en haut de page, jusqu'à la fin du cahier : rien à couvrir
    t = tiree(1.0, [(2, 3.0, 0.0)], [], 8)
    assert hors_contribution(t, 2, 600, 800) == []


def test_hors_contribution_suit_les_cotes_du_contour():
    # une case de grille : le début borne la gauche, la fin notée la droite
    t = tiree(0.1, [(1, 200.0, 200.0)], [(1, 300.0, 360.0)], 8)
    assert hors_contribution(t, 1, 600, 800) == [
        (0.0, 0.0, 600, 200.0 - MARGE),
        (0.0, 300.0 + MARGE, 600, 800),
        (0.0, 200.0 - MARGE, 200.0 - MARGE, 300.0 + MARGE),
        (360.0 + MARGE, 200.0 - MARGE, 600, 300.0 + MARGE),
    ]
    # sur plusieurs pages : la page du début n'est bornée qu'à gauche, celle
    # de la fin qu'à droite ; près du bord, le côté colle à la page
    t = tiree(0.1, [(1, 200.0, 200.0)], [(2, 300.0, 400.0)], 8)
    assert hors_contribution(t, 1, 600, 800)[1:] == [
        (0.0, 200.0 - MARGE, 200.0 - MARGE, 800)
    ]
    assert hors_contribution(t, 2, 600, 800)[1:] == [
        (400.0 + MARGE, 0.0, 600, 300.0 + MARGE)
    ]
    t = tiree(0.1, [(1, 200.0, 80.0)], [(1, 300.0, 520.0)], 8)
    assert hors_contribution(t, 1, 600, 800)[2:] == []


def test_derniere_page_saute_les_vierges():
    pages = [
        {"page": n, "type": t}
        for n, t in enumerate(["manuscrite", "mixte", "vierge", "vierge"], 1)
    ]
    assert derniere_page(pages, "f.pdf", {}) == 2
    # un type vérifié l'emporte sur le typage
    assert derniere_page(pages, "f.pdf", {("f.pdf", 4): {"type": "manuscrite"}}) == 4
    assert derniere_page([{"page": 1, "type": "vierge"}], "f.pdf", {}) == 1


def test_delimite_quand_une_page_vue_atteint_la_derniere_montree():
    pages = {
        "f.pdf": [
            {"page": n, "type": t}
            for n, t in enumerate(["manuscrite", "mixte", "vierge", "vierge"], 1)
        ]
    }
    assert delimites({"f.pdf"}, pages, {("f.pdf", 1)}, {}) == set()
    assert delimites({"f.pdf"}, pages, {("f.pdf", 2)}, {}) == {"f.pdf"}
    # une page vue plus loin, devenue vierge depuis, compte aussi
    assert delimites({"f.pdf"}, pages, {("f.pdf", 4)}, {}) == {"f.pdf"}
    # un cahier hors du versement n'est jamais délimité
    assert delimites({"g.pdf"}, pages, {("g.pdf", 9)}, {}) == set()


def test_ordre_commence_par_ce_qui_manque():
    from selection.ordre import ordre

    tirage = [
        {"fichier": "a", "region": "Bretagne", "taille": "petite"},
        {"fichier": "b", "region": "Bretagne", "taille": "petite"},
        {"fichier": "c", "region": "Île-de-France", "taille": "grande"},
        {"fichier": "d", "region": "Île-de-France", "taille": "grande"},
    ]
    # « a » fait : l'Île-de-France et les grandes communes manquent
    assert [t["fichier"] for t in ordre(tirage, {"a"})] == ["c", "b", "d"]
    # rien de fait : on alterne, à égalité dans l'ordre des fichiers
    assert [t["fichier"] for t in ordre(tirage, set())] == ["a", "c", "b", "d"]


def test_reordonner_garde_les_elements_et_met_les_faits_a_la_fin():
    from selection.ordre import reordonner

    tirage = [
        {"fichier": f, "region": r, "taille": "t"}
        for f, r in [("a", "X"), ("b", "X"), ("c", "Y")]
    ]
    liste = {
        "titre": "T",
        "elements": [{"fichier": f, "commentaire": f.upper()} for f in "abc"],
    }
    nouvelle = reordonner(liste, tirage, {"a"})
    assert [e["fichier"] for e in nouvelle["elements"]] == ["c", "b", "a"]
    assert nouvelle["elements"][0]["commentaire"] == "C"
    assert nouvelle["titre"] == "T"


def test_une_page_a_ecarter_ecarte_la_contribution():
    qualifications = {
        ("c.pdf", 3): {"problemes": {"à écarter": True}},
        ("c.pdf", 5): {"problemes": {"coupée": True}},
    }
    assert ecartee("c.pdf", [2, 3], qualifications)
    assert not ecartee("c.pdf", [4, 5], qualifications)


def test_decocher_a_ecarter_rend_la_contribution():
    decoche = {("c.pdf", 3): {"problemes": {"à écarter": False}}}
    assert not ecartee("c.pdf", [3], decoche)


def test_une_page_tournee_sort_dans_le_sens_de_lecture(tmp_path):
    chemin, sortie = tmp_path / "cahier.pdf", tmp_path / "contribution.pdf"
    with pymupdf.open() as doc:
        doc.new_page(width=600, height=800)
        doc.save(chemin)
    # tournée d'un quart de tour, la page se lit en 800 × 600
    t = tiree(0.1, [(1, 100.0, 0.0)], [], 1)
    caviarder(chemin, sortie, t, {}, {1: Sens(90, 600, 800)}, "cahier.pdf")
    with pymupdf.open(sortie) as doc:
        page = doc[0]
        assert page.rotation == 90
        assert (page.rect.width, page.rect.height) == (800, 600)
        pix = page.get_pixmap(dpi=36)  # un demi-point par pixel
        # le gris couvre le dessus du début, en haut de la page lue
        assert pix.pixel(200, 20) != (255, 255, 255)
        assert pix.pixel(200, 200) == (255, 255, 255)


def test_hors_polygone_couvre_tout_le_dehors():
    # un L : le bas-droit de la page est dehors
    points = [[0, 0], [600, 0], [600, 400], [300, 400], [300, 800], [0, 800]]
    cadres = hors_polygone(points, 600, 800)
    assert cadres == [(300, 400.0, 600, 800.0)]
    # un triangle : rien de dehors ne reste découvert, à la bande près
    triangle = [[0, 0], [600, 0], [0, 800]]
    cadres = hors_polygone(triangle, 600, 800)
    for x, y in [(590, 20), (300, 420), (550, 700)]:
        assert any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in cadres)
    assert not any(x0 <= 100 <= x1 and y0 <= 100 <= y1 for x0, y0, x1, y1 in cadres)


def test_un_contour_grise_le_dehors_du_polygone(tmp_path):
    chemin, sortie = tmp_path / "cahier.pdf", tmp_path / "contribution.pdf"
    with pymupdf.open() as doc:
        doc.new_page(width=600, height=800)
        doc.save(chemin)
    t = tiree(0.1, [(1, 100.0, 0.0)], [], 1)
    polygone = [[0, 0], [600, 0], [600, 400], [300, 400], [300, 800], [0, 800]]
    caviarder(
        chemin, sortie, t, {}, {1: Sens(0, 600, 800)}, "cahier.pdf", None, {1: polygone}
    )
    with pymupdf.open(sortie) as doc:
        pix = doc[0].get_pixmap(dpi=36)
        assert pix.pixel(200, 200) != (255, 255, 255)  # bas droit : dehors
        assert pix.pixel(100, 300) == (255, 255, 255)  # bas gauche : dedans
        # les bandes ne s'appliquent plus : le haut, au-dessus du début, reste
        assert pix.pixel(100, 20) == (255, 255, 255)
