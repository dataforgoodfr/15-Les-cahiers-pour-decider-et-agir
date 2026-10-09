"""Pages d'ouverture imprimées, sur des lignes construites pour le test."""

from ouvertures.ouvertures import lignes_de_page, modele, porte

COUVERTURE = "Cahier de doléances\net de propositions\nAssociation des maires 17"


def test_lignes_de_page_a_l_ocr_pres():
    assert lignes_de_page("Cahier de doléances,\n  ET de propositions.\n12") == {
        "cahier de doléances",
        "et de propositions",
    }


def test_modele_des_lignes_communes_au_departement():
    premieres = {f"c{i}.pdf": lignes_de_page(COUVERTURE) for i in range(12)}
    premieres |= {f"l{i}.pdf": {f"lettre propre au cahier {i}"} for i in range(50)}
    assert modele(premieres) == lignes_de_page(COUVERTURE)
    # sous dix cahiers, une ligne commune n'est pas un modèle
    assert modele({f"c{i}.pdf": lignes_de_page(COUVERTURE) for i in range(9)}) == set()


def test_porte_le_modele():
    lignes_modele = lignes_de_page(COUVERTURE)
    assert porte(lignes_de_page(COUVERTURE + "\nCommune de Burie"), lignes_modele)
    assert not porte(lignes_de_page("Cahier de doléances\nMa demande"), lignes_modele)
