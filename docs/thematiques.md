# Taxonomie des thématiques (`Thematique`)

Ce document consigne les choix de modélisation et d'architecture retenus pour la
taxonomie des thèmes et sous-thèmes de la plateforme.

## 1. Un modèle unique auto-référencé à deux niveaux stricts

La taxonomie est représentée par un unique modèle Django `Thematique` dans
`plateforme/cahiers/models.py` :

```text
Thematique
├── nom          (CharField, 200 car. max)
├── slug         (SlugField, 100 car. max, unique)
├── parent       (FK vers soi-même, nullable, on_delete=PROTECT)
├── ordre        (PositiveIntegerField, >= 1, relatif au parent)
└── description  (TextField, description publique)
```

- `parent = None` désigne un **thème principal** (niveau 1).
- `parent = <thème>` désigne un **sous-thème** (niveau 2).
- La profondeur est strictement bornée à **2 niveaux** : un sous-thème ne peut
  pas être parent d'une autre thématique, et un thème ayant déjà des sous-thèmes
  ne peut pas devenir sous-thème.

### Pourquoi une table unique plutôt que deux tables (`Theme` + `SousTheme`) ?

Les contenus classés (en particulier les futures `Idee`) peuvent être rattachés :
- à un sous-thème (cas normal),
- plus rarement, uniquement à un thème principal (lorsque le sous-thème n'est
  pas encore précisé),
- ou à aucune thématique au départ (`null=True`).

Avec une table unique `Thematique`, chaque objet classé ne porte qu'**une seule
clé étrangère** (`thematique = ForeignKey(Thematique, null=True, blank=True,
on_delete=PROTECT)`). Il est ainsi **impossible par construction** d'obtenir un
couple `(theme, sous_theme)` incohérent. Le même modèle peut également être
réutilisé tel quel sur `Contribution` ou sur les pages du CMS.

Les requêtes courantes restent directes et indexées via l'ORM Django :
- non classées : `filter(thematique__isnull=True)` ;
- classées au thème seul : `filter(thematique__isnull=False, thematique__parent__isnull=True)` ;
- sous-thème précis : `filter(thematique=sous_theme)` ;
- tout un thème (thème seul + ses sous-thèmes) : `Q(thematique=theme) | Q(thematique__parent=theme)` (ou `thematique_id__in=ids`).

## 2. Identifiant stable (`slug`) et ordre relatif (`ordre`)

- **`slug` court, unique et figé :** certains intitulés de sous-thèmes dépassent
  100 caractères et peuvent être reformulés. Le `slug` est défini explicitement
  (ASCII minuscules et tirets, ex. `processus-electoral`, `ric`, `isf`) et sert
  de clé métier stable pour les filtres d'URL et les chargements idempotents.
- **`ordre` relatif au parent :** les thèmes principaux sont numérotés à partir
  de 1, et les sous-thèmes repartent à 1 au sein de chaque thème. Une contrainte
  PostgreSQL `UniqueConstraint(fields=["parent", "ordre"], nulls_distinct=False,
  deferrable=DEFERRED)` garantit l'unicité à chaque niveau (y compris entre
  thèmes principaux où `parent IS NULL`) tout en autorisant les échanges
  d'ordres dans une même transaction.

## 3. Séparation `cahiers` / `cms` et intégration Wagtail

- **`Thematique` vit dans `cahiers`** (et non dans une app dédiée supplémentaire)
  afin de conserver un graphe de dépendances simple et unidirectionnel :
  `territoires` ← `cahiers` ← `cms`. L'app `cahiers` n'importe jamais Wagtail.
- **Snippet Wagtail (`cms/wagtail_hooks.py`) :** `Thematique` est exposée en
  `SnippetViewSet` dans le backoffice Wagtail (`/admin/`). Les champs
  structurels (`nom`, `parent`, `slug`, `ordre`) y sont en lecture seule afin de
  préserver la taxonomie figée ; seule `description` (publique) est modifiable
  par les éditeurs disposant des permissions `view_thematique` et
  `change_thematique` (sans `add` ni `delete`).
- **Lien futur avec les pages éditoriales Wagtail :** chaque future page
  éditoriale (`ThematiquePage` dans `cms`) pointera vers sa `Thematique` par
  `OneToOneField(Thematique, on_delete=PROTECT)` — jamais par le `slug` — afin
  que les éditeurs puissent modifier librement les URLs Wagtail sans rompre les
  liens avec les données métier.

## 4. Chargement des données

La logique de chargement vit dans `plateforme/cahiers/chargement.py`
(`charger_thematiques`), appelée par la commande atomique
`uv run python manage.py charger_thematiques` :

- idempotente (clé = `slug`), exécutée en transaction atomique ;
- **préserve par défaut** toute `description` déjà non vide en base afin de ne
  pas écraser le travail des éditeurs Wagtail (sauf `--ecraser-descriptions`) ;
- charge le jeu d'essai `plateforme/cahiers/data/thematiques_mock.csv` par
  défaut en `LOCAL` et `STAGING`, mais exige `--fichier` explicitement en `PROD`.
