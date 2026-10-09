"""Réglages de la plateforme.

Tout ce qui dépend de l'environnement passe par des variables
d'environnement : celles des add-ons Clever Cloud (PostgreSQL, Cellar) en
production, celles de README.md en local.
"""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get("DJANGO_DEBUG") == "1"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY manque (ou DJANGO_DEBUG=1 en local)."
        )
    SECRET_KEY = "django-insecure-developpement-local"

# Noms de domaine séparés par des virgules, par exemple
# « cahiers.cleverapps.io,cahiers.example.org ».
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h]
if DEBUG:
    ALLOWED_HOSTS += ["localhost", "127.0.0.1"]
CSRF_TRUSTED_ORIGINS = [f"https://{h}" for h in ALLOWED_HOSTS]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Sans Nginx en déploiement uv, l'application sert ses fichiers statiques.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# POSTGRESQL_ADDON_URI est fournie par l'add-on PostgreSQL de Clever Cloud.
DATABASES = {
    "default": dj_database_url.parse(
        os.environ.get("POSTGRESQL_ADDON_URI")
        or os.environ.get("DATABASE_URL", "postgres://localhost/cahiers"),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Les fichiers déposés (PDF des cahiers) vont sur Cellar quand l'add-on est
# branché, sur le disque sinon. Le bucket reste privé : les PDF non anonymisés
# ne sont servis que par des liens signés, qui expirent.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}
MEDIA_ROOT = BASE_DIR / "media"
if os.environ.get("CELLAR_ADDON_HOST"):
    hote = os.environ["CELLAR_ADDON_HOST"].removeprefix("https://")
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "endpoint_url": f"https://{hote}",
            "access_key": os.environ["CELLAR_ADDON_KEY_ID"],
            "secret_key": os.environ["CELLAR_ADDON_KEY_SECRET"],
            "bucket_name": os.environ["CELLAR_BUCKET"],
            "region_name": "default",
            "default_acl": "private",
            "querystring_auth": True,
            "querystring_expire": 600,
            "file_overwrite": False,
        },
    }

# Clever Cloud termine le HTTPS et transmet le protocole d'origine. La
# redirection vers HTTPS se règle dans la console (« Force HTTPS ») : faite
# ici, elle renverrait aussi le contrôle de santé, qui arrive en HTTP.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SILENCED_SYSTEM_CHECKS = ["security.W008"]
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 3600

MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.console.EmailBackend",
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
