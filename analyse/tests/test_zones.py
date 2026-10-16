"""Zones de signature au bord des contributions."""

from anonymisation.zones import zones

LETTRE = (
    "Dupont Jean, Montendre\n"
    "Je demande le retour de l'ISF et une hausse des petites retraites, "
    "car la vie devient trop chère pour beaucoup de gens ici.\n"
    "\n"
    "Cordialement,\n"
    "J. Dupont"
)


def texte_des(texte, zones_):
    return [(texte[a:b], cote) for a, b, cote in zones_]


def test_zones_fin_et_debut():
    assert texte_des(LETTRE, zones(LETTRE, fin=2, debut=1)) == [
        ("Dupont Jean, Montendre", "début"),
        ("Cordialement,", "fin"),
        ("J. Dupont", "fin"),
    ]


def test_une_ligne_longue_arrete_la_zone():
    texte = "Une ligne bien trop longue pour être une signature, " * 3 + "\nT.S."
    assert texte_des(texte, zones(texte, fin=3, debut=1)) == [("T.S.", "fin")]


def test_contribution_toute_courte_sans_zone_de_debut():
    assert texte_des("Merci\nT.S.", zones("Merci\nT.S.", fin=2, debut=1)) == [
        ("Merci", "fin"),
        ("T.S.", "fin"),
    ]


def test_une_date_ne_compte_pas_dans_la_zone_de_debut():
    texte = (
        "29/01/19\nDupont Jean\n"
        + "Une proposition assez longue pour être le corps du texte, " * 2
    )
    assert texte_des(texte, zones(texte, fin=0, debut=1)) == [
        ("29/01/19", "début"),
        ("Dupont Jean", "début"),
    ]
