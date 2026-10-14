# Plateforme

L'application de production, en Django, hébergée sur Clever Cloud
([#34](https://github.com/dataforgoodfr/15-Les-cahiers-pour-decider-et-agir/issues/34)).
Les modèles du POC y sont repris un à un. Pour l'instant :

- `territoires` : régions, départements et communes **au 1er janvier 2019**,
  le millésime des codes INSEE des cahiers. Communes déléguées, associées et
  arrondissements y sont rattachés à leur commune parente ; le découpage actuel
  n'est qu'une annotation (`code_courant`, `nom_courant`). Chargés par
  `uv run python manage.py charger_communes`, depuis l'INSEE (COG 2019,
  populations municipales 2017) et geo.api.gouv.fr (centres actuels). Sources
  sous Licence Ouverte : toute publication porte « Source : Insee » et
  « Source : IGN ». Mayotte n'a pas de population légale 2017.
- `cahiers` : les documents du versement (cahiers, courriers, comptes rendus),
  leurs pages, et les contributions qu'on y délimite. Document et pages sont
  la provenance, jamais réécrite ; une délimitation est une couche, rattachée
  à un run, et plusieurs coexistent. Les contributions sont délimitées sur
  l'image, en points PDF, comme dans l'outil d'annotation d'`analyse/`.
  Les cahiers citoyens et leurs pages sont chargés par
  `uv run python manage.py charger_corpus`, depuis les sorties d'`analyse/`
  (`--analyse`, par défaut `../analyse/data`) : type, rotation, pages de
  service et d'ouverture, rattachements à une autre commune. Les types et
  rotations vérifiés dans l'outil d'annotation l'emportent sur les mesures.
  Les contributions délimitées à la main (sortie de `python -m delimitation`
  dans `analyse/`) sont chargées par `uv run python manage.py
  charger_contributions`, sous un run de délimitation « à la main » : un
  début et une fin en (page, x, y), et `publiable` à faux pour ce qui est « à
  écarter », jamais montré.
  Leur extrait, le PDF de la contribution seule caviardé et relu (sortie de
  `python -m selection`), est rattaché par `uv run python manage.py
  charger_extraits` : c'est le seul fichier que le public voit. La page
  d'accueil en tire une au sort (#30), parmi les contributions publiables du
  run actif qui ont un extrait ; le PDF d'un cahier n'a aucune adresse
  publique.
  Les contributions de l'édition de Marie-Anne Chabin (Charente-Maritime)
  sont chargées par `uv run python manage.py charger_chabin`, sous un run de
  délimitation « édition Chabin », jamais activé : celles, dactylographiées
  ou courriels, dont `python -m chabin` retrouve le début dans l'OCR du scan,
  avec leur texte anonymisé par l'édition. Les manuscrits, sans position, ne
  sont pas chargés.

## La table des pages

Le format commun de la chaîne texte
([#16](https://github.com/dataforgoodfr/15-Les-cahiers-pour-decider-et-agir/issues/16)) :
les étapes lisent ces tables, pas les PDF. PostgreSQL fait référence.

| Table | Une ligne par | Contenu |
| --- | --- | --- |
| `Document` | fichier du versement | catégorie, commune du nom de fichier, date de dépôt, nombre de pages |
| `Rattachement` | changement de commune dans un document | page à partir de laquelle le cahier est celui d'une autre commune (#42) |
| `Page` | page | type (vierge, dactylographiée, mixte, manuscrite), rotation, page de service ou d'ouverture, couche texte native du PDF |
| `Run` | couche produite | genre, auteur, modèle et paramètres ; un seul actif par genre |
| `Transcription` | page et run de transcription | texte, qualité entre 0 et 1, chemin des sorties lourdes (ALTO, images) hors base |
| `Contribution` | contribution et run de délimitation | de (page, x, y) à (page, x, y), en points PDF ; publiable ou non ; texte s'il a été lu |

Le fichier PDF (`CC_01000_190304_01053_MD_15462.pdf`) et le numéro de page,
à partir de 1, désignent une page partout, dans `analyse/` comme ici.

Chaque étape écrit sous un run de son genre, sans toucher aux couches des
autres runs : une transcription par HTR ajoute des `Transcription`, un
découpage automatique des `Contribution`. Le document et ses pages ne sont
jamais réécrits ; seuls les attributs mesurés par `analyse/` (type, rotation,
service, ouverture) y sont reportés.

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
uv run python manage.py charger_corpus  # si les sorties d'analyse/ sont là
uv run python manage.py charger_contributions  # après python -m delimitation
uv run python manage.py charger_extraits  # après python -m selection
uv run python manage.py charger_chabin  # après python -m chabin
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
