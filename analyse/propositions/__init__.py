"""Les propositions des contributions de l'édition Chabin (issue #94).

    uv run python -m propositions
        [--extraction ../data/cahiers_chabin-extraction.json]
        [--echantillon 50] [--graine 0] [--sortie data/propositions]

Découpe chaque contribution transcrite en propositions, par règles
(`propositions.decoupage`) : l'unité de l'étalon de regroupement, dont on
tirera des paires à annoter. Écrit dans la sortie :

- `propositions.csv` : une ligne par proposition, avec son contexte (le
  dernier intitulé) et sa forme (puce ou phrase) ;
- `verification.csv` : les propositions de contributions tirées au hasard,
  avec deux colonnes à remplir par les volontaires, `decoupage` (« juste »,
  « à couper », « à fusionner ») et `nature` (« proposition » ou
  « témoignage »), pour mesurer les règles avant de s'en servir.

Les transcriptions sont anonymisées par l'édition, dont la réutilisation est
accordée. La commande n'affiche que des comptes.
"""
