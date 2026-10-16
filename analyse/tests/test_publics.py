"""Noms publics : commune, maire, présidents et ministres."""

from anonymisation.publics import charger_maires, est_public, publics


def test_est_public():
    noms = publics(
        [("Édouard", "Philippe"), ("Paul", "Durand")], ["La Rochelle"], {"Philippe"}
    )
    assert est_public("M. le maire Durand", noms)
    assert est_public("Édouard Philippe", noms)
    assert est_public("La Rochelle", noms)
    assert not est_public("Philippe", noms)  # un prénom seul n'est pas public
    assert not est_public("Marie Durand", noms)


def test_charger_maires():
    contenu = (
        "Liste des maires\n"
        "Code du département (Maire)\tLibellé de département (Maires)\t"
        "Code Insee de la commune\tLibellé de la commune\tNom de l'élu\t"
        "Prénom de l'élu\n"
        "01\tAin\t001\tL'Abergement-Clémenciat\tDUPONT\tMarie\n"
        "2A\tCorse-du-Sud\t004\tAjaccio\tMARTIN\tPaul\n"
        "ZA\tGuadeloupe\t101\tLes Abymes\tDURAND\tLéa\n"
        "ZN\tNouvelle-Calédonie\t801\tBelep\tPETIT\tLuc\n"
    ).encode("latin-1")
    assert charger_maires(contenu) == {
        "01001": ("Marie", "DUPONT"),
        "2A004": ("Paul", "MARTIN"),
        "97101": ("Léa", "DURAND"),
        "98801": ("Luc", "PETIT"),
    }
