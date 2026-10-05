"""Outil d'annotation, sur un faux versement construit pour le test."""

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pymupdf
import pytest

from annotation import listes
from annotation.__main__ import application
from annotation.carnet import Carnet
from annotation.corpus import Corpus
from annotation.metadonnees import Metadonnees

FICHIER = "CC_00000_190225_00000_MD_00001.pdf"


def test_carnet_rejoue_notes_modifications_et_statuts(tmp_path):
    carnet = Carnet(tmp_path / "notes.jsonl")
    note = carnet.noter(
        {
            "fichier": "a.pdf",
            "page": "2",
            "x0": 1,
            "y0": 2,
            "x1": 1,
            "y1": 2,
            "etiquette": "date",
            "texte": "secret",
        }
    )
    autre = carnet.noter(
        {
            "fichier": "a.pdf",
            "page": 3,
            "x0": 0,
            "y0": 0,
            "x1": 5,
            "y1": 5,
            "etiquette": "remarque",
            "texte": "",
        }
    )
    carnet.modifier(note["id"], {"etiquette": "signature", "fichier": "ignoré"})
    carnet.supprimer(autre["id"])
    carnet.marquer("a.pdf", 2, "vue")
    carnet.marquer("a.pdf", 3, "a_revoir")
    carnet.marquer("a.pdf", 3, None)
    notes, statuts = carnet.etat()
    assert list(notes) == [note["id"]]
    assert notes[note["id"]]["etiquette"] == "signature"
    assert notes[note["id"]]["fichier"] == "a.pdf"
    assert notes[note["id"]]["page"] == 2
    assert statuts == {("a.pdf", 2): "vue"}
    # les positions ne portent jamais le texte des notes
    assert "texte" not in carnet.positions()[0]
    with pytest.raises(ValueError):
        carnet.marquer("a.pdf", 2, "inconnu")


def test_listes_aller_retour(tmp_path):
    elements = [{"fichier": "a.pdf", "page": 1, "marques": [{"y0": 10}]}]
    listes.ecrire(tmp_path, "essai-1", "Essai", "Regarder.", elements)
    assert listes.lire(tmp_path, "essai-1")["elements"] == elements
    assert listes.sommaire(tmp_path) == [
        {"nom": "essai-1", "titre": "Essai", "elements": 1}
    ]
    for nom in ("../secret", "inconnue"):
        with pytest.raises(KeyError):
            listes.lire(tmp_path, nom)


@pytest.fixture
def serveur(tmp_path):
    dossier = tmp_path / "versement" / "BnF_GDN_00_PDF"
    dossier.mkdir(parents=True)
    with pymupdf.open() as doc:
        for _ in range(2):
            doc.new_page(width=200, height=300).insert_text((20, 40), "Essai")
        doc.save(dossier / FICHIER)
    typage = tmp_path / "typage"
    typage.mkdir()
    (typage / "BnF_GDN_00_PDF.csv").write_text(
        "fichier,page,type_page,encre,qualite,mots,page_de_service\n"
        f"{FICHIER},1,dactylographiée,0,0,1,1\n{FICHIER},2,manuscrite,0,0,0,0\n"
    )
    carnet = Carnet(tmp_path / "annotation" / "notes.jsonl")
    http = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        application(
            Corpus(tmp_path / "versement", typage),
            carnet,
            tmp_path / "listes",
            Metadonnees(tmp_path / "donnees"),
        ),
    )
    threading.Thread(target=http.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{http.server_address[1]}", carnet
    http.shutdown()


def appeler(url, corps=None):
    donnees = None if corps is None else json.dumps(corps).encode()
    requete = urllib.request.Request(
        url, data=donnees, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(requete) as reponse:
        return reponse.headers["Content-Type"], reponse.read()


def test_serveur_sert_pages_images_et_notes(serveur):
    base, carnet = serveur
    type_, corps = appeler(f"{base}/")
    assert type_.startswith("text/html")
    _, corps = appeler(f"{base}/api/cahiers?q=00001")
    assert json.loads(corps) == [FICHIER]
    _, corps = appeler(f"{base}/api/cahier?fichier={FICHIER}")
    cahier = json.loads(corps)
    assert [p["type"] for p in cahier["pages"]] == ["dactylographiée", "manuscrite"]
    assert cahier["pages"][0]["service"] is True
    assert (cahier["pages"][0]["largeur"], cahier["pages"][0]["hauteur"]) == (200, 300)
    _, corps = appeler(f"{base}/api/lignes?fichier={FICHIER}&page=1")
    (ligne,) = json.loads(corps)
    assert ligne["texte"] == "Essai" and ligne["y0"] < 40 < ligne["y1"]
    type_, corps = appeler(f"{base}/api/image?fichier={FICHIER}&page=2&largeur=400")
    assert type_ == "image/jpeg" and corps[:2] == b"\xff\xd8"

    appeler(
        f"{base}/api/notes",
        {
            "fichier": FICHIER,
            "page": 2,
            "x0": 10,
            "y0": 20,
            "x1": 10,
            "y1": 20,
            "etiquette": "date",
            "texte": "x",
        },
    )
    appeler(f"{base}/api/statut", {"fichier": FICHIER, "page": 2, "statut": "vue"})
    _, corps = appeler(f"{base}/api/cahier?fichier={FICHIER}")
    cahier = json.loads(corps)
    assert len(cahier["notes"]) == 1
    assert cahier["statuts"] == {"2": "vue"}
    assert carnet.etat()[1] == {(FICHIER, 2): "vue"}


@pytest.mark.parametrize(
    "chemin",
    [
        "/api/cahier?fichier=../../etc/passwd",
        "/api/image?fichier=CC_00000_190225_00000_MD_00001.pdf&page=9&largeur=100",
        "/statique/../carnet.py",
        "/api/liste?nom=../x",
    ],
)
def test_serveur_refuse_ce_qui_n_est_pas_indexe(serveur, chemin):
    base, _ = serveur
    with pytest.raises(urllib.error.HTTPError) as e:
        appeler(base + chemin)
    assert e.value.code == 404


def test_serveur_refuse_une_note_sur_un_fichier_inconnu(serveur):
    base, carnet = serveur
    with pytest.raises(urllib.error.HTTPError) as e:
        appeler(
            f"{base}/api/notes",
            {
                "fichier": "autre.pdf",
                "page": 1,
                "x0": 0,
                "y0": 0,
                "x1": 0,
                "y1": 0,
                "etiquette": "date",
                "texte": "",
            },
        )
    assert e.value.code == 400
    assert carnet.evenements() == []


def test_carnet_qualifie_les_pages(tmp_path):
    carnet = Carnet(tmp_path / "notes.jsonl")
    carnet.qualifier("a.pdf", 2, "illisible", True)
    carnet.qualifier("a.pdf", 2, "page tournée", True)
    carnet.qualifier("a.pdf", 2, "illisible", False)  # décoché : on le garde
    carnet.qualifier("a.pdf", 3, "type", "mixte")
    carnet.qualifier("a.pdf", 3, "remarque", "à relire")
    carnet.qualifier("a.pdf", 0, "remarque", "cahier relié à l'envers")
    assert carnet.qualifications() == {
        ("a.pdf", 2): {
            "problemes": {"illisible": False, "page tournée": True},
            "type": None,
            "remarque": "",
        },
        ("a.pdf", 3): {"problemes": {}, "type": "mixte", "remarque": "à relire"},
        ("a.pdf", 0): {
            "problemes": {},
            "type": None,
            "remarque": "cahier relié à l'envers",
        },
    }
    # une analyse ne lit pas les remarques, qui peuvent citer le cahier
    assert "remarque" not in carnet.qualifications(remarques=False)[("a.pdf", 3)]
    for champ, valeur in (("inconnu", True), ("type", "imprimée")):
        with pytest.raises(ValueError):
            carnet.qualifier("a.pdf", 2, champ, valeur)


def test_metadonnees_lit_les_sorties_des_analyses(tmp_path):
    for chemin, contenu in {
        "orientation/pages_tournees.csv": "fichier,pages,tournees,pages_tournees\n"
        "a.pdf,9,2,p6 p7\n",
        "concatenes/concatenes.csv": "fichier,pages,pages_de_garde,categorie,"
        "autres_communes,pages_autres_communes,gardes_illisibles,desordre\n"
        "a.pdf,9,2,concatene,75056,4,p5,p3:garde_en_double\n",
        "manquantes/exemplaires.csv": "fichier,modele,pages,pages_du_modele,"
        "pages_trouvees,statut,pages_manquantes,coupure,voisine_illisible\n"
        "a.pdf,3,p8 p9,3,2,incomplet,1,0,1\n",
        "inventaires/documents.csv": "fichier,categorie,departement,code_insee,"
        "inventaires,present,pages_attendues,pages_presentes\n"
        "a.pdf,CC,75,75056,1,1,10,9\n",
    }.items():
        (tmp_path / chemin).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / chemin).write_text(contenu)
    m = Metadonnees(tmp_path)
    assert m.cahier("a.pdf") == [
        "contient le cahier d'autres communes",
        "autres communes : 75056 (4 pages)",
        "inventaire : 10 pages attendues, 9 présentes",
        "2 pages tournées détectées",
    ]
    pages = m.pages("a.pdf")
    assert pages[6] == ["tournée d'un quart de tour (orientation)"]
    assert pages[5] == ["page de garde illisible (concatenes)"]
    assert pages[3] == ["garde en double (concatenes)"]
    assert pages[8] == [
        (
            "formulaire type 3, incomplet : 1 page(s) manquante(s), "
            "page voisine illisible (manquantes)"
        )
    ]
    assert m.problemes("a.pdf") == {
        6: {"page tournée"},
        7: {"page tournée"},
        5: {"illisible"},
        3: {"doublon"},
        8: {"page manquante"},
        9: {"page manquante"},
    }
    # sans sorties d'analyse, rien n'est signalé
    vide = Metadonnees(tmp_path / "absent")
    assert vide.cahier("a.pdf") == [] and vide.pages("a.pdf") == {}


def test_serveur_qualifie_une_page(serveur):
    base, _ = serveur
    _, corps = appeler(f"{base}/api/etiquettes")
    assert "illisible" in json.loads(corps)["problemes"]
    appeler(
        f"{base}/api/qualifier",
        {"fichier": FICHIER, "page": 1, "champ": "illisible", "valeur": True},
    )
    appeler(
        f"{base}/api/qualifier",
        {"fichier": FICHIER, "page": 1, "champ": "type", "valeur": "mixte"},
    )
    _, corps = appeler(f"{base}/api/cahier?fichier={FICHIER}")
    page = json.loads(corps)["pages"][0]
    assert page["problemes"] == {"illisible": True}
    assert page["problemes_auto"] == []
    assert page["type_verifie"] == "mixte"
    assert page["type"] == "dactylographiée"  # le typage reste visible
    with pytest.raises(urllib.error.HTTPError) as e:
        appeler(
            f"{base}/api/qualifier",
            {"fichier": FICHIER, "page": 1, "champ": "type", "valeur": "imprimée"},
        )
    assert e.value.code == 400


def test_statuts_par_tache(tmp_path):
    carnet = Carnet(tmp_path / "notes.jsonl")
    carnet.marquer("a.pdf", 1, "vue", "anonymisation")
    carnet.marquer("a.pdf", 2, "vue")  # hors liste : vaut pour toutes les tâches
    carnet.marquer("a.pdf", 3, "vue", "contributions")
    assert carnet.statuts("contributions") == {("a.pdf", 2): "vue", ("a.pdf", 3): "vue"}
    assert carnet.statuts("anonymisation") == {("a.pdf", 1): "vue", ("a.pdf", 2): "vue"}
    assert len(carnet.statuts()) == 3
    assert carnet.statuts("anonymisation", exacte=True) == {("a.pdf", 1): "vue"}


def test_retablir_puis_recacher_un_reperage(serveur):
    base, carnet = serveur
    marque = {"id": "abc", "x0": 1, "y0": 2, "x1": 30, "y1": 12, "etiquette": "nom"}
    appeler(f"{base}/api/retablir", {"fichier": FICHIER, "page": 1, "marque": marque})
    _, corps = appeler(f"{base}/api/cahier?fichier={FICHIER}")
    assert json.loads(corps)["retablis"] == [[1, "abc"]]
    (retabli,) = carnet.retablis().values()
    assert (retabli["x1"], retabli["etiquette"]) == (30, "nom")
    appeler(
        f"{base}/api/retablir",
        {"fichier": FICHIER, "page": 1, "marque": marque, "retabli": False},
    )
    assert carnet.retablis() == {}


def test_une_liste_a_masquer_identifie_ses_marques(tmp_path):
    element = {"fichier": "a.pdf", "page": 1, "marques": [{"x0": 0, "y0": 0}]}
    with pytest.raises(ValueError):
        listes.ecrire(tmp_path, "l", "L", "", [element], mode="masquer")
    element["marques"][0]["id"] = "x"
    listes.ecrire(tmp_path, "l", "L", "", [element], mode="masquer")
    assert listes.lire(tmp_path, "l")["mode"] == "masquer"
