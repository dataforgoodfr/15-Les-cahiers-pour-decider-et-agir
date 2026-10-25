"""Tâche « paires » de l'outil d'annotation, et accord des annotateurs."""

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from urllib.parse import quote

import pytest

from annotation.__main__ import application
from annotation.carnet import Carnet
from annotation.corpus import Corpus
from annotation.metadonnees import Metadonnees
from annotation.paires import Journal, etat, kappa, litiges, retenus
from classement.paires.__main__ import COLONNES
from classement.paires.accord import couples

MEME, SUJET, SANS = "même proposition", "même sujet, mesure différente", "sans rapport"


@pytest.fixture
def serveur(tmp_path):
    chemin = tmp_path / "paires.csv"
    lignes = [",".join(COLONNES)]
    for n in (1, 2):
        lignes.append(
            f"{n},test,1,0.5,17001,A,1,1,Fiscalité,Rétablir l'ISF.,"
            "17002,B,1,1,,Taxer les grandes fortunes."
        )
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    (tmp_path / "versement").mkdir()
    (tmp_path / "typage").mkdir()
    journal = Journal(tmp_path / "paires.jsonl")
    http = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        application(
            Corpus(tmp_path / "versement", tmp_path / "typage"),
            Carnet(tmp_path / "notes.jsonl"),
            tmp_path / "listes",
            Metadonnees(tmp_path / "donnees"),
            chemin,
            journal,
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
        return json.loads(reponse.read())


def test_l_annotateur_ne_voit_ni_tranche_ni_similarite_ni_les_autres(serveur):
    base, _ = serveur
    appeler(
        f"{base}/api/paires/juger",
        {"paire": "1", "annotateur": "Léa", "jugement": MEME},
    )
    vue = appeler(f"{base}/api/paires?annotateur={quote('Marc')}")
    assert vue["paires"][0] == {
        "paire": "1",
        "a": {"contexte": "Fiscalité", "texte": "Rétablir l'ISF."},
        "b": {"contexte": "", "texte": "Taxer les grandes fortunes."},
    }
    assert vue["miens"] == {}
    assert appeler(f"{base}/api/paires?annotateur={quote('Léa')}")["miens"] == {
        "1": MEME
    }


def test_seul_un_tiers_adjuge_un_litige(serveur):
    base, journal = serveur
    juger = f"{base}/api/paires/juger"
    appeler(juger, {"paire": "1", "annotateur": "Léa", "jugement": MEME})
    appeler(juger, {"paire": "1", "annotateur": "Marc", "jugement": SUJET})
    assert appeler(f"{base}/api/paires?annotateur={quote('Léa')}")["litiges"] == []
    (litige,) = appeler(f"{base}/api/paires?annotateur={quote('Inès')}")["litiges"]
    assert litige == {"paire": "1", "jugements": [MEME, SUJET], "adjudication": None}
    with pytest.raises(urllib.error.HTTPError):
        appeler(
            juger,
            {
                "paire": "1",
                "annotateur": "Léa",
                "jugement": MEME,
                "role": "adjudication",
            },
        )
    with pytest.raises(urllib.error.HTTPError):
        appeler(
            juger,
            {
                "paire": "2",
                "annotateur": "Inès",
                "jugement": MEME,
                "role": "adjudication",
            },
        )
    appeler(
        juger,
        {"paire": "1", "annotateur": "Inès", "jugement": SUJET, "role": "adjudication"},
    )
    jugements, adjudications = etat(journal.evenements())
    assert retenus(jugements, adjudications) == {"1": SUJET}


def test_un_jugement_vide_retire_le_precedent(tmp_path):
    journal = Journal(tmp_path / "j.jsonl")
    journal.juger("1", "Léa", MEME)
    journal.juger("1", "Léa", None)
    jugements, _ = etat(journal.evenements())
    assert jugements == {"1": {}}
    with pytest.raises(ValueError):
        journal.juger("1", "Léa", "peut-être")


def test_les_deux_premiers_annotateurs_font_le_litige():
    jugements = {"1": {"Léa": MEME, "Marc": MEME, "Inès": SANS}, "2": {"Léa": MEME}}
    assert litiges(jugements) == {}
    assert retenus(jugements, {}) == {"1": MEME}


def test_kappa_et_couples():
    assert kappa([(MEME, MEME), (SANS, SANS)]) == 1
    assert kappa([(MEME, SANS), (SANS, MEME)]) == -1
    assert kappa([]) is None
    jugements = {"1": {"Marc": MEME, "Léa": SANS}}
    assert couples(jugements) == {("Léa", "Marc"): [(SANS, MEME)]}
