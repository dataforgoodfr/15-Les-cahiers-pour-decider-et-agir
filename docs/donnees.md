# Données

Les cahiers citoyens de 2019 contiennent des opinions politiques signées, souvent
avec nom, adresse ou téléphone. Ce sont des données sensibles au sens de
l'article 9 du RGPD. Ce dépôt est **public** : tout ce qui y entre (code, issues,
PR, captures d'écran) est publié.

## Règles de base

1. **Aucune donnée des cahiers dans git.** Ni PDF, ni texte extrait, ni base, ni
   export, ni échantillon « juste pour tester ».
2. **Aucun extrait de cahier dans les issues ou les PR.** Pas de copie de texte,
   pas de capture d'écran de page. Pour désigner une page, on donne son
   identifiant (nom du fichier PDF et numéro de page).

## Garde-fous

Le hook `pas-de-donnees` refuse tout fichier de données (PDF, images, tables,
bases, archives, texte brut, dossiers `data/`) avant le commit. Il ne protège
que si pre-commit est installé, une fois après le clone :

```bash
uvx pre-commit install
```

La CI relance les mêmes vérifications sur chaque PR, mais elle arrive après le
push : sans le hook local, un fichier poussé sur une branche est déjà public.
