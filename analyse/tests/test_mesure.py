"""Mesure du repérage automatique, sur des cadres construits pour le test."""

from anonymisation.mesure import mesurer


def cadre(x0, y0, x1, y1, **reste):
    return {
        "fichier": "a.pdf",
        "page": 1,
        "x0": x0,
        "y0": y0,
        "x1": x1,
        "y1": y1,
    } | reste


def test_mesurer_precision_rappel_et_seule_source():
    reperes = [
        cadre(0, 0, 10, 10, etiquette="nom", source="mot"),
        cadre(0, 0, 10, 10, etiquette="nom", source="gliner"),
        cadre(50, 0, 60, 10, etiquette="nom", source="gliner"),
        cadre(100, 0, 110, 10, etiquette="adresse", source="mot"),
    ]
    retablis = [cadre(100, 0, 110, 10, etiquette="adresse", id="x")]  # fausse alerte
    notes = [
        cadre(1, 1, 9, 9, etiquette="nom"),  # déjà couverte
        cadre(200, 0, 220, 10, etiquette="signature"),  # oubli
    ]
    m = mesurer(reperes, retablis, notes)
    assert m["references"] == 3 and m["oublis"] == 1
    mot, gliner = m["sources"]["mot"], m["sources"]["gliner"]
    assert (mot["precision"], mot["couvertes"], mot["seule"]) == (0.5, 1, 0)
    assert (gliner["precision"], gliner["couvertes"], gliner["seule"]) == (1, 2, 1)
    assert m["sources"]["toutes"]["couvertes"] == 2
    assert m["rappel"]["signature"] == [0, 1]
    assert m["precision"]["adresse"] == [0, 1]
