"""Tâche « sous-thèmes » de l'outil d'annotation, liste à revoir et accord."""

import csv
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from urllib.parse import quote

import pymupdf
import pytest

from annotation.__main__ import application
from annotation.carnet import Carnet
from annotation.corpus import Corpus
from annotation.metadonnees import Metadonnees
from annotation.paires import Journal
from annotation.themes import JournalThemes, etat, grille
from classement.themes.accord import par_contribution, scores
from classement.themes.revue import COLONNES, situer

ISF, RIC, ECOLE = "Rétablissement de l'ISF", "RIC", "École, égalité d'accès"


def ligne(proposition, numero, texte, contexte=""):
    return {
        "proposition": proposition,
        "contribution": "17001-1",
        "commune": "A",
        "numero": numero,
        "contexte": contexte,
        "texte": texte,
        "pdf": "edition.pdf",
        "page": 1,
        "largeur": 595,
        "hauteur": 842,
        "cadres": json.dumps([[72, 100, 200, 112]]),
    }


@pytest.fixture
def revue(tmp_path):
    chemin = tmp_path / "revue.csv"
    with chemin.open("w", encoding="utf-8", newline="") as f:
        ecrire = csv.DictWriter(f, COLONNES)
        ecrire.writeheader()
        ecrire.writerow(ligne("17001-1-1", 1, "Rétablir l'ISF.", "Fiscalité :"))
        ecrire.writerow(ligne("17001-1-2", 2, "Instaurer le RIC."))
    return chemin


@pytest.fixture
def serveur(tmp_path, revue):
    (tmp_path / "versement").mkdir()
    (tmp_path / "typage").mkdir()
    pdf = tmp_path / "chabin"
    pdf.mkdir()
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 110), "Rétablir l'ISF.")
    doc.save(pdf / "edition.pdf")
    journal = JournalThemes(tmp_path / "themes.jsonl")
    http = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        application(
            Corpus(tmp_path / "versement", tmp_path / "typage"),
            Carnet(tmp_path / "notes.jsonl"),
            tmp_path / "listes",
            Metadonnees(tmp_path / "donnees"),
            tmp_path / "paires.csv",
            Journal(tmp_path / "paires.jsonl"),
            revue,
            journal,
            pdf,
        ),
    )
    threading.Thread(target=http.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{http.server_address[1]}", journal
    http.shutdown()


def appeler(url, corps=None):
    donnees = None if corps is None else json.dumps(corps).encode()
    requete = urllib.request.Request(
        url, data=donnees, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(requete) as reponse:
        return (
            reponse.read()
            if corps is None and "image" in url
            else json.loads(reponse.read())
        )


def test_l_annotateur_voit_la_contribution_mais_pas_les_autres(serveur):
    base, _ = serveur
    appeler(
        f"{base}/api/themes/annoter",
        {"proposition": "17001-1-1", "annotateur": "Léa", "sous_themes": [ISF]},
    )
    vue = appeler(f"{base}/api/themes?annotateur={quote('Marc')}")
    (contribution,) = vue["contributions"]
    assert contribution["pdf"] == "edition.pdf"
    assert [p["proposition"] for p in contribution["propositions"]] == [
        "17001-1-1",
        "17001-1-2",
    ]
    assert contribution["propositions"][0]["contexte"] == "Fiscalité :"
    assert contribution["propositions"][0]["cadres"] == [[72, 100, 200, 112]]
    assert vue["miens"] == {}
    lea = appeler(f"{base}/api/themes?annotateur={quote('Léa')}")
    assert lea["miens"] == {"17001-1-1": {"sous_themes": [ISF], "mal_coupee": False}}


def test_la_page_de_l_edition_est_servie_mais_pas_un_autre_pdf(serveur):
    base, _ = serveur
    image = appeler(f"{base}/api/themes/image?pdf=edition.pdf&page=1&largeur=800")
    assert image[:2] == b"\xff\xd8"
    with pytest.raises(urllib.error.HTTPError):
        appeler(f"{base}/api/themes/image?pdf=autre.pdf&page=1&largeur=800")


def test_un_sous_theme_hors_grille_ou_une_proposition_inconnue_est_refuse(serveur):
    base, _ = serveur
    for corps in (
        {"proposition": "17001-1-1", "annotateur": "Léa", "sous_themes": ["Inconnu"]},
        {"proposition": "99999-1-1", "annotateur": "Léa", "sous_themes": []},
    ):
        with pytest.raises(urllib.error.HTTPError):
            appeler(f"{base}/api/themes/annoter", corps)


def test_la_derniere_annotation_l_emporte_et_aucune_case_compte(tmp_path):
    journal = JournalThemes(tmp_path / "themes.jsonl")
    journal.annoter("1", "Léa", [ISF])
    journal.annoter("1", "Léa", [], mal_coupee=True)
    journal.annoter("2", "Léa", [RIC])
    journal.annoter("2", "Léa", None)
    assert etat(journal.evenements()) == {
        "1": {"Léa": {"sous_themes": set(), "mal_coupee": True}},
        "2": {},
    }


def test_la_grille_reprend_chaque_sous_theme_une_fois():
    noms = [s for g in grille() for s in g["sous_themes"]]
    assert len(noms) == len(set(noms))
    assert {ISF, RIC, ECOLE} <= set(noms)


def test_chaque_proposition_est_retrouvee_dans_l_ordre():
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Une autre contribution sur le RIC.")
    page.insert_text((72, 200), "- Rétablir l'impôt")
    page.insert_text((72, 215), "sur la fortune ; instaurer le RIC.")
    places = situer(
        doc,
        "- Rétablir l'impôt sur la fortune ; instaurer le RIC.",
        [
            {"texte": "Rétablir l'impôt sur la fortune"},
            {"texte": "instaurer le RIC."},
        ],
    )
    cadres = [json.loads(p["cadres"]) for p in places]
    assert len(cadres[0]) == 2  # sur deux lignes
    assert cadres[1][0][1] > 200  # pas le RIC de la contribution précédente


def test_precision_rappel_et_contribution_reunie():
    vrai = {"1": {ISF}, "2": set()}
    predit = {"1": {ISF, RIC}, "2": {ECOLE}}
    s = scores(predit, vrai, ["1", "2"])
    assert (s["precision"], s["rappel"]) == (1 / 3, 1.0)
    humains = {"Léa": {"a-1": {ISF}, "a-2": {RIC}, "b-1": {ECOLE}}}
    propositions = {"a": {"a-1", "a-2"}, "b": {"b-1", "b-2"}}
    assert par_contribution(humains, propositions, set()) == {"Léa": {"a": {ISF, RIC}}}
    assert par_contribution(humains, propositions, {"b-2"})["Léa"]["b"] == {ECOLE}
