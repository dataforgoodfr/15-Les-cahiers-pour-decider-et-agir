"""Débuts de contributions, sur des pages construites pour le test."""

from contributions.regles import (
    courriels,
    debuts,
    evaluer,
    gabarit,
    public,
    ressemble,
)

COURRIEL = ["De : Jean", "Envoyé : lundi", "À : mairie", "Objet : doléances"]
FORMULAIRE = [
    "Quelles sont vos propositions pour la fiscalité ?",
    "réponse",
    "Quelles sont vos propositions pour la démocratie ?",
    "réponse",
    "Quelles sont vos propositions pour l'écologie ?",
]


def test_un_courriel_par_bloc_expediteur_et_objet():
    page = ["Bonjour", *COURRIEL, "texte", "texte", "texte", "texte", *COURRIEL]
    assert courriels(page) == [1, 9]


def test_un_bloc_sans_objet_n_est_pas_un_courriel():
    assert courriels(["De : Jean", "Date : lundi", "texte"]) == []


def test_un_courriel_transfere_commence_au_message_d_origine():
    page = [*COURRIEL, "", "-----Message d'origine-----", *COURRIEL, "texte"]
    assert courriels(page) == [6]


MAIRIE = ["De : contact@mairie-exemple.fr", "Envoyé : mardi", "Objet : TR: doléances"]


def test_un_envoi_de_mairie_n_est_pas_une_contribution():
    # transfert direct : le citoyen, pas la mairie
    page = [*MAIRIE, "", *COURRIEL, "texte"]
    assert courriels(page) == [4]
    # la mairie écrit quelques lignes avant le courriel du citoyen
    page = [*MAIRIE, "Bonjour,", "voici une contribution", "reçue", "hier", *COURRIEL]
    assert courriels(page) == [7]
    # seul sur la page, le courriel de la mairie reste un début
    assert courriels([*MAIRIE, "texte"]) == [0]


def test_un_courriel_en_tete_de_page():
    # un bloc à la ligne 0 ne doit pas être pris pour un transfert du suivant
    page = [*COURRIEL, "a", "b", "c", "d", *COURRIEL]
    assert courriels(page) == [0, 8]


def test_gabarit_repere_chaque_formulaire():
    pages = [["Mairie de X", *FORMULAIRE], FORMULAIRE, ["suite"], FORMULAIRE]
    assert gabarit(pages) == [(0, 1, "exact"), (1, 0, "exact"), (3, 0, "exact")]


def test_ressemble_a_l_ocr_pres():
    modele = "cahier de doléances"
    for ligne in (
        "cahïer de doléances",
        "cahier dedoléanœs",
        "cahier de doléances ç< jjl.",
    ):
        assert ressemble(ligne, modele), ligne
    for ligne in ("doléances", "rihirr tir nnteinm", "", "monsieur le maire,"):
        assert not ressemble(ligne, modele), ligne
    # cité au milieu d'une phrase, le modèle n'en ouvre pas une
    assert not ressemble("sur le site (onglet cahier de doléances)", modele)


def test_gabarit_un_seul_en_tete_ressemblant_par_page():
    tete = "Grand débat national"
    pages = [[tete, *FORMULAIRE] for _ in range(4)]
    # l'en-tête abîmé l'emporte sur la citation, pourtant plus proche par la fin
    pages.append(
        ["Grand débat nadonal", "du Grand débat national organisé", *FORMULAIRE]
    )
    assert [d for d in gabarit(pages) if d[0] == 4] == [(4, 0, "ressemblant")]


def test_gabarit_retrouve_un_en_tete_abime():
    tete = "Cahier de doléances de la commune"
    pages = [[tete, *FORMULAIRE] for _ in range(4)]
    pages.append(["Cahïer de doléanœs de la commune", *FORMULAIRE])
    # en-tête méconnaissable : les questions du formulaire suffisent
    pages.append(["xjq vv~", FORMULAIRE[0], "réponse", FORMULAIRE[2]])
    pages.append(["Une lettre libre", "sans rien du formulaire"])
    debuts_ = gabarit(pages)
    assert (4, 0, "ressemblant") in debuts_
    assert (5, 1, "compagnes") in debuts_
    assert not [d for d in debuts_ if d[0] == 6]


def test_un_en_tete_repete_n_est_pas_un_gabarit():
    pages = [["Grand débat national, contribution", f"texte {i}"] for i in range(6)]
    assert gabarit(pages) == []


def test_debuts_ajoute_le_debut_du_cahier():
    pages = [["", "Préambule du cahier"], ["texte", *COURRIEL]]
    assert debuts(pages) == [(0, 1, "début du cahier"), (1, 1, "courriel")]
    # un courriel en tête du cahier en est le début
    assert debuts([COURRIEL]) == [(0, 0, "courriel")]
    # un logo puis un courriel : le courriel ouvre le cahier
    assert debuts([["VILLE DE", "PARIS", *COURRIEL]]) == [(0, 2, "courriel")]
    # un vrai texte avant le premier courriel reste une contribution
    texte = [f"ligne {k}" for k in range(8)]
    assert debuts([[*texte, *COURRIEL]])[0] == (0, 0, "début du cahier")
    # une page manuscrite précède : la première page lue n'ouvre rien
    assert debuts(pages, debut_du_cahier=False) == [(1, 1, "courriel")]


def test_evaluer_apparie_les_debuts_proches():
    reference = [("a", 1, 100.0), ("a", 1, 400.0), ("a", 2, 50.0)]
    predits = [("a", 1, 110.0), ("a", 1, 115.0), ("a", 2, 400.0)]
    # 110 apparié à 100 ; 115 n'a plus de début libre assez proche
    assert evaluer(predits, reference) == (1 / 3, 1 / 3)
    assert evaluer([], reference) == (0.0, 0.0)


def test_evaluer_admet_l_ecart_d_un_en_tete():
    # le lecteur ouvre le formulaire en haut de son en-tête, la règle plus bas
    assert evaluer([("a", 1, 200.0)], [("a", 1, 80.0)]) == (1.0, 1.0)
    assert evaluer([("a", 1, 80.0)], [("a", 1, 200.0)]) == (1.0, 1.0)
    # mais pas au-delà d'un début trouvé voisin
    predits = [("a", 1, 80.0), ("a", 1, 150.0)]
    assert evaluer(predits, [("a", 1, 200.0)]) == (0.5, 1.0)
    # ni plus loin que la hauteur d'un en-tête
    assert evaluer([("a", 1, 80.0)], [("a", 1, 400.0)]) == (0.0, 0.0)


def test_public_juge_le_domaine_d_une_adresse():
    assert public("De : contact@mairie-exemple.fr")
    assert public("De : Mairie de Villeneuve")
    assert not public("De : Jean Villeneuve <jean.villeneuve@exemple.com>")
    assert not public("De : Jean Dupont")


def test_courriel_imprime_depuis_une_messagerie():
    page = [
        "Jean Dupont <jean.dupont@exemple.com>",
        "lundi 4 février 2019 10:12",
        "À : contact@mairie-exemple.fr",
        "Bonjour,",
        "texte",
        *MAIRIE,  # message cité plus bas : même échange
        "texte",
    ]
    assert courriels(page) == [0]
    # une adresse en haut d'une lettre, sans destinataire, n'en fait pas un courriel
    assert courriels(["jean@exemple.com", "Monsieur le Maire,", "texte"]) == []
