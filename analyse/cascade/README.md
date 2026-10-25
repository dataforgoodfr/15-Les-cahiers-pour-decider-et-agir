# Cascade : du versement BnF aux pages écrites

Ce que devient chaque page numérisée, niveau par niveau. La figure et sa
lecture sont dans [`docs/corpus.md`](../../docs/corpus.md).

```bash
uv run python -m typage <racine du versement>/B[nN][fF]_GDN_*_PDF/CC --sortie data/typage/pages.csv
uv run python -m cascade <racine du versement> --typage data/typage/pages.csv
```

La racine du versement contient les dossiers `BnF_GDN_XX_PDF` (un par
département, chacun avec `CC`, `CO`, `CR`, `IL`). Attention à la casse : celui
des Hautes-Pyrénées s'écrit `Bnf_GDN_65_PDF`. Le typage peut être découpé
par département et passé en parallèle : `--typage` accepte un dossier de CSV.

Sorties :

- `data/cascade/cascade.csv` (hors git) : pages et part de chaque segment,
  documents par catégorie ;
- `../docs/cascade.svg` : la figure, versionnée. Elle ne contient que des
  comptes.
