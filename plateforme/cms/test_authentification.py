"""Tests de l'authentification des espaces d'administration (issue #226)."""

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from cms.models import HomePage


class AccesParRoleTests(TestCase):
    """Fige les droits de chaque rôle sur les deux espaces d'administration.

    Wagtail (`/admin/`) s'ouvre via la permission `wagtailadmin.access_admin`,
    portée par les groupes `Editors` et `Moderators` ; l'admin Django
    (`/django-admin/`) exige `is_staff`, un attribut que l'interface Wagtail
    ne permet pas d'attribuer.
    """

    def setUp(self):
        """Crée un éditeur, un modérateur et un administrateur Wagtail."""
        self.accueil = HomePage.objects.get(slug="home")
        self.editeur = self._membre("editeur", "Editors")
        self.moderateur = self._membre("moderateur", "Moderators")
        # Administrateur Wagtail : superutilisateur, mais sans `is_staff`.
        self.admin_wagtail = User.objects.create_user(
            username="admin-wagtail", is_superuser=True
        )

    @staticmethod
    def _membre(username, groupe):
        """Crée un utilisateur sans `is_staff`, membre du groupe Wagtail donné."""
        utilisateur = User.objects.create_user(username=username)
        utilisateur.groups.add(Group.objects.get(name=groupe))
        return utilisateur

    def _redirige_vers_connexion_django(self, utilisateur):
        """Vérifie que l'admin Django renvoie l'utilisateur vers sa connexion."""
        self.client.force_login(utilisateur)
        reponse = self.client.get(reverse("admin:index"))
        self.assertRedirects(
            reponse,
            f"{reverse('admin:login')}?next={reverse('admin:index')}",
            fetch_redirect_response=False,
        )

    def test_editeur_accede_a_wagtail_sans_pouvoir_publier(self):
        """Un éditeur ouvre Wagtail et modifie, mais ne publie pas."""
        self.client.force_login(self.editeur)
        self.assertEqual(self.client.get(reverse("wagtailadmin_home")).status_code, 200)
        droits = self.accueil.permissions_for_user(self.editeur)
        self.assertTrue(droits.can_edit())
        self.assertFalse(droits.can_publish())

    def test_moderateur_peut_publier(self):
        """Un modérateur peut publier les pages."""
        droits = self.accueil.permissions_for_user(self.moderateur)
        self.assertTrue(droits.can_publish())

    def test_admin_wagtail_gere_les_utilisateurs(self):
        """Un administrateur Wagtail ouvre la gestion des utilisateurs."""
        self.client.force_login(self.admin_wagtail)
        reponse = self.client.get(reverse("wagtailusers_users:index"))
        self.assertEqual(reponse.status_code, 200)

    def test_aucun_role_wagtail_n_accede_a_l_admin_django(self):
        """Sans `is_staff`, aucun rôle Wagtail n'entre dans l'admin Django."""
        for utilisateur in (self.editeur, self.moderateur, self.admin_wagtail):
            with self.subTest(utilisateur=utilisateur.username):
                self._redirige_vers_connexion_django(utilisateur)
