# Analyse du corpus

Mesures sur le versement BnF des cahiers citoyens : des comptes, jamais de
texte. Les commandes se lancent depuis ce dossier ; les sources et les sorties
vont dans `data/` (hors git).

```bash
cd analyse
uv sync
uv run pytest
```

| Module | Issue | Ce qu'il fait |
|---|---|---|
| `typage` | #17 | Type chaque page : vierge, dactylographiée ou manuscrite |
| `cascade` | #41 | Du versement aux pages écrites, niveau par niveau |
| `communes` | #19 | Variables INSEE de 2019 des communes du corpus |
| `communes.representativite` | #20 | Écart du corpus (ou d'un panel) à la France |
| `panel` | #22 | Panel aligné sur l'échantillon du Campus Condorcet |

Chaque module décrit sa commande dans sa docstring ou son README.
