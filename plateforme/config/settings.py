"""Réglages de la plateforme (12-Factor App).

Trois environnements de déploiement sont pris en charge via ``DJANGO_ENV`` :
- ``LOCAL`` : développement local (PostgreSQL sous Docker, ``DEBUG=True`` par défaut).
- ``STAGING`` : pré-production (Clever Cloud, ``DEBUG=False`` par défaut).
- ``PROD`` : production (Clever Cloud, ``DEBUG=False`` imposé).

Les variables d'environnement peuvent être chargées depuis un fichier ``.env``
(en local) ou fournies par la plateforme d'hébergement (Clever Cloud en
STAGING et PROD). Les variables déjà présentes dans l'environnement système
sont toujours prioritaires sur les fichiers ``.env``.
"""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

ENVIRONNEMENTS_VALIDES = ("LOCAL", "STAGING", "PROD")


def _charger_fichiers_env(base_dir: Path) -> None:
    """Charge les fichiers .env sans écraser les variables déjà définies."""
    fichier_explicite = os.environ.get("DJANGO_ENV_FILE")
    if fichier_explicite:
        chemin = Path(fichier_explicite)
        if not chemin.is_absolute():
            chemin = base_dir / chemin
        load_dotenv(chemin, override=False)
        return

    env_courant = os.environ.get("DJANGO_ENV", "").strip().lower()
    if env_courant:
        load_dotenv(base_dir / f".env.{env_courant}", override=False)
    load_dotenv(base_dir / ".env", override=False)


_charger_fichiers_env(BASE_DIR)

# Détermination de l'environnement (LOCAL, STAGING ou PROD).
_env_brut = os.environ.get("DJANGO_ENV", "").strip().upper()
if _env_brut:
    if _env_brut not in ENVIRONNEMENTS_VALIDES:
        raise ImproperlyConfigured(
            f"DJANGO_ENV invalide : {_env_brut!r}. "
            f"Valeurs attendues : {', '.join(ENVIRONNEMENTS_VALIDES)}."
        )
    ENV = _env_brut
else:
    ENV = "LOCAL" if os.environ.get("DJANGO_DEBUG") == "1" else "PROD"

# Mode DEBUG : activé par défaut uniquement en LOCAL, interdit en PROD.
if "DJANGO_DEBUG" in os.environ:
    DEBUG = os.environ["DJANGO_DEBUG"].strip().lower() in ("1", "true", "yes")
else:
    DEBUG = ENV == "LOCAL"

if ENV == "PROD" and DEBUG:
    raise ImproperlyConfigured("DJANGO_DEBUG ne peut pas être activé lorsque DJANGO_ENV=PROD.")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if ENV != "LOCAL":
        raise ImproperlyConfigured(
            f"DJANGO_SECRET_KEY manque (obligatoire en {ENV}, ou définir DJANGO_ENV=LOCAL)."
        )
    SECRET_KEY = "django-insecure-developpement-local"

# Noms de domaine séparés par des virgules, par exemple
# « cahiers-staging.cleverapps.io » ou « cahiers.cleverapps.io,cahiers.example.org ».
ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()
]
if ENV == "LOCAL" or DEBUG:
    for hote_local in ("localhost", "127.0.0.1"):
        if hote_local not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(hote_local)
CSRF_TRUSTED_ORIGINS = [f"https://{h}" for h in ALLOWED_HOSTS]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "territoires",
    "cahiers",
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

# POSTGRESQL_ADDON_URI est fournie par l'add-on PostgreSQL de Clever Cloud (STAGING / PROD).
# En LOCAL, l'URL par défaut correspond au conteneur Docker postgres:18 (pg-cahiers).
_database_url = os.environ.get("POSTGRESQL_ADDON_URI") or os.environ.get("DATABASE_URL")
if not _database_url:
    if ENV == "LOCAL":
        _database_url = "postgres://postgres:cahiers@localhost:5432/cahiers"
    else:
        raise ImproperlyConfigured(
            f"DATABASE_URL ou POSTGRESQL_ADDON_URI manque en environnement {ENV}."
        )

DATABASES = {
    "default": dj_database_url.parse(
        _database_url,
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

# Fichiers téléchargés de l'INSEE, gardés pour ne pas les retélécharger.
SOURCES_DIR = Path(os.environ.get("SOURCES_DIR", BASE_DIR / "sources"))

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
