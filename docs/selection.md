# Sélection de 100 contributions

Note pour l'association (#21). Elle propose une première sélection de
contributions à lire ; vos réactions fixeront les critères de la sélection
définitive (« gold », #29). Chaque critère ci-dessous est un choix : on peut
le changer et refaire le tirage en quelques minutes.

## Critères retenus

| Critère | Choix | Conséquence |
|---|---|---|
| Unité | La contribution | 100 textes d'auteurs différents, plutôt que 100 cahiers de longueur très inégale. |
| Objectif | Ressembler aux habitants de la France | Une commune a d'autant plus de chances de sortir qu'elle est peuplée. Paris pèse plus qu'un village, même si le village a écrit davantage. |
| Territoire | France entière | Toutes les régions, outre-mer compris. |
| Taille de commune et région | Chacune reçoit sa part de la population, à une unité près | Pas de région ni de taille de commune surreprésentée par hasard. |
| Écriture | Dactylographié seulement, pour commencer | Les cahiers entièrement manuscrits ne peuvent pas sortir tant que la lecture automatique des manuscrits n'est pas prête. |
| Nombre | 100 | Assez pour se faire une idée, trop peu pour mesurer des écarts fins. |

## Ce que la sélection ne dit pas

Les cahiers ne disent ni l'âge, ni le métier, ni le revenu de ceux qui ont
écrit. Ceux qui ont écrit sont des volontaires, plutôt âgés et ruraux, pas un
sondage. La sélection garantit seulement que les communes d'où viennent les
contributions ressemblent à la France.

## Questions pour l'association

1. **Outre-mer et Corse.** Avec 100 contributions, la Guyane (0,4 attendue)
   et la Corse (0,5) ne sortent pas. Faut-il leur garantir une contribution
   chacune ?
2. **Revenu.** Le niveau de revenu des communes varie de quelques points d'un
   tirage à l'autre. Faut-il le fixer, comme la taille et la région ?
3. **Manuscrits.** Ils représentent la moitié des pages. Faut-il attendre de
   pouvoir les inclure avant de lire la sélection ?
4. **Autre critère.** Y a-t-il un critère qui compte pour vous et qui manque
   (thème, longueur, période du débat…) ?

## Annexe : ce que donne le tirage

Tirage du 5 octobre 2026, graine 2026, sur 16 651 cahiers citoyens avec des
pages dactylographiées, dans 14 202 communes. Les communes sont décrites par
le recensement et Filosofi 2017.

| Profil des communes | France | ensemble des cahiers | sélection |
|---|---|---|---|
| retraités (15 ans et plus) | 27 % | 31 % | 28 % |
| cadres | 9 % | 7 % | 9 % |
| ouvriers | 12 % | 14 % | 12 % |
| 15 à 29 ans | 18 % | 14 % | 17 % |
| 60 à 74 ans | 16 % | 19 % | 16 % |

L'ensemble des cahiers est plus âgé et plus retraité que la France ; la
sélection corrige cet écart.

Méthode et rapport complet : `cd analyse && uv run python -m tirage`
(module `analyse/tirage`).
