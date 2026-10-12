from datetime import date

from django.contrib.auth.models import User
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
