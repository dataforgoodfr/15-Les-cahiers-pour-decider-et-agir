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
a besoin d'une sélection « gold » de moins d'une centaine de cahiers pour ses
médias. Cette sélection doit sortir d'une méthode de tirage automatique, dont
les critères restent à définir avec l'association
([#21](https://github.com/dataforgoodfr/15-Les-cahiers-pour-decider-et-agir/issues/21)).
Les chantiers de données visent la qualité nécessaire pour ce panel, pas
l'exhaustivité.

Le produit doit être décidé en novembre 2026, pour l'arrivée des bénévoles ;
livraison au premier trimestre 2027. Le détail est dans l'issue
[#29](https://github.com/dataforgoodfr/15-Les-cahiers-pour-decider-et-agir/issues/29).

## Où on en est

- **Le contenu est encore mal balisé.** Il faut le structurer avant de pouvoir
  l'exploiter.
- **Une analyse des cahiers est en cours** pour dégager un panel représentatif.
- **De nombreux cahiers sont au format texte.** Leur exploitation demande un
  travail particulier, mené par le Campus Condorcet.

Le POC de l'été 2026 a porté sur trois départements (Ain, Eure-et-Loir,
Mayenne). Son code est dans [dataforgoodfr/cahier_doleances](https://github.com/dataforgoodfr/cahier_doleances).

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
  panel). Sous-projet autonome, avec son `pyproject.toml`.
- [`docs/`](docs/) : règles sur les données.

Chaque sous-projet utilise [uv](https://docs.astral.sh/uv/) : `cd analyse && uv sync`,
puis `uv run ...`.

## Licence

Voir [LICENSE](LICENSE).
