"""Tests de l'authentification des espaces d'administration (issue #226)."""

from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from cms.models import HomePage
from cms.wagtail_hooks import bouton_lien_reinitialisation


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


class CreationSansMotDePasseTests(TestCase):
    """Personne ne saisit ni ne connaît le mot de passe d'un nouveau compte.

    L'administrateur Wagtail crée le compte sans mot de passe ; la personne
    choisit le sien via un lien de réinitialisation. Django enregistre alors
    un mot de passe vide : aucune connexion n'est possible, mais le compte
    reste « utilisable » au sens de Django, si bien que la réinitialisation
    par courriel fonctionnera le jour où un serveur SMTP sera disponible.
    """

    def setUp(self):
        """Connecte un administrateur Wagtail."""
        admin_wagtail = User.objects.create_user(
            username="admin-wagtail", password="secret-admin", is_superuser=True
        )
        self.client.force_login(admin_wagtail)
        self.url_ajout = reverse("wagtailusers_users:add")

    def test_formulaire_sans_champ_de_mot_de_passe(self):
        """Le formulaire d'ajout Wagtail ne propose aucun mot de passe."""
        formulaire = self.client.get(self.url_ajout).context["form"]
        self.assertNotIn("password1", formulaire.fields)
        self.assertNotIn("password2", formulaire.fields)

    def test_compte_cree_inaccessible_mais_reinitialisable(self):
        """Le compte créé n'ouvre aucune session et reste réinitialisable."""
        reponse = self.client.post(
            self.url_ajout,
            {
                "username": "editrice",
                "email": "editrice@example.org",
                "first_name": "Édith",
                "last_name": "Rice",
                "groups": [Group.objects.get(name="Editors").pk],
            },
        )
        self.assertEqual(reponse.status_code, 302)
        editrice = User.objects.get(username="editrice")

        self.client.logout()
        self.assertFalse(self.client.login(username="editrice", password=""))
        self.assertTrue(editrice.has_usable_password())
        self.assertEqual(
            list(PasswordResetForm().get_users("editrice@example.org")), [editrice]
        )


class LienReinitialisationTests(TestCase):
    """Bouton « Lien de réinitialisation » de Paramètres → Utilisateurs.

    Sans serveur SMTP, l'administrateur Wagtail génère le lien et le transmet
    lui-même. Un administrateur Wagtail (superutilisateur sans `is_staff`) ne
    peut pas viser un compte `is_staff` : il prendrait sinon la main sur un
    compte développeur et entrerait dans l'admin Django.
    """

    NOUVEAU_MOT_DE_PASSE = "Un-mot-de-passe-solide-42"

    def setUp(self):
        """Crée un administrateur Wagtail, deux développeurs et une éditrice."""
        self.admin_wagtail = User.objects.create_user(
            username="admin-wagtail", is_superuser=True
        )
        self.developpeur = User.objects.create_user(
            username="dev", is_superuser=True, is_staff=True
        )
        self.autre_developpeur = User.objects.create_user(
            username="dev-2", is_superuser=True, is_staff=True
        )
        # Créée comme depuis Wagtail : sans mot de passe.
        self.editrice = User.objects.create(
            username="editrice", email="editrice@example.org"
        )
        self.editrice.groups.add(Group.objects.get(name="Editors"))

    @staticmethod
    def _url(cible):
        """Renvoie l'URL de la page du lien de réinitialisation de `cible`."""
        return reverse("cms_lien_reinitialisation", args=[cible.pk])

    def _lien(self, demandeur, cible):
        """Renvoie le lien que `demandeur` obtient pour `cible`."""
        self.client.force_login(demandeur)
        reponse = self.client.get(self._url(cible))
        self.assertEqual(reponse.status_code, 200)
        return reponse.context["lien"]

    def _assert_refuse(self, demandeur, cible):
        """Vérifie que Wagtail refuse la page et ne divulgue aucun lien."""
        self.client.force_login(demandeur)
        reponse = self.client.get(self._url(cible))
        self.assertRedirects(
            reponse, reverse("wagtailadmin_home"), fetch_redirect_response=False
        )

    def _choisir_mot_de_passe(self, lien):
        """Suit le lien en visiteur anonyme et choisit un mot de passe."""
        self.client.logout()
        reponse = self.client.get(lien)
        # Django retire le jeton de l'URL et le garde en session.
        self.assertEqual(reponse.status_code, 302)
        url_formulaire = reponse.url
        self.assertEqual(self.client.get(url_formulaire).status_code, 200)
        return self.client.post(
            url_formulaire,
            {
                "new_password1": self.NOUVEAU_MOT_DE_PASSE,
                "new_password2": self.NOUVEAU_MOT_DE_PASSE,
            },
        )

    def test_bouton_present_dans_la_liste_des_utilisateurs(self):
        """L'administrateur Wagtail voit le bouton sur la ligne d'un compte."""
        self.client.force_login(self.admin_wagtail)
        reponse = self.client.get(reverse("wagtailusers_users:index"))
        self.assertContains(reponse, self._url(self.editrice))

    def test_bouton_absent_pour_qui_ne_peut_pas_generer_le_lien(self):
        """Pas de bouton hors superutilisateur, ni vers un compte développeur."""
        self.assertEqual(
            bouton_lien_reinitialisation(
                user=self.admin_wagtail, request_user=self.editrice
            ),
            [],
        )
        self.assertEqual(
            bouton_lien_reinitialisation(
                user=self.developpeur, request_user=self.admin_wagtail
            ),
            [],
        )

    def test_lien_absolu_vers_la_confirmation_wagtail(self):
        """Le lien pointe vers la page de réinitialisation de Wagtail."""
        lien = self._lien(self.admin_wagtail, self.editrice)
        self.assertTrue(
            lien.startswith("http://testserver/admin/password_reset/confirm/")
        )

    def test_lien_permet_de_choisir_son_mot_de_passe(self):
        """La personne choisit son mot de passe puis se connecte avec."""
        lien = self._lien(self.admin_wagtail, self.editrice)
        reponse = self._choisir_mot_de_passe(lien)
        self.assertRedirects(
            reponse,
            reverse("wagtailadmin_password_reset_complete"),
            fetch_redirect_response=False,
        )
        self.assertTrue(
            self.client.login(
                username="editrice", password=self.NOUVEAU_MOT_DE_PASSE
            )
        )

    def test_lien_a_usage_unique(self):
        """Une fois le mot de passe choisi, le même lien ne marche plus."""
        lien = self._lien(self.admin_wagtail, self.editrice)
        self._choisir_mot_de_passe(lien)
        self.client.logout()
        reponse = self.client.get(lien)
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(reponse.context["validlink"])

    def test_lien_invalide_renvoie_vers_un_administrateur(self):
        """Un lien périmé oriente vers un administrateur, pas vers le courriel.

        Sans serveur SMTP, le formulaire « nouvelle réinitialisation » de
        Wagtail n'enverrait rien : seul un administrateur peut aider.
        """
        lien = self._lien(self.admin_wagtail, self.editrice)
        self._choisir_mot_de_passe(lien)
        self.client.logout()
        reponse = self.client.get(lien)
        self.assertContains(reponse, "Demandez un nouveau lien à un administrateur")
        self.assertContains(reponse, f'href="{reverse("wagtailadmin_login")}"')
        self.assertNotContains(reponse, reverse("wagtailadmin_password_reset"))

    def test_mot_de_passe_oublie_oriente_vers_un_administrateur(self):
        """« Mot de passe oublié ? » ne propose pas un courriel qui n'arrivera pas.

        Les courriels partent dans la console (`MAILERS`) : le formulaire de
        Wagtail annoncerait un envoi que personne ne recevrait.
        """
        reponse = self.client.get(reverse("wagtailadmin_password_reset"))
        self.assertContains(reponse, "Demandez un lien de réinitialisation")
        self.assertNotContains(reponse, 'name="email"')
        self.assertContains(reponse, f'href="{reverse("wagtailadmin_login")}"')

    def test_page_refusee_a_une_editrice(self):
        """Une éditrice ne peut générer aucun lien."""
        self._assert_refuse(self.editrice, self.admin_wagtail)

    def test_admin_wagtail_ne_vise_pas_un_developpeur(self):
        """Un administrateur Wagtail ne peut pas viser un compte `is_staff`."""
        self._assert_refuse(self.admin_wagtail, self.developpeur)

    def test_developpeur_vise_un_developpeur(self):
        """Un développeur peut générer le lien d'un autre développeur."""
        self._lien(self.developpeur, self.autre_developpeur)

    def test_utilisateur_inconnu(self):
        """Un identifiant inexistant renvoie une 404."""
        self.client.force_login(self.admin_wagtail)
        url = reverse("cms_lien_reinitialisation", args=[999_999])
        self.assertEqual(self.client.get(url).status_code, 404)
