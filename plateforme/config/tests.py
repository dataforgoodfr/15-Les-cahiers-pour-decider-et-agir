import importlib
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase

import config.settings as reglage_module


def _recharger_settings(env_vars: dict[str, str]):
    """Recharge config.settings dans un environnement isolé sans fichier .env."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        env_propre = {"DJANGO_ENV_FILE": str(Path(tmp_dir) / ".env.inexistant"), **env_vars}
        with patch.dict(os.environ, env_propre, clear=True):
            return importlib.reload(reglage_module)


class AdminTests(TestCase):
    def test_page_de_connexion(self):
        reponse = self.client.get("/admin/login/")
        self.assertContains(reponse, "Les cahiers pour décider et agir")

    def test_admin_reservee_aux_administrateurs(self):
        self.assertRedirects(self.client.get("/admin/"), "/admin/login/?next=/admin/")
        User.objects.create_superuser("admin", password="motdepasse")
        self.client.login(username="admin", password="motdepasse")
        self.assertEqual(self.client.get("/admin/").status_code, 200)


class SettingsEnvironnementTests(SimpleTestCase):
    """Vérifie la configuration 12-Factor pour LOCAL, STAGING et PROD."""

    def tearDown(self):
        # Restaure le module settings dans son état initial après chaque test.
        importlib.reload(reglage_module)

    def test_configuration_local_par_defaut(self):
        s = _recharger_settings({"DJANGO_ENV": "LOCAL"})
        self.assertEqual(s.ENV, "LOCAL")
        self.assertTrue(s.DEBUG)
        self.assertEqual(s.SECRET_KEY, "django-insecure-developpement-local")
        self.assertIn("localhost", s.ALLOWED_HOSTS)
        self.assertEqual(s.DATABASES["default"]["NAME"], "cahiers")
        self.assertEqual(s.DATABASES["default"]["PASSWORD"], "cahiers")

    def test_configuration_staging(self):
        s = _recharger_settings(
            {
                "DJANGO_ENV": "STAGING",
                "DJANGO_SECRET_KEY": "secret-staging",
                "DJANGO_ALLOWED_HOSTS": "staging.cahiers.example.org",
                "POSTGRESQL_ADDON_URI": "postgres://u:p@db.internal:5432/cahiers_staging",
            }
        )
        self.assertEqual(s.ENV, "STAGING")
        self.assertFalse(s.DEBUG)
        self.assertEqual(s.ALLOWED_HOSTS, ["staging.cahiers.example.org"])
        self.assertTrue(s.SESSION_COOKIE_SECURE)
        self.assertEqual(s.DATABASES["default"]["NAME"], "cahiers_staging")

    def test_configuration_prod_refuse_debug(self):
        with self.assertRaises(ImproperlyConfigured):
            _recharger_settings(
                {
                    "DJANGO_ENV": "PROD",
                    "DJANGO_DEBUG": "1",
                    "DJANGO_SECRET_KEY": "secret-prod",
                    "DATABASE_URL": "postgres://u:p@db.internal:5432/cahiers_prod",
                }
            )

    def test_configuration_staging_et_prod_exigent_secret_key(self):
        for env in ("STAGING", "PROD"):
            with self.assertRaises(ImproperlyConfigured):
                _recharger_settings(
                    {
                        "DJANGO_ENV": env,
                        "DATABASE_URL": "postgres://u:p@db.internal:5432/cahiers",
                    }
                )

    def test_environnement_invalide_refuse(self):
        with self.assertRaises(ImproperlyConfigured):
            _recharger_settings({"DJANGO_ENV": "INCONNU"})

    def test_chargement_fichier_dotenv(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            fichier_env = Path(tmp_dir) / ".env.test"
            fichier_env.write_text(
                "DJANGO_ENV=STAGING\n"
                "DJANGO_SECRET_KEY=cle-depuis-dotenv\n"
                "DATABASE_URL=postgres://u:p@localhost:5432/cahiers_dotenv\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"DJANGO_ENV_FILE": str(fichier_env)}, clear=True):
                s = importlib.reload(reglage_module)
                self.assertEqual(s.ENV, "STAGING")
                self.assertEqual(s.SECRET_KEY, "cle-depuis-dotenv")
                self.assertEqual(s.DATABASES["default"]["NAME"], "cahiers_dotenv")

