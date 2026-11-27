"""Droits des groupes éditoriaux sur le snippet `Thematique`.

La base de test est créée par les migrations : ces tests vérifient donc la
migration de données qui accorde les droits, sur une base neuve.
"""

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from wagtail.snippets.models import get_snippet_models

from cahiers.models import Thematique

# Snippets volontairement réservés aux administrateurs Wagtail : aucune
# migration ne donne de droits aux groupes éditoriaux. Vide pour l'instant.
SNIPPETS_RESERVES_AUX_ADMINISTRATEURS = set()


class MigrationDeDroitsParSnippetTests(TestCase):
    def test_chaque_snippet_donne_des_droits_aux_groupes_editoriaux(self):
        """Django crée les permissions d'un snippet sans les donner à personne.

        Sans migration de données, éditeurs et modérateurs ne le voient pas.
        Chaque nouveau snippet a donc sa propre migration, dans un nouveau
        fichier (`makemigrations --empty cms`), à l'image de
        `cms/migrations/0004_droits_thematiques.py`.
        """
        groupes = Group.objects.filter(name__in=["Editors", "Moderators"])
        for modele in get_snippet_models():
            if modele in SNIPPETS_RESERVES_AUX_ADMINISTRATEURS:
                continue
            with self.subTest(snippet=modele.__name__):
                droits = Permission.objects.filter(
                    content_type=ContentType.objects.get_for_model(modele),
                    group__in=groupes,
                )
                self.assertTrue(
                    droits.exists(),
                    f"Aucun droit sur {modele.__name__} pour Editors ou "
                    f"Moderators : écrire une nouvelle migration de données "
                    f"qui les accorde, ou ajouter le modèle à "
                    f"SNIPPETS_RESERVES_AUX_ADMINISTRATEURS.",
                )


class DroitsThematiquesTests(TestCase):
    def setUp(self):
        self.thematique = Thematique.objects.create(
            nom="Démocratie", slug="democratie", ordre=1
        )

    def connecter(self, groupe):
        """Connecte un membre du groupe donné."""
        membre = User.objects.create_user(f"membre-{groupe}")
        membre.groups.add(Group.objects.get(name=groupe))
        self.client.force_login(membre)

    def test_groupes_editoriaux_voient_et_modifient_seulement(self):
        for nom in ("Editors", "Moderators"):
            with self.subTest(groupe=nom):
                codenames = set(
                    Group.objects.get(name=nom)
                    .permissions.filter(content_type__model="thematique")
                    .values_list("codename", flat=True)
                )
                self.assertEqual(codenames, {"view_thematique", "change_thematique"})

    def test_editeur_consulte_et_modifie(self):
        self.connecter("Editors")
        for action, args in (("list", []), ("edit", [self.thematique.pk])):
            with self.subTest(action=action):
                url = reverse(f"wagtailsnippets_cahiers_thematique:{action}", args=args)
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_editeurs_et_moderateurs_modifient_la_description(self):
        url = reverse(
            "wagtailsnippets_cahiers_thematique:edit", args=[self.thematique.pk]
        )
        for groupe in ("Editors", "Moderators"):
            with self.subTest(groupe=groupe):
                self.connecter(groupe)
                description = f"Description revue par {groupe}."
                reponse = self.client.post(url, {"description": description})
                self.assertRedirects(
                    reponse, reverse("wagtailsnippets_cahiers_thematique:list")
                )
                self.thematique.refresh_from_db()
                self.assertEqual(self.thematique.description, description)

    def test_editeur_ne_peut_ni_ajouter_ni_supprimer(self):
        self.connecter("Editors")
        for action, args in (("add", []), ("delete", [self.thematique.pk])):
            with self.subTest(action=action):
                url = reverse(f"wagtailsnippets_cahiers_thematique:{action}", args=args)
                self.assertRedirects(self.client.get(url), reverse("wagtailadmin_home"))
