"""Cascade du corpus, sur un versement construit pour le test (aucun cahier)."""

import csv
from collections import Counter
from itertools import pairwise

import pymupdf

from cascade.cascade import (
    DACTYLOGRAPHIEES,
    MANUSCRITES,
    SERVICE,
    VIERGES,
    categorie,
    compter_versement,
    lire_typage,
    niveaux,
    svg,
)


def pdf(chemin, pages):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with pymupdf.open() as doc:
        for _ in range(pages):
            doc.new_page()
        doc.save(chemin)


def test_categorie_lue_dans_le_nom():
    assert categorie("CC_01100_190304_01237_MD_15529.pdf") == "CC"
    assert categorie("CO_01000_190215_D_02389.pdf") == "CO"
    assert categorie("BNF_GDN_01_Ain_inventaire_contributions.pdf") is None


def test_versement_compte_documents_et_pages_par_categorie(tmp_path):
    pdf(tmp_path / "BnF_GDN_01_PDF/CC/CC_01100_190304_01237_MD_1.pdf", 3)
    pdf(tmp_path / "BnF_GDN_01_PDF/CC/CC_01100_190304_01238_MD_2.pdf", 2)
    pdf(tmp_path / "BnF_GDN_01_PDF/CO/CO_01000_190215_D_3.pdf", 1)
    pdf(tmp_path / "A_lire/BNF_GDN_01_Ain_inventaire_contributions.pdf", 9)
    documents, pages = compter_versement(tmp_path)
    assert documents == Counter({"CC": 2, "CO": 1})
    assert pages == Counter({"CC": 5, "CO": 1})


def test_typage_page_de_service_passe_avant_le_type(tmp_path):
    chemin = tmp_path / "pages.csv"
    lignes = [
        ("CC_a.pdf", "vierge", "1"),
        ("CC_a.pdf", "dactylographiée", "1"),
        ("CC_a.pdf", "vierge", "0"),
        ("CC_a.pdf", "manuscrite", "0"),
        ("CC_a.pdf", "dactylographiée", "0"),
        ("CO_b.pdf", "manuscrite", "0"),
    ]
    with chemin.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(["fichier", "page", "type_page", "page_de_service"])
        for i, (fichier, type_page, service) in enumerate(lignes):
            ecrivain.writerow([fichier, i, type_page, service])
    assert lire_typage([tmp_path]) == Counter(
        {SERVICE: 2, VIERGES: 1, MANUSCRITES: 1, DACTYLOGRAPHIEES: 1}
    )


def test_chaque_niveau_garde_une_partie_du_precedent():
    pages = Counter({"CC": 10, "CO": 5, "CR": 3, "IL": 2})
    typage = Counter({SERVICE: 1, VIERGES: 4, DACTYLOGRAPHIEES: 3, MANUSCRITES: 2})
    cascade = niveaux(pages, typage)
    assert [n.pages for n in cascade] == [20, 10, 5]
    for niveau, suivant in pairwise(cascade):
        assert sum(s.pages for s in niveau.segments if s.suite) == suivant.pages


def test_figure_est_un_svg_sans_texte_de_cahier():
    pages = Counter({"CC": 10, "CO": 5, "CR": 3, "IL": 2})
    typage = Counter({SERVICE: 1, VIERGES: 4, DACTYLOGRAPHIEES: 3, MANUSCRITES: 2})
    figure = svg(niveaux(pages, typage), "2026-10-01")
    assert figure.startswith("<svg") and figure.rstrip().endswith("</svg>")
    assert "Pages écrites" in figure
