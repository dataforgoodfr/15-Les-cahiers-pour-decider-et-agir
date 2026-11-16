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
        env_propre = {
            "DJANGO_ENV_FILE": str(Path(tmp_dir) / ".env.inexistant"),
            **env_vars,
        }
        with patch.dict(os.environ, env_propre, clear=True):
            return importlib.reload(reglage_module)


class AdminTests(TestCase):
    def test_page_de_connexion(self):
        reponse = self.client.get("/django-admin/login/")
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
        self.assertFalse(s.SESSION_COOKIE_SECURE)
        self.assertFalse(s.CSRF_COOKIE_SECURE)
        self.assertEqual(s.SECURE_HSTS_SECONDS, 0)
        self.assertEqual(s.DATABASES["default"]["NAME"], "cahiers")
        self.assertEqual(s.DATABASES["default"]["PASSWORD"], "cahiers")
        self.assertEqual(
            s.STORAGES["default"]["BACKEND"],
            "django.core.files.storage.FileSystemStorage",
        )
        self.assertEqual(
            s.STORAGES["staticfiles"]["BACKEND"],
            "whitenoise.storage.CompressedStaticFilesStorage",
        )

    def test_configuration_staging_avec_addons_clever_cloud(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_staging = {
                "DJANGO_ENV_FILE": str(Path(tmp_dir) / ".env.inexistant"),
                "DJANGO_ENV": "STAGING",
                "DJANGO_SECRET_KEY": "secret-staging",
                "DJANGO_ALLOWED_HOSTS": "staging.cahiers.cleverapps.io",
                "POSTGRESQL_ADDON_URI": "postgres://u:p@db.internal:5432/cahiers_staging",
                "CELLAR_ADDON_HOST": "cellar-c2.services.clever-cloud.com",
                "CELLAR_ADDON_KEY_ID": "cle-cellar",
                "CELLAR_ADDON_KEY_SECRET": "secret-cellar",
                "CELLAR_BUCKET": "cahiers-staging-prive",
            }
            with patch.dict(os.environ, env_staging, clear=True):
                s = importlib.reload(reglage_module)
                self.assertEqual(s.ENV, "STAGING")
                self.assertFalse(s.DEBUG)
                self.assertEqual(s.ALLOWED_HOSTS, ["staging.cahiers.cleverapps.io"])
                self.assertTrue(s.SESSION_COOKIE_SECURE)
                self.assertTrue(s.CSRF_COOKIE_SECURE)
                self.assertEqual(s.SECURE_HSTS_SECONDS, 3600)
                self.assertEqual(s.DATABASES["default"]["NAME"], "cahiers_staging")
                self.assertEqual(
                    s.STORAGES["default"]["BACKEND"],
                    "storages.backends.s3.S3Storage",
                )
                self.assertEqual(
                    s.STORAGES["default"]["OPTIONS"]["endpoint_url"],
                    "https://cellar-c2.services.clever-cloud.com",
                )
                self.assertEqual(
                    s.STORAGES["default"]["OPTIONS"]["bucket_name"],
                    "cahiers-staging-prive",
                )
                self.assertEqual(
                    os.environ.get("AWS_REQUEST_CHECKSUM_CALCULATION"),
                    "when_required",
                )
                self.assertEqual(
                    os.environ.get("AWS_RESPONSE_CHECKSUM_VALIDATION"),
                    "when_required",
                )

    def test_cellar_incomplet_refuse(self):
        with self.assertRaises(ImproperlyConfigured):
            _recharger_settings(
                {
                    "DJANGO_ENV": "STAGING",
                    "DJANGO_SECRET_KEY": "secret-staging",
                    "POSTGRESQL_ADDON_URI": "postgres://u:p@db.internal:5432/cahiers_staging",
                    "CELLAR_ADDON_HOST": "cellar-c2.services.clever-cloud.com",
                }
            )

    def test_base_de_donnees_manquante_en_staging_et_prod_refuse(self):
        for env in ("STAGING", "PROD"):
            with self.assertRaises(ImproperlyConfigured):
                _recharger_settings(
                    {
                        "DJANGO_ENV": env,
                        "DJANGO_SECRET_KEY": "secret",
                    }
                )

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
            with patch.dict(
                os.environ, {"DJANGO_ENV_FILE": str(fichier_env)}, clear=True
            ):
                s = importlib.reload(reglage_module)
                self.assertEqual(s.ENV, "STAGING")
                self.assertEqual(s.SECRET_KEY, "cle-depuis-dotenv")
                self.assertEqual(s.DATABASES["default"]["NAME"], "cahiers_dotenv")
