import json
import tempfile
from datetime import date
from io import StringIO
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase

from territoires.models import Commune, Departement, Region

from . import noms
from .models import Contribution, Document, Page, Rattachement, Run, Transcription


def bourg_en_bresse():
    region = Region.objects.create(code="84", nom="Auvergne-Rhône-Alpes")
    ain = Departement.objects.create(code="01", nom="Ain", region=region)
    return Commune.objects.create(
        code="01053", type="COM", nom="Bourg-en-Bresse", departement=ain
    )


class NomsTests(TestCase):
    def test_cahier_citoyen(self):
        commune = bourg_en_bresse()
        document = noms.document("CC_01000_190304_01053_MD_15462.pdf")
        self.assertEqual(document.categorie, "CC")
        self.assertEqual(document.mode, "MD")
        self.assertEqual(document.code_postal, "01000")
        self.assertEqual(document.date_depot, date(2019, 3, 4))
        self.assertEqual(document.numero, 15462)
        self.assertEqual(document.commune, commune)

    def test_suffixe_du_code_ignore(self):
        commune = bourg_en_bresse()
        document = noms.document("CC_01000_190304_01053s_MD_15462.pdf")
        self.assertEqual(document.code_insee, "01053S")
        self.assertEqual(document.commune, commune)

    def test_courrier_sans_code_insee(self):
        document = noms.document("CO_01000_190215_D_02389.pdf")
        self.assertEqual(document.categorie, "CO")
        self.assertEqual(document.mode, "D")
        self.assertEqual(document.code_insee, "")
        self.assertIsNone(document.commune)

    def test_commune_non_renseignee(self):
        document = noms.document("CC_01000_190304_00000_MD_15462.pdf")
        self.assertIsNone(document.commune)

    def test_commune_absente_du_referentiel(self):
        document = noms.document("CC_01000_190304_01999_MD_15462.pdf")
        self.assertEqual(document.code_insee, "01999")
        self.assertIsNone(document.commune)

    def test_nom_hors_convention(self):
        document = noms.document("scan 12.pdf")
        self.assertEqual(document.fichier, "scan 12.pdf")
        self.assertEqual(document.categorie, "")


class ModelesTests(TestCase):
    def setUp(self):
        self.document = Document.objects.create(
            fichier="CC_01000_190304_01053_MD_15462.pdf", categorie="CC"
        )
        for numero in range(1, 5):
            Page.objects.create(document=self.document, numero=numero)
        self.run = Run.objects.create(
            genre="delimitation", libelle="à la main", auteur="test", actif=True
        )

    def test_pages_d_une_contribution(self):
        contribution = Contribution.objects.create(
            run=self.run, document=self.document, rang=1, page_debut=2, page_fin=3
        )
        self.assertEqual([p.numero for p in contribution.pages], [2, 3])

    def test_un_seul_run_actif_par_genre(self):
        Run.objects.create(genre="anonymisation", libelle="a", auteur="t", actif=True)
        with self.assertRaises(IntegrityError):
            Run.objects.create(
                genre="delimitation", libelle="b", auteur="t", actif=True
            )

    def test_la_fin_suit_le_debut(self):
        with self.assertRaises(IntegrityError):
            Contribution.objects.create(
                run=self.run, document=self.document, rang=1, page_debut=3, page_fin=2
            )

    def test_deux_runs_delimitent_le_meme_document(self):
        autre = Run.objects.create(genre="delimitation", libelle="règles", auteur="t")
        for run in (self.run, autre):
            Contribution.objects.create(
                run=run, document=self.document, rang=1, page_debut=1, page_fin=1
            )
        self.assertEqual(self.document.contributions.count(), 2)

    def test_deux_transcriptions_de_la_meme_page(self):
        page = self.document.pages.get(numero=1)
        for libelle in ("htr a", "htr b"):
            run = Run.objects.create(genre="transcription", libelle=libelle, auteur="t")
            Transcription.objects.create(run=run, page=page, texte="…", qualite=0.8)
        self.assertEqual(page.transcriptions.count(), 2)

    def test_une_transcription_par_run_et_par_page(self):
        run = Run.objects.create(genre="transcription", libelle="htr", auteur="t")
        page = self.document.pages.get(numero=1)
        Transcription.objects.create(run=run, page=page)
        with self.assertRaises(IntegrityError):
            Transcription.objects.create(run=run, page=page)

    def test_qualite_entre_0_et_1(self):
        run = Run.objects.create(genre="transcription", libelle="htr", auteur="t")
        with self.assertRaises(IntegrityError):
            Transcription.objects.create(
                run=run, page=self.document.pages.get(numero=1), qualite=87
            )

    def test_cahier_concatene(self):
        commune = bourg_en_bresse()
        Rattachement.objects.create(
            document=self.document, page_debut=3, code_insee="01053", commune=commune
        )
        self.assertEqual(self.document.rattachements.get().commune, commune)


class AdminTests(TestCase):
    def test_pages_de_l_admin(self):
        document = Document.objects.create(fichier="CO_01000_190215_D_02389.pdf")
        run = Run.objects.create(genre="delimitation", libelle="r", auteur="t")
        Contribution.objects.create(
            run=run, document=document, rang=1, page_debut=1, page_fin=1
        )
        self.client.force_login(User.objects.create_superuser("admin"))
        for url in [
            "/admin/cahiers/document/",
            f"/admin/cahiers/document/{document.pk}/change/",
            "/admin/cahiers/page/",
            "/admin/cahiers/run/",
            "/admin/cahiers/transcription/",
            "/admin/cahiers/contribution/",
        ]:
            self.assertEqual(self.client.get(url).status_code, 200, url)


FICHIER = "CC_01000_190304_01053_MD_15462.pdf"


def sorties_d_analyse(dossier: Path):
    """Des sorties d'analyse/ pour un cahier de 4 pages, concaténé en p. 3."""
    fichiers = {
        "typage/departements/BnF_GDN_01_PDF.csv": (
            "fichier,page,type_page,encre,qualite,mots,page_de_service\n"
            f"{FICHIER},1,dactylographiée,0.01,0.7,7,1\n"
            f"{FICHIER},2,manuscrite,0.05,0.1,3,0\n"
            f"{FICHIER},3,manuscrite,0.05,0.1,3,0\n"
            f"{FICHIER},4,vierge,0,0,0,1\n"
        ),
        "orientation/pages_tournees.csv": (
            f"fichier,pages,tournees,pages_tournees\n{FICHIER},4,2,p2 p3\n"
        ),
        "ouvertures/ouvertures.csv": f"fichier,page\n{FICHIER},2\n",
        "concatenes/concatenes.csv": (
            "fichier,pages,pages_de_garde,categorie,autres_communes,"
            "pages_autres_communes,gardes_illisibles,desordre\n"
            f"{FICHIER},4,2,concatene,p3:01024,2,,\n"
        ),
    }
    for chemin, contenu in fichiers.items():
        (dossier / chemin).parent.mkdir(parents=True, exist_ok=True)
        (dossier / chemin).write_text(contenu, encoding="utf-8")
    notes = [
        {"type": "note", "fichier": FICHIER, "page": 2, "etiquette": "nom"},
        {
            "type": "qualification",
            "fichier": FICHIER,
            "page": 3,
            "champ": "rotation",
            "valeur": 270,
        },
        {
            "type": "qualification",
            "fichier": FICHIER,
            "page": 2,
            "champ": "type",
            "valeur": "mixte",
        },
    ]
    (dossier / "annotation").mkdir()
    (dossier / "annotation" / "notes.jsonl").write_text(
        "".join(json.dumps(n) + "\n" for n in notes), encoding="utf-8"
    )


class ChargerCorpusTests(TestCase):
    def charger(self):
        with tempfile.TemporaryDirectory() as dossier:
            sorties_d_analyse(Path(dossier))
            call_command("charger_corpus", "--analyse", dossier, stdout=StringIO())

    def test_documents_et_pages(self):
        commune = bourg_en_bresse()
        self.charger()
        document = Document.objects.get(fichier=FICHIER)
        self.assertEqual(document.commune, commune)
        self.assertEqual(document.nombre_pages, 4)
        pages = {p.numero: p for p in document.pages.all()}
        self.assertTrue(pages[1].service)
        self.assertEqual(pages[1].type, "dactylographiee")
        self.assertTrue(pages[2].ouverture)

    def test_la_main_l_emporte_sur_la_mesure(self):
        self.charger()
        pages = {p.numero: p for p in Document.objects.get().pages.all()}
        self.assertEqual(pages[2].type, "mixte")
        self.assertEqual(pages[2].rotation, 90)
        self.assertEqual(pages[3].rotation, 270)

    def test_rattachement_hors_referentiel(self):
        self.charger()
        rattachement = Rattachement.objects.get()
        self.assertEqual(
            (rattachement.page_debut, rattachement.code_insee), (3, "01024")
        )
        self.assertIsNone(rattachement.commune)

    def test_relancer_garde_les_runs(self):
        self.charger()
        document = Document.objects.get()
        Page.objects.filter(document=document, numero=2).update(texte="couche")
        run = Run.objects.create(genre="delimitation", libelle="r", auteur="t")
        Contribution.objects.create(
            run=run, document=document, rang=1, page_debut=2, page_fin=3
        )
        self.charger()
        self.assertEqual(Page.objects.count(), 4)
        self.assertEqual(Rattachement.objects.count(), 1)
        self.assertEqual(document.pages.get(numero=2).texte, "couche")
        self.assertEqual(document.contributions.count(), 1)


DELIMITATION = (
    "fichier,rang,page_debut,x_debut,y_debut,page_fin,x_fin,y_fin,fin,publiable\n"
    f"{FICHIER},1,1,40.0,100.0,2,300.0,500.0,notée,1\n"
    f"{FICHIER},2,2,40.0,520.0,3,,,fin du cahier,0\n"
    "CC_99999_190304_99999_MD_00001.pdf,1,1,40.0,100.0,1,,,fin du cahier,1\n"
)


class ChargerContributionsTests(TestCase):
    def setUp(self):
        self.document = Document.objects.create(fichier=FICHIER, categorie="CC")

    def charger(self):
        with tempfile.TemporaryDirectory() as dossier:
            (Path(dossier) / "delimitation").mkdir()
            (Path(dossier) / "delimitation" / "contributions.csv").write_text(
                DELIMITATION, encoding="utf-8"
            )
            sortie = StringIO()
            call_command("charger_contributions", "--analyse", dossier, stdout=sortie)
        return sortie.getvalue()

    def test_contributions_du_run_a_la_main(self):
        sortie = self.charger()
        premiere, seconde = self.document.contributions.all()
        self.assertEqual(
            (premiere.page_debut, premiere.x_debut, premiere.y_debut), (1, 40.0, 100.0)
        )
        self.assertEqual((premiere.page_fin, premiere.x_fin), (2, 300.0))
        self.assertTrue(premiere.publiable)
        self.assertIsNone(seconde.y_fin)
        self.assertFalse(seconde.publiable)
        self.assertTrue(premiere.run.actif)
        self.assertIn("ignorées : CC_99999", sortie)

    def test_relancer_remplace_le_run_sans_toucher_aux_autres(self):
        autre = Run.objects.create(genre="delimitation", libelle="règles", auteur="t")
        Contribution.objects.create(
            run=autre, document=self.document, rang=1, page_debut=1, page_fin=1
        )
        self.charger()
        self.charger()
        self.assertEqual(Run.objects.count(), 2)
        self.assertEqual(self.document.contributions.count(), 3)
