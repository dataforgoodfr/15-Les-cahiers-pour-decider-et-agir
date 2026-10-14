# Lecture des manuscrits (HTR)

Lit les pages manuscrites du versement avec un modèle HTR léger, sur CPU,
sans LLM : kraken segmente la page en lignes (modèle `blla`), puis un modèle
de reconnaissance lit chaque ligne. Le choix du modèle vient du banc d'essai
sur l'étalon de Charente-Maritime ([docs/htr.md](../docs/htr.md)) :
**Manicule 2026** par défaut.

Aucun modèle générique ne lit encore assez bien pour publier (un caractère
sur quatre faux). Cette lecture sert à retrouver des textes déjà transcrits
dans les scans (les contributions manuscrites de l'édition Chabin), puis à
préparer l'affinage d'un modèle sur nos écritures.

## Installation

Un sous-projet à part : kraken 7.1.1 demande Python 3.12 et numpy 1 (sous
numpy 2, il perd des lignes sans arrêter le traitement), quand `analyse` est
en Python 3.14 et numpy 2.

```bash
cd htr
uv sync
uv run pytest
```

## Usage

```bash
uv run python -m htr --extraction ../data/cahiers_chabin-extraction.json
```

Les pages à lire sont celles que `analyse/typage` a classées manuscrites
(`--types` pour en changer). Pour chaque scan, la commande écrit
`../data/htr/<modèle>/<scan>.jsonl` : une ligne par page lue,

```json
{"page": 3, "lignes": [{"texte": "…", "cadre": [x0, y0, x1, y1]}]}
```

avec le cadre en points de la page affichée, comme les lignes de la couche
texte dans `analyse`. Un scan déjà lu n'est pas relu. Le modèle est
téléchargé depuis Zenodo et vérifié par sa somme de contrôle
(`htr/modeles.py`).

Compter une dizaine de secondes par page sur 8 cœurs. Le texte reconnu
n'est pas anonymisé : il reste dans `data/`, hors git ; la commande
n'affiche que des comptes.
