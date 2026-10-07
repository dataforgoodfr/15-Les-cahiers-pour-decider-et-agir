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

Au 7 octobre 2026 :

- **Le corpus est mesuré** : type de chaque page, communes, panel
  ([`analyse/`](analyse/)).
- **100 contributions sont tirées.** Pour chacune, il faut délimiter à la main
  toutes les contributions de son cahier, puis caviarder la contribution
  tirée. 37 sont faites et exportées en PDF caviardés, soit 1 300 contributions
  délimitées ; il en reste 63
  ([#5](https://github.com/dataforgoodfr/15-Les-cahiers-pour-decider-et-agir/issues/5),
  [#7](https://github.com/dataforgoodfr/15-Les-cahiers-pour-decider-et-agir/issues/7)).
- **Les transcriptions de Marie-Anne Chabin** (134 cahiers de
  Charente-Maritime, 1 693 contributions déjà séparées) arrivent dans
  [`extraction/`](extraction/). Elles serviront de référence de découpage.
- **Le Campus Condorcet sert de juge indépendant.** Le projet ne repose pas
  sur son travail ; un petit panel aligné sur son échantillon
  ([`analyse/`](analyse/), module `panel`) sert d'échantillon de travail.

Le POC de l'été 2026 a porté sur trois départements (Ain, Eure-et-Loir,
Mayenne). Son code est dans [dataforgoodfr/cahier_doleances](https://github.com/dataforgoodfr/cahier_doleances).

## Avant la diffusion sur la plateforme

On est encore loin de diffuser massivement les cahiers :

- **Contenu prêt** : les 37 contributions délimitées et caviardées à la main
  de la première sélection. C'est le rythme d'un lecteur, pas d'une diffusion
  massive.
- **Découper et anonymiser automatiquement** est le préalable au reste du
  corpus. Aujourd'hui, les règles ne découpent que les courriels et les
  formulaires dactylographiés, et l'anonymisation automatique doit être relue
  à la main.
- **La moitié des pages écrites sont manuscrites** (142 000 sur 276 000) et
  ne sont pas encore lues
  ([#6](https://github.com/dataforgoodfr/15-Les-cahiers-pour-decider-et-agir/issues/6)).
- **La plateforme n'est pas choisie**
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

- [`analyse/`](analyse/) : mesures sur le corpus (typage des pages, communes,
  panel, tirage), outil d'annotation, découpage et caviardage des
  contributions. Sous-projet autonome, avec son `pyproject.toml`.
- [`backend/`](backend/) : extraction des fichiers des cahiers, base de données
  et interface d'administration.
- [`extraction/`](extraction/) : transcriptions extérieures (édition Chabin).
- [`docs/`](docs/) : règles sur les données.

Chaque sous-projet utilise [uv](https://docs.astral.sh/uv/) : par exemple `cd analyse && uv sync`,
puis `uv run ...`.

## Licence

Voir [LICENSE](LICENSE).
