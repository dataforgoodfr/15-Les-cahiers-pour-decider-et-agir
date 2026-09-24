# Backend Cahier pour décider et agir

Ce répertoire contient le code et scripts permettant l'extraction et le traitement des données des fichiers consituant les cahiers citoyens

## Installation

Pré-requis:
 - Python 3.13+
 - uv

Installation des dépendances

```
uv sync
```

Initialisation des variables d'environnement:

Remplacer `cpda` par vos paramètres de connexion à la base de données

```
$ export CPDA_LOGGING_CONFIGURATION_FILE="logging.ini"
$ export CPDA_PG_DSN=postgresql+asyncpg://cpda:cpda@localhost/cpda
```

## Initialisation

Lancer le script suivant pour charger la nomenclature des région/départements/communes

```
python chargement_admin.py
```

## Chargement des fichiers PDF

```
python -m extraction <chemin_vers_les_pdf> -r
```

`chemin_vers_les_pdf` : emplacement des fichiers PDF à traiter
`-r` : permet d'indiquer si le traitement doit traiter récursivement les fichiers PDF situés dans des sous-répertoires.

## Reconnaissance des textes

Ce traitement permet de mesurer la qualité des textes brut

```
python -m reconnaissance.reco_texte_pdf
```

Les résultats de ce traitement sont consultables dans la table `reconnaissance`

# Modèle de données

Voir [./docs/modele.md]