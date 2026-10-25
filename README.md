# Les cahiers pour décider et agir

Projet [Data For Good](https://dataforgood.fr/), saison 2026-2027, avec
l'association [Des cahiers pour décider et agir](https://www.decider-agir.fr/).

## Le projet

Pendant le Grand débat national (fin 2018 - début 2019), des milliers de
communes ont ouvert des « cahiers citoyens » où chacun pouvait écrire ses
doléances.

**Des cahiers pour décider et agir** est un projet associatif : organiser la
restitution de ces cahiers. Data For Good l'accompagne sur la partie données.

## L'objectif

Une plateforme grand public pour consulter les cahiers : lire des
contributions anonymisées, voter, s'informer. Les administrateurs de
l'association accèdent à la base, cahiers non anonymisés compris.

La plateforme montre un panel représentatif, pas tout le corpus. L'association
a besoin d'une sélection « gold » d'une centaine de contributions pour ses
médias. Elle sort d'un tirage automatique : un premier tirage de 100
contributions, représentatif des habitants de la France entière, est fait
([#21](https://github.com/dataforgoodfr/15-Les-cahiers-pour-decider-et-agir/issues/21)) ;
les réactions de l'association en fixeront les critères définitifs.
Les chantiers de données visent la qualité nécessaire pour ce panel, pas
l'exhaustivité.

Le produit doit être décidé en novembre 2026, pour l'arrivée des bénévoles ;
livraison au premier trimestre 2027. Le détail est dans l'issue
[#29](https://github.com/dataforgoodfr/15-Les-cahiers-pour-decider-et-agir/issues/29).

## Où on en est

Au 25 octobre 2026 :

- **Le corpus est mesuré** : type de chaque page, communes, panel
  ([`analyse/`](analyse/)).
- **Les 100 contributions tirées sont prêtes** : exportées en PDF caviardés,
  réunies dans un recueil pour l'association. Leurs cahiers sont délimités
  en entier à la main, soit 4 228 contributions
  ([#5](https://github.com/dataforgoodfr/15-Les-cahiers-pour-decider-et-agir/issues/5),
  [#7](https://github.com/dataforgoodfr/15-Les-cahiers-pour-decider-et-agir/issues/7)).
- **Le découpage automatique** (règles : courriels, formulaires, lettres ;
  un petit modèle pour les pages qu'elles ne découpent pas) est mesuré sur
  ces cahiers délimités : sur les pages dactylographiées et mixtes, 75 %
  des débuts trouvés sont justes et 81 % des débuts sont trouvés. Une référence de test,
  un tronçon dans chacun des 41 départements qu'ils ne couvrent pas, est en
  cours d'annotation ([`analyse/contributions/`](analyse/contributions/)).
- **L'anonymisation automatique** est mesurée sur trois étalons caviardés
  par des humains ([`docs/anonymisation.md`](docs/anonymisation.md)).
  Publié en texte seul, le corpus est couvert à 92 % en ne cachant que 3 %
  des mots du lexique, à 94 % si l'on encadre deux pages par formulaire ;
  1 333 cahiers en ont un
  ([#128](https://github.com/dataforgoodfr/15-Les-cahiers-pour-decider-et-agir/issues/128)).
  Sur l'image, des modèles de vision à poids ouverts, servis sur une carte
  louée en Europe, couvrent 88 à 89 % des données de l'étalon de l'Aude en
  ne cachant que 1 à 2 % du reste, manuscrits compris.
- **L'OCR du versement** (ABBYY FineReader 11) est mesuré
  ([`docs/ocr.md`](docs/ocr.md)) : une contribution imprimée typique a 1,5 %
  d'erreurs par caractère, 0,6 % avec un OCR récent à poids ouverts. La
  couche texte n'est pas décalée de l'image. Environ 3 000 pages typées
  dactylographiées lui sont presque illisibles : celles qu'on a regardées
  sont des formulaires remplis à la main.
- **La lecture des manuscrits** a son banc d'essai, sur deux étalons
  (Charente-Maritime, Dole) ([`docs/htr.md`](docs/htr.md)).
- **Les thèmes** suivent la grille V2 de l'association : 8 thèmes et 42
  sous-thèmes, repérés par mots-clés ([#24](https://github.com/dataforgoodfr/15-Les-cahiers-pour-decider-et-agir/issues/24)).
- **Le regroupement des propositions** est outillé : découpage des
  contributions de l'édition Chabin en propositions, paires tirées et outil
  pour les juger ([#94](https://github.com/dataforgoodfr/15-Les-cahiers-pour-decider-et-agir/issues/94)).
- **La plateforme Django** charge les cahiers, les contributions délimitées
  et celles de l'édition Chabin
  ([`plateforme/`](plateforme/)).

Le POC de l'été 2026 a porté sur trois départements (Ain, Eure-et-Loir,
Mayenne). Son code est dans [dataforgoodfr/cahier_doleances](https://github.com/dataforgoodfr/cahier_doleances).

## Travaux extérieurs

- **Marie-Anne Chabin** nous a donné le droit de réutiliser ses
  [transcriptions](https://www.marieannechabin.fr/edition-de-cahiers-doleances-2019/)
  des cahiers de Charente-Maritime (134 communes, 1 693 contributions déjà
  séparées). Elles nous servent d'étalon pour le découpage et l'exploitation
  des contributions ([`extraction/`](extraction/)).
- **Le Campus Condorcet** a publié ses méthodes pour la représentativité d'un
  échantillon de contributions (5 % du corpus). Nous comparons nos résultats
  aux siens pour nous assurer de la cohérence de nos travaux.

## Avant la diffusion sur la plateforme

On est encore loin de diffuser massivement les cahiers :

- **Contenu prêt** : les 100 contributions délimitées et caviardées à la main
  du premier tirage. C'est le rythme d'un lecteur, pas d'une diffusion
  massive.
- **Découper automatiquement** est le préalable au reste du corpus.
  Aujourd'hui, règles et modèle ne découpent que les pages à couche
  imprimée (dactylographiées et mixtes), et en manquent un cinquième des
  débuts.
- **Anonymiser sans tout relire** suppose une décision de l'association
  ([#128](https://github.com/dataforgoodfr/15-Les-cahiers-pour-decider-et-agir/issues/128)) : publier le texte des contributions plutôt que les
  images des pages (il resterait à encadrer deux pages par formulaire,
  environ 2 700 pages), ou les images, en confiant leurs pages à des
  modèles de vision servis hors de nos machines. Dans les deux cas, un audit
  par échantillon.
- **La modération** des contenus haineux ou illicites se fait à la main,
  pendant la délimitation : rien ne la mesure ni ne l'automatise encore
  ([#166](https://github.com/dataforgoodfr/15-Les-cahiers-pour-decider-et-agir/issues/166)).
- **La moitié des pages écrites sont manuscrites** (142 000 sur 276 000) et
  ne sont pas encore lues
  ([#6](https://github.com/dataforgoodfr/15-Les-cahiers-pour-decider-et-agir/issues/6)) :
  aucun modèle local ne les lit encore assez bien ([`docs/htr.md`](docs/htr.md)).
- **La plateforme sera en Django** sur Clever Cloud (PostgreSQL, Cellar pour
  les PDF), avec Wagtail s'il faut un CMS
  ([#34](https://github.com/dataforgoodfr/15-Les-cahiers-pour-decider-et-agir/issues/34)) :
  produit décidé en novembre 2026, livraison au premier trimestre 2027.

## Les données

Les cahiers contiennent des opinions politiques signées : ce sont des données
sensibles. **Aucune donnée des cahiers n'entre dans ce dépôt**, qui est public.
Les règles sont dans [docs/donnees.md](docs/donnees.md).
À lire avant toute contribution.

## Organisation

Le travail est suivi dans les [issues](https://github.com/dataforgoodfr/15-Les-cahiers-pour-decider-et-agir/issues).

Pour commencer, voir [CONTRIBUTING.md](CONTRIBUTING.md).

## Organisation du dépôt

Les étapes du traitement et le module qui fait chacune sont dans
[`docs/chaine.md`](docs/chaine.md).


- [`analyse/`](analyse/) : mesures sur le corpus (typage des pages, communes,
  panel, tirage), outil d'annotation, découpage et caviardage des
  contributions. Sous-projet autonome, avec son `pyproject.toml`.
- [`backend/`](backend/) : extraction des fichiers des cahiers, base de données
  et interface d'administration.
- [`extraction/`](extraction/) : transcriptions extérieures (édition Chabin).
- [`htr/`](htr/) : lecture des pages manuscrites par un modèle HTR léger
  (kraken, sur CPU).
- [`plateforme/`](plateforme/) : l'application de production, en Django sur
  Clever Cloud. Pour l'instant un squelette, qui reprendra les modèles de
  `backend/`.
- [`docs/`](docs/) : la chaîne de traitement, des PDF à la plateforme
  ([`docs/chaine.md`](docs/chaine.md)), règles sur les données, et les bancs
  d'essai de chaque étape (OCR, manuscrits, anonymisation).

Chaque sous-projet utilise [uv](https://docs.astral.sh/uv/) : par exemple `cd analyse && uv sync`,
puis `uv run ...`.

## Licence

Voir [LICENSE](LICENSE).
