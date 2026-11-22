"""Tests de l'intégration Wagtail dans l'app `cms`."""

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse

from cahiers.models import Thematique


class ThematiqueSnippetTests(TestCase):
    """Vérifie l'exposition de `Thematique` en Snippet Wagtail pour les éditeurs."""

    def setUp(self):
        self.theme = Thematique.objects.create(
            nom="Démocratie",
            slug="democratie",
            ordre=1,
            description="Description initiale du thème.",
        )
        self.sous_theme = Thematique.objects.create(
            nom="RIC",
            slug="ric",
            parent=self.theme,
            ordre=1,
            description="Description initiale du RIC.",
        )

        # Éditeur Wagtail autorisé uniquement à voir et modifier `Thematique`
        # (sans droits d'ajout ni de suppression).
        self.editeur = User.objects.create_user(
            username="editeur", password="mot-de-passe-test"
        )
        permissions = Permission.objects.filter(
            codename__in=["access_admin", "view_thematique", "change_thematique"]
        )
        self.editeur.user_permissions.set(permissions)

    def test_editeur_consulte_et_modifie_uniquement_description(self):
        self.client.force_login(self.editeur)

        url_liste = reverse("wagtailsnippets_cahiers_thematique:list")
        reponse_liste = self.client.get(url_liste)
        self.assertEqual(reponse_liste.status_code, 200)
        self.assertContains(reponse_liste, "Démocratie")
        self.assertContains(reponse_liste, "RIC")

        url_edition = reverse(
            "wagtailsnippets_cahiers_thematique:edit", args=[self.sous_theme.pk]
        )
        reponse_get = self.client.get(url_edition)
        self.assertEqual(reponse_get.status_code, 200)

        # Tentative de modifier `description` + falsifier les champs figés.
        reponse_post = self.client.post(
            url_edition,
            {
                "nom": "Nom falsifié",
                "slug": "slug-falsifie",
                "ordre": "99",
                "parent": "",
                "description": "Nouvelle description validée par l'éditeur.",
            },
        )
        self.assertEqual(reponse_post.status_code, 302)

        self.sous_theme.refresh_from_db()
        self.assertEqual(
            self.sous_theme.description,
            "Nouvelle description validée par l'éditeur.",
        )
        self.assertEqual(self.sous_theme.nom, "RIC")
        self.assertEqual(self.sous_theme.slug, "ric")
        self.assertEqual(self.sous_theme.ordre, 1)
        self.assertEqual(self.sous_theme.parent, self.theme)

    def test_editeur_ne_peut_ni_ajouter_ni_supprimer(self):
        self.client.force_login(self.editeur)

        url_ajout = reverse("wagtailsnippets_cahiers_thematique:add")
        url_suppression = reverse(
            "wagtailsnippets_cahiers_thematique:delete", args=[self.sous_theme.pk]
        )

        # Wagtail redirige vers l'accueil admin (302) en cas de permission refusée.
        self.assertEqual(self.client.get(url_ajout).status_code, 302)
        self.assertEqual(self.client.post(url_suppression).status_code, 302)
        self.assertTrue(Thematique.objects.filter(pk=self.sous_theme.pk).exists())
