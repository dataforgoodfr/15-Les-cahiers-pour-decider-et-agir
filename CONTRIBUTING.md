# Contribuer

Ce projet est actif : l'équipe y travaille pendant la saison 2026-2027 de
Data For Good, avec l'association
[Des cahiers pour décider et agir](https://www.decider-agir.fr/).

## Rejoindre le projet

Le recrutement officiel des bénévoles a lieu le **samedi 7 novembre 2026**,
à la journée de lancement de la saison Data For Good : à Paris (13e), dans
les bureaux de l'école ETHIC, de 11 h à 17 h.

En attendant, rejoignez le Mattermost de Data For Good
([inscription](https://authentik.services.dataforgood.fr/if/flow/main-page-enrollment/))
et présentez-vous dans le canal **Onboarding** : les bénévoles y sont les
bienvenus.

## Par où commencer

1. Lisez [le README](README.md), surtout « Où on en est » et « Avant la
   diffusion sur la plateforme » : ce qui est fait, ce qui bloque.
2. Lisez [docs/donnees.md](docs/donnees.md) : les cahiers contiennent des
   opinions politiques signées, et ce dépôt est public.
3. Choisissez un chantier ci-dessous et dites-le sur Mattermost avant de
   vous lancer, pour ne pas doubler quelqu'un.

## Les chantiers

Chaque chantier est une issue qui regroupe ses sous-issues.

| Chantier | Ce qu'il faut | Issues |
|---|---|---|
| Découper les cahiers en contributions | Python, règles, petits modèles de classification | [#5](https://github.com/dataforgoodfr/15-Les-cahiers-pour-decider-et-agir/issues/5), [#64](https://github.com/dataforgoodfr/15-Les-cahiers-pour-decider-et-agir/issues/64) |
| Anonymiser | Python, reconnaissance d'entités nommées, rigueur | [#7](https://github.com/dataforgoodfr/15-Les-cahiers-pour-decider-et-agir/issues/7), [#128](https://github.com/dataforgoodfr/15-Les-cahiers-pour-decider-et-agir/issues/128) |
| Lire les manuscrits (HTR) | Vision, modèles légers sur CPU | [#6](https://github.com/dataforgoodfr/15-Les-cahiers-pour-decider-et-agir/issues/6), [docs/htr.md](docs/htr.md) |
| Classer et regrouper les propositions | Traitement de la langue, statistiques | [#4](https://github.com/dataforgoodfr/15-Les-cahiers-pour-decider-et-agir/issues/4), [#94](https://github.com/dataforgoodfr/15-Les-cahiers-pour-decider-et-agir/issues/94) |
| La plateforme | Django, PostgreSQL, front | [#29](https://github.com/dataforgoodfr/15-Les-cahiers-pour-decider-et-agir/issues/29), [#38](https://github.com/dataforgoodfr/15-Les-cahiers-pour-decider-et-agir/issues/38) |
| Restitution et valorisation | Produit, design, rédaction | [#10](https://github.com/dataforgoodfr/15-Les-cahiers-pour-decider-et-agir/issues/10) |

Pas besoin de coder pour aider : l'annotation des cahiers (délimiter les
contributions, encadrer les données personnelles) sert de référence à
toutes les mesures, et se fait dans l'outil d'annotation d'`analyse/`.

Les étiquettes aident à choisir : `help wanted` (on cherche quelqu'un),
`good first issue` (pour démarrer), `exploration` (le livrable est une
mesure, pas du code), `à trancher` et `bloqué` (rien à coder pour l'instant).

## Installer

Chaque sous-projet (`analyse/`, `plateforme/`, `htr/`…) a son propre
environnement [uv](https://docs.astral.sh/uv/) :

```bash
cd analyse
uv sync
uv run pytest
```

Une fois après le clone, installez les hooks : ils refusent tout fichier de
données avant le commit (voir [docs/donnees.md](docs/donnees.md)).

```bash
uvx pre-commit install
```

Les cahiers eux-mêmes ne sont pas dans le dépôt. Une partie du travail
s'en passe : les tests tournent sans, et la plateforme charge ses
territoires depuis des sources publiques (INSEE, IGN).

## Proposer une modification

- Une branche par sujet, et de **petites PR, un module à la fois** : elles
  se relisent vite.
- Les commits suivent [Conventional Commits](https://www.conventionalcommits.org/fr/),
  en français : `feat(contributions): découper les lettres`.
- Code, commentaires, issues et PR sont en français.
- Une mesure accompagne chaque changement de méthode : ce qu'elle gagne,
  ce qu'elle perd, sur quelle référence.
- La CI relance les tests et les hooks sur chaque PR.

Nous préférons les petits modèles qui tournent en local aux gros modèles de
langage : moins d'énergie, et aucune donnée des cahiers ne sort de nos
machines.

## Les données

Avant toute contribution, lisez [docs/donnees.md](docs/donnees.md). En
résumé : aucune donnée des cahiers dans git, aucun extrait ni capture
d'écran dans les issues et les PR. Pour désigner une page, donnez le nom du
fichier PDF et le numéro de page.
