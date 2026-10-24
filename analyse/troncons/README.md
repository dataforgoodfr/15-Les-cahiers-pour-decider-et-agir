# Tronçons de test du découpage (#5)

```bash
uv run python -m troncons
```

Les 98 cahiers délimités pour le tirage de l'association (`selection`)
servent à écrire les règles du découpage (`contributions`) et à entraîner
le modèle : mesurer sur eux flatte les chiffres. Ils ne couvrent que 56
départements du versement.

La référence de test prend un tronçon de 10 pages écrites dans chacun des
autres départements (hors versements 00, sans commune, et 99, étranger) :
des numérisations et des usages locaux que le découpage n'a jamais vus. Dans
chaque département, une page dactylographiée est tirée au hasard, et le
tronçon part d'elle. Chaque tronçon a pour poids les pages dactylographiées
de son département.

Au 24 octobre 2026 (graine 2026) : 41 tronçons, 320 pages écrites, dont 208
dactylographiées. Beaucoup de cahiers ont moins de 10 pages écrites.

La liste « decoupage » de l'outil d'annotation (tâche « decoupage ») les
montre un à un : on y note les débuts de contribution, manuscrits compris,
sans caviarder.
