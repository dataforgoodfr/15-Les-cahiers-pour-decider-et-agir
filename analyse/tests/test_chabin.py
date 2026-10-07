"""Référence Chabin : liste à relire et comparaison des comptes."""

from chabin.reference import Cahier, cahiers, comparer, elements

EXTRACTION = [
    None,
    {
        "city": {"insee": "17280", "commune": "Plassay", "habitants": 1},
        "found_nb_contrib": 13,
        "nb_contrib": 13,
        "contributions": [{"title": "…", "text": "…"}],
        "pdf_files": ["BnF_GDN_17_PDF/CC/a.pdf", "BnF_GDN_17_PDF/CC/b.pdf"],
    },
]


def test_cahiers_ignore_les_non_telecharges_et_le_texte():
    assert cahiers(EXTRACTION) == [Cahier("17280", "Plassay", 13, ("a.pdf", "b.pdf"))]


def test_elements_sans_le_compte_de_l_edition():
    els = elements(cahiers(EXTRACTION), {"a.pdf": 18, "b.pdf": 36})
    assert [(e["fichier"], e["page"]) for e in els] == [("a.pdf", 1), ("b.pdf", 1)]
    assert "13" not in els[0]["commentaire"]
    assert "fichier 1 sur 2" in els[0]["commentaire"]
    # un scan absent du versement n'a pas d'élément
    assert [e["fichier"] for e in elements(cahiers(EXTRACTION), {"b.pdf": 36})] == [
        "b.pdf"
    ]


def test_comparer_attend_tous_les_scans_du_cahier():
    liste = cahiers(EXTRACTION)
    assert comparer(liste, {"a.pdf": 5}, {"a.pdf"}) == []
    (ligne,) = comparer(liste, {"a.pdf": 5, "b.pdf": 7}, {"a.pdf", "b.pdf"})
    assert (ligne["chabin"], ligne["lecteur"], ligne["ecart"]) == (13, 12, -1)
