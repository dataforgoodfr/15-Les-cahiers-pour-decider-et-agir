# Plateforme

L'application de production, en Django, hébergée sur Clever Cloud
([#34](https://github.com/dataforgoodfr/15-Les-cahiers-pour-decider-et-agir/issues/34)).
Les modèles du POC (`backend/`) y sont repris un à un. Pour l'instant :

- `territoires` : régions, départements et communes, arrondissements de Paris,
  Lyon et Marseille et collectivités d'outre-mer compris, chargés depuis
  [geo.api.gouv.fr](https://geo.api.gouv.fr/) par
  `uv run python manage.py charger_communes`. Les cahiers dont la commune est
  inconnue, ou qui viennent de l'étranger, vont à la commune `99999`.

## En local

Il faut un PostgreSQL. Par exemple avec Podman ou Docker :

```sh
podman run -d --name pg-cahiers -e POSTGRES_PASSWORD=cahiers -e POSTGRES_DB=cahiers -p 5432:5432 postgres:18
```

Puis :

```sh
export DATABASE_URL=postgres://postgres:cahiers@localhost/cahiers DJANGO_DEBUG=1
uv sync
uv run python manage.py migrate
uv run python manage.py charger_communes
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

L'administration est sur <http://localhost:8000/admin/>.

Les tests : `uv run python manage.py test`.

## Déploiement sur Clever Cloud

Une application Python, avec les add-ons PostgreSQL et Cellar. Le `uv.lock`
active le déploiement uv natif : pas de Nginx, l'application sert elle-même
ses fichiers statiques (WhiteNoise). Clever Cloud ne lance alors ni `migrate`
ni `collectstatic` : les hooks s'en chargent.

Variables d'environnement à définir :

| Variable | Valeur |
| --- | --- |
| `APP_FOLDER` | `plateforme` |
| `CC_PYTHON_UV_RUN_COMMAND` | `uv run gunicorn config.wsgi` (gunicorn écoute sur `PORT`) |
| `CC_POST_BUILD_HOOK` | `uv run python manage.py collectstatic --noinput` |
| `CC_PRE_RUN_HOOK` | `uv run python manage.py migrate --noinput` |
| `DJANGO_SECRET_KEY` | une longue chaîne aléatoire |
| `DJANGO_ALLOWED_HOSTS` | les domaines, séparés par des virgules |
| `CELLAR_BUCKET` | le nom du bucket des PDF, privé |

`POSTGRESQL_ADDON_URI` et `CELLAR_ADDON_*` sont fournies par les add-ons.
Après le premier déploiement, charger les communes une fois avec
`clever ssh`, puis `uv run python manage.py charger_communes`.
Sans Cellar, les fichiers déposés restent sur le disque de l'instance, qui
n'est pas conservé entre deux déploiements.

Dans la console, activer « Force HTTPS » sur le domaine : l'application ne
redirige pas elle-même vers HTTPS.
