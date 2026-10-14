"""Paires de propositions à annoter, pour l'étalon de regroupement (issue #94).

    uv sync --group modeles
    uv run python -m paires [--propositions data/propositions/propositions.csv]
        [--modele sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2]
        [--tranches 5] [--par-tranche 100] [--hasard 100] [--reglage 0.33]
        [--graine 0] [--sortie data/paires]

Plonge chaque proposition (sortie de `python -m propositions`) avec un petit
modèle de phrases local, sur CPU (`paires.plongements`), puis tire des
paires (`paires.tirage`) :

- par tranches de ressemblance : les voisins les plus proches de chaque
  proposition sont coupés en tranches de même effectif, du moins au plus
  semblable, et chaque tranche fournit le même nombre de paires ;
- une part au hasard, presque toutes sans rapport, qui garde la mesure
  honnête loin des voisins.

Deux propositions d'une même contribution ne font pas une paire, ni deux
textes identiques (une méthode les fusionne sans peine). Une proposition
n'entre que dans une paire. Chaque paire va dans le lot de réglage ou de
test, gardé à part, en même part dans chaque tranche. Écrit dans la sortie :

- `plongements.npz` : les plongements, réutilisés tant que les propositions
  et le modèle ne changent pas ;
- `paires.csv` : une ligne par paire, son lot, sa tranche, sa similarité
  cosinus et les deux propositions, à juger : « même proposition », « même
  sujet, mesure différente » ou « sans rapport ».

La commande n'affiche que des comptes.
"""
