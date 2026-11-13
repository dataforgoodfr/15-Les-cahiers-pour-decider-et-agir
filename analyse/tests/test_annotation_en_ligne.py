"""Le serveur en ligne : paires et sous-thèmes seulement, annotateur déduit du jeton."""

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from annotation.__main__ import application, lire_jetons
from annotation.paires import Journal
from annotation.themes import JournalThemes
from classement.paires.__main__ import COLONNES

LEA = "a" * 16
MARC = "b" * 16
MEME = "même proposition"


@pytest.fixture
def serveur(tmp_path):
    chemin = tmp_path / "paires.csv"
    chemin.write_text(
        ",".join(COLONNES) + "\n1,test,1,0.5,17001,A,1,1,Fiscalité,Rétablir l'ISF.,"
        "17002,B,1,1,,Taxer les grandes fortunes.\n",
        encoding="utf-8",
    )
    journal = Journal(tmp_path / "paires.jsonl")
    http = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        application(
            None,
            None,
            None,
            None,
            chemin,
            journal,
            tmp_path / "revue.csv",
            JournalThemes(tmp_path / "themes.jsonl"),
            tmp_path,
            jetons={LEA: "Léa", MARC: "Marc"},
        ),
    )
    threading.Thread(target=http.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{http.server_address[1]}", journal
    http.shutdown()


def appeler(url, corps=None, jeton=None):
    entetes = {"Content-Type": "application/json"}
    if jeton:
        entetes["X-Jeton"] = jeton
    donnees = None if corps is None else json.dumps(corps).encode()
    requete = urllib.request.Request(url, data=donnees, headers=entetes)
    with urllib.request.urlopen(requete) as reponse:
        return reponse.read()


def statut(url, corps=None, jeton=None):
    try:
        appeler(url, corps, jeton)
    except urllib.error.HTTPError as e:
        return e.code
    return 200


def test_le_prenom_vient_du_jeton_pas_de_la_requete(serveur):
    base, journal = serveur
    appeler(
        f"{base}/api/paires/juger",
        {"paire": "1", "annotateur": "Marc", "jugement": MEME},
        LEA,
    )
    assert [e["annotateur"] for e in journal.evenements()] == ["Léa"]
    vue = json.loads(appeler(f"{base}/api/paires?annotateur=L%C3%A9a", jeton=MARC))
    assert vue["annotateur"] == "Marc"
    assert vue["miens"] == {}
    vue = json.loads(appeler(f"{base}/api/paires?j={LEA}"))
    assert vue["miens"] == {"1": MEME}


def test_sans_jeton_connu_rien_ne_s_ecrit(serveur):
    base, journal = serveur
    assert statut(f"{base}/api/paires") == 403
    assert statut(f"{base}/api/paires", jeton="c" * 16) == 403
    corps = {"paire": "1", "annotateur": "Léa", "jugement": MEME}
    assert statut(f"{base}/api/paires/juger", corps) == 403
    assert journal.evenements() == []


def test_ni_les_cahiers_ni_le_carnet_ne_sont_servis(serveur):
    base, _ = serveur
    for chemin in ("/", "/statique/index.html", "/statique/app.js", "/api/cahiers"):
        assert statut(f"{base}{chemin}", jeton=LEA) == 404
    assert statut(f"{base}/api/notes", {"fichier": "x"}, LEA) == 404
    assert statut(f"{base}/paires") == 200
    assert statut(f"{base}/statique/themes.js") == 200


def test_jetons_mal_formes():
    assert lire_jetons(f" {LEA}:Léa , {MARC}:Marc,") == {LEA: "Léa", MARC: "Marc"}
    for texte in ("", "court:Léa", f"{LEA}:", f"{LEA}:Léa,{LEA}:Marc"):
        with pytest.raises(ValueError):
            lire_jetons(texte)
