"""Référence Chabin : liste à relire et comparaison des comptes."""

from chabin.__main__ import DEBUT, lecture_htr, mesurer_manuscrits
from chabin.alignement import genre, localiser, normaliser
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


def test_genre_du_titre():
    assert genre("3. Mail imprimé, 15 lignes, 198 mots (homme)") == "mail"
    assert genre("1. Dactylographié (6 pages), 200 lignes") == "dactylographié"
    assert genre("12 . Manuscrit, 8 lignes") == "manuscrit"
    assert genre("C12. Manuscrit (coupon préimprimé collé), 10 lignes") == "manuscrit"
    assert genre("2. Une page dactylographiée pliée collée, 9 lignes") == (
        "dactylographié"
    )
    assert genre("4. Tract dactylographié (copie noir et blanc)") == "dactylographié"
    assert genre("Annexe") == ""


def test_normaliser_retire_les_ajouts_de_l_edition():
    assert normaliser("NOM : [Nom Prénom]\nÂge : 70 ans [sic].") == "nom âge 70 ans"


OCR = [
    "Cahier citoyen",
    "",
    "Monsieur le Prefet, je souhaite",
    "la baisse des taxes sur le carburant",
    "et le retour du service public.",
    "Grand debat national - formulaire",
    "Vos propositions : plus de trains",
    "Grand debat national - formulaire",
    "Vos propositions : moins de taxes",
]


def test_localiser_a_l_ocr_pres():
    (trouve,) = localiser(
        [
            (
                "Monsieur le Préfet, je souhaite la baisse des taxes "
                "sur le carburant et le retour du service public."
            )
        ],
        OCR,
    )
    assert trouve[0] == 2
    assert trouve[1] > 0.9


def test_localiser_departage_les_formulaires_par_l_ordre():
    trouves = localiser(
        [
            "Grand débat national – formulaire\nVos propositions : plus de trains",
            "Grand débat national – formulaire\nVos propositions : moins de taxes",
        ],
        OCR,
    )
    assert [t[0] for t in trouves] == [5, 7]


def test_localiser_sans_ocr_ressemblant():
    assert localiser(["Texte collé que l'OCR n'a pas lu du tout."], OCR) == [None]


HTR = [
    "Cahier citoyen",
    "Je demande le retablisement de",
    "lisf et la bausse de la csg sur",
    "les petites retraites. Merci",
]
MANUSCRIT = (
    "Je demande le rétablissement de l'ISF et la baisse de la CSG sur les "
    "petites retraites. Merci."
)


def test_localiser_un_manuscrit_sous_son_seuil():
    assert localiser([MANUSCRIT], HTR, [0.99]) == [None]
    ((ligne, ressemblance),) = localiser([MANUSCRIT], HTR, [0.45])
    assert ligne == 1
    assert 0.45 <= ressemblance < 0.99


def test_lecture_htr(tmp_path):
    (tmp_path / "a.jsonl").write_text(
        '{"page": 3, "lignes": [{"texte": "Bonjour", "cadre": [1, 2, 3, 4]}]}\n',
        encoding="utf-8",
    )
    lues = lecture_htr(tmp_path, "a.pdf")
    assert list(lues) == [3]
    texte, cadre = lues[3][0]
    assert texte == "Bonjour"
    assert (cadre.y0, cadre.y1) == (2, 4)
    assert lecture_htr(tmp_path, "b.pdf") == {}
    assert lecture_htr(None, "a.pdf") == {}


def test_mesurer_manuscrits(tmp_path):
    (tmp_path / "a.jsonl").write_text(
        '{"page": 2, "lignes": []}\n{"page": 3, "lignes": []}\n', encoding="utf-8"
    )
    alignement = [
        {
            "insee": "1",
            "genre": "manuscrit",
            "source": "htr",
            "fichier": "a.pdf",
            "page": 2,
            "y0": 100.0,
        },
        {
            "insee": "1",
            "genre": "manuscrit",
            "source": "htr",
            "fichier": "a.pdf",
            "page": 3,
            "y0": 500.0,
        },
        {
            "insee": "1",
            "genre": "manuscrit",
            "source": "",
            "fichier": "",
            "page": "",
            "y0": "",
        },
        {
            "insee": "1",
            "genre": "mail",
            "source": "ocr",
            "fichier": "a.pdf",
            "page": 1,
            "y0": 50.0,
        },
        {
            "insee": "2",
            "genre": "manuscrit",
            "source": "htr",
            "fichier": "b.pdf",
            "page": 1,
            "y0": 80.0,
        },
    ]
    notes = [
        {"fichier": "a.pdf", "page": 2, "y0": 110.0, "etiquette": DEBUT},
        {"fichier": "a.pdf", "page": 3, "y0": 80.0, "etiquette": DEBUT},
        {"fichier": "a.pdf", "page": 1, "y0": 50.0, "etiquette": DEBUT},
        {"fichier": "a.pdf", "page": 2, "y0": 300.0, "etiquette": "autre"},
    ]
    precision, rappel, placés, ref, total = mesurer_manuscrits(
        alignement, {"1"}, {"1": ["a.pdf"], "2": ["b.pdf"]}, notes, tmp_path
    )
    # page 1 non lue par l'HTR : hors référence ; page 3 : placé trop bas
    assert (placés, ref, total) == (2, 2, 3)
    assert (precision, rappel) == (0.5, 0.5)
