"""Cahiers à formulaire, sur des pages construites."""

from anonymisation.formulaires import pages_de_formulaire, pages_ecrites

FORMULAIRE = ["vos nom et prenom", "votre adresse postale", "vos propositions ici"]


def test_formulaire_noye_parmi_des_lettres():
    lettres = [[f"une lettre libre numero {i}"] for i in range(30)]
    pages = lettres[:10] + [FORMULAIRE + ["ecrit a la main"]] * 4 + lettres[10:]
    assert pages_de_formulaire(pages) == {10, 11, 12, 13}


def test_trois_exemplaires_ne_suffisent_pas():
    assert pages_de_formulaire([FORMULAIRE] * 3) == set()


def test_un_pied_de_page_repete_n_est_pas_un_formulaire():
    pages = [[f"lettre {i} assez longue", "imprime en mairie de x"] for i in range(8)]
    assert pages_de_formulaire(pages) == set()


def test_lignes_courtes_ignorees():
    assert pages_de_formulaire([["nom", "prenom", "adresse"]] * 6) == set()


def test_pages_ecrites(tmp_path):
    (tmp_path / "t.csv").write_text(
        "fichier,page,type_page,page_de_service\n"
        "a.pdf,1,dactylographiée,1\n"
        "a.pdf,2,manuscrite,0\n"
        "a.pdf,3,vierge,0\n"
        "a.pdf,4,dactylographiée,0\n",
        encoding="utf-8",
    )
    assert pages_ecrites([tmp_path], {("a.pdf", 4)}) == {"a.pdf": [2]}
