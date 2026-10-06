# Extraction de transcriptions existantes

Ce répertoire contient le code permettant d'extraire des transcriptions existantes fiables.
Ces transcriptions peuvent-être utiles pour la validation des transcriptions générées
par le(s) modèle(s) de reconnaissance. Elles peuvent aussi être utilisées pour les modèles de
classification ou la navigation au travers de contributions.

Ces transcriptions sont produites dans des fichiers plats (JSON ou JSONL).

## Transcriptions existantes
### Marie-Anne Chabin
Marie-Anne Chabin a effectué des transcriptions des cahiers de doléances pour plus
d'une centaine de communes de Charente-Maritime à partir de février 2024.
Ces transcriptions snt disponibles sur son [blog](https://www.marieannechabin.fr/edition-de-cahiers-doleances-2019/).

## Gestion des fichiers
On effectue la gestion de ces transcriptions de manière indépendante du backend pour avoir:

* **Compatibilité native avec l'écosystème Python/IA :** Assurer un lien simple avec les
bibliothèques d'analyse de données et de machine learning (Pandas, HuggingFace...).
* **Inspection et débogage immédiats :** Pouvoir balayer les fichiers de transcriptions produits
par programme ou de manière visuelle sans faire appel au backend.
* **Infrastructure additionnelle simplifiée:** Limiter le besoin de la BD et permettre de charger
les données dans une ou plusieurs BDs sans recalculer les transcriptions.
* **Portabilité et archivage simplifiés :** Pour partager les résultats ou archiver une
expérimentation, un zip d'un répertoire suffit.

## Installation

Pré-requis:

- Python 3.14+
- uv

Installation des dépendances

```
uv sync
```
