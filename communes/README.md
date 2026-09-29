# Communes : variables INSEE des communes du corpus

Issue #19. Pour chaque code INSEE du corpus : nom, type d'entité, département,
région, population et degré de densité.

```bash
uv run python -m communes <corpus.csv> [--colonne code_insee] [--sortie data/communes]
```

L'entrée a une ligne par commune ; ses colonnes sont recopiées. Les sources
sont téléchargées une fois dans `data/sources/`. Les sorties vont dans
`data/communes/` (hors git) :

- `communes.csv` : les communes rattachées ;
- `non_rattaches.csv` : les autres, avec la raison.

## Sources et millésimes

| Variable | Source | Millésime |
|---|---|---|
| nom, type, département, région | [Code officiel géographique](https://www.insee.fr/fr/information/3720946) | 1er janvier 2019 |
| `population_2017` | [Populations légales](https://www.insee.fr/fr/statistiques/4265429), population municipale | millésime 2017, limites au 1er janvier 2019 |
| `densite` (1 à 4) | [Grille communale de densité](https://www.insee.fr/fr/information/2114627) | géographie au 1er janvier 2021 |
| passage d'un millésime à l'autre | [Mouvements de communes](https://www.insee.fr/fr/information/8740222) | depuis 1943 |

**Tout est au millésime 2019**, celui des codes des noms de fichiers : des
communes ont fusionné depuis, et un référentiel plus récent en perdrait.

**La grille de densité n'existe pas dans la géographie de 2019.** On prend
celle de 2021, en suivant les fusions intervenues entre-temps : une commune
fusionnée reçoit la densité de sa commune nouvelle, et la colonne `note` le
dit.

Licence Ouverte 2.0 : toute réutilisation mentionne « Source : Insee » et les
millésimes.

## Cas particuliers

- **Commune déléguée ou associée, arrondissement municipal** : département,
  région et densité de la commune parente. Leur population est déjà comptée
  dans celle de la parente (`population_incluse_dans`) : ne pas sommer les deux.
- **Code supprimé au 1er janvier 2019** (le système de dépôt utilisait parfois
  le COG 2018) : rattaché à la commune nouvelle, type `supprimée`, sans
  population propre.
- **Paris, Lyon, Marseille** : les populations légales ne les donnent que par
  arrondissement ; la population de la commune est leur somme.
- **Mayotte** : absente des populations légales millésimées 2017.
- **Non rattachés** : `00000` (commune non renseignée), collectivités
  d'outre-mer hors COG des communes, `99999` (étranger), codes disparus avant
  2018.
