"""Relecture inversée : ce qui reste à masquer, sur des cadres construits."""

from anonymisation.masquage import a_masquer, fusionner, mesurer_relecture


def cadre(x0, y0, x1, y1, etiquette="nom", page=1, **autres):
    return {
        "fichier": "a.pdf",
        "page": page,
        "x0": x0,
        "y0": y0,
        "x1": x1,
        "y1": y1,
        "etiquette": etiquette,
        **autres,
    }


def test_fusionner_garde_le_plus_grand_cadre():
    grand = cadre(0, 0, 100, 20, "adresse")
    petit = cadre(10, 5, 40, 15)  # dans le grand
    ailleurs = cadre(0, 50, 30, 60)
    autre_page = cadre(10, 5, 40, 15, page=2)
    gardes = fusionner([petit, grand, ailleurs, autre_page])
    assert [(r["page"], r["etiquette"], r["y0"]) for r in gardes] == [
        (1, "adresse", 0),
        (1, "nom", 50),
        (2, "nom", 5),
    ]
    # identifiants stables d'une exécution à l'autre, distincts
    assert [r["id"] for r in fusionner([grand, ailleurs])] == [
        r["id"] for r in gardes[:2]
    ]
    assert len({r["id"] for r in gardes}) == 3


def test_a_masquer_retire_les_retablis_et_ajoute_les_oublis():
    a, b, c = sorted(
        fusionner([cadre(0, 0, 50, 10), cadre(0, 20, 50, 30), cadre(0, 40, 200, 80)]),
        key=lambda r: r["y0"],
    )
    retablis = [
        {**a, "id": a["id"]},
        # cadre rétabli sous un autre identifiant, au même endroit
        cadre(0, 19, 51, 31, id="ancien"),
        # petit cadre rétabli dans un grand : le grand reste masqué
        cadre(0, 40, 20, 50, id="petit"),
    ]
    oubli = cadre(300, 300, 350, 310, "téléphone", id="note")
    masques = a_masquer([a, b, c], retablis, [oubli])
    assert [(m["y0"], m["origine"]) for m in masques] == [
        (40, "repérage"),
        (300, "relecture"),
    ]


def test_mesurer_relecture():
    a, b, c, d = sorted(
        fusionner([cadre(0, y, 50, y + 10) for y in (0, 20, 40, 60)]),
        key=lambda r: r["y0"],
    )
    oubli = cadre(300, 300, 350, 310)
    deja_couvert = cadre(0, 40, 50, 50)  # une note sur un repérage gardé
    precision, rappel, pages = mesurer_relecture(
        [a, b, c, d], [a], [oubli, deja_couvert], {("a.pdf", 1)}
    )
    assert (precision, rappel, pages) == (3 / 4, 3 / 4, 1)
    assert mesurer_relecture([a], [], [], set()) is None
