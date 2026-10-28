# Classification des contributions (draft)

Ce projet permet d'analyser automatiquement des contributions afin d'en extraire les idées principales.
Il segmente le texte et classifie chaque idée selon une taxonomie stricte (Thème > Sous-thème).

**À noter :** Il s'agit de la **première étape** d'un projet plus vaste. Ce prototype sert à valider l'extraction et la
structuration de données à l'aide d'un Modèle de Langage (LLM) exécuté localement.

## Objectif du projet

L'objectif actuel de ce script (`__main__.py`) est de lire un texte fourni par l'utilisateur, de le découper en
plusieurs segments logiques, et de renvoyer un format structuré contenant pour chaque segment :

* Le texte extrait mot pour mot (verbatim).

* Le grand thème abordé (ex: *Transition écologique*, *Démocratie et citoyenneté*...).

* Le sous-thème spécifique associé.

* Une courte justification du choix de classification.

Ce processus garantit que les contributions non structurées peuvent être catégorisées et taggées.

## Prérequis

Pour faire fonctionner ce projet, vous avez besoin de :

1. **Python** avec le gestionnaire de paquets `uv`.

2. **Ollama** installé sur votre machine (pour faire tourner le LLM en local).

3. Le modèle **Mistral** téléchargé via Ollama.

## Comment lancer le projet

Le traitement se fait en deux temps : il faut d'abord démarrer le serveur d'intelligence artificielle, puis lancer le
script d'analyse.

### 1. Lancer Ollama

Ouvrez un premier terminal et démarrez le serveur Ollama avec le modèle Mistral :

```
ollama run mistral

```

*(Laissez ce terminal ouvert en arrière-plan. Si le modèle n'est pas encore sur votre machine, Ollama le téléchargera
automatiquement).*

### 2. Lancer le script d'analyse

Ouvrez un second terminal, placez-vous dans le dossier `analyse`, et exécutez le script `__main__.py` en lui
passant votre texte entre guillemets :

```
uv run ./classification/__main__.py "La question de réduire radicalement notre influence\
  néfaste sur le climat doit être considérée comme l'urgence primordiale.\
   Les gros salaires sont donc plafonnés."

```

*(Si votre texte contient lui-même des guillemets doubles, vous pouvez entourer l'ensemble de votre texte avec des
guillemets simples `'...'`)*.

## Dépendances techniques

Le projet utilise les bibliothèques suivantes (gérées par `uv`) :

* `openai` : Pour communiquer avec l'API locale d'Ollama.

* `pydantic` : Pour définir la structure stricte des données attendues (schéma de validation).

* `instructor` : Pour forcer le LLM à respecter parfaitement le schéma de validation Pydantic.