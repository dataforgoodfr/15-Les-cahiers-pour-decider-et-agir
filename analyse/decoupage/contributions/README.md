# Découpage des contributions (#5)

```bash
uv run python -m decoupage.contributions
```

Repère où commencent les contributions des cahiers tirés pour l'association
(#21), par des règles décrites dans `regles.py` : courriels imprimés,
formulaires à gabarit répété, et lettres. Une page ouvre une lettre si ses
premières lignes portent un titre de doléance ou une salutation, ou si la
page précédente finit par une formule de politesse ; la règle ne s'applique
pas sur une page où une autre a trouvé un début.

L'en-tête d'un formulaire se reconnaît à l'OCR près (75 % de caractères
communs) ; quand il est méconnaissable, deux autres lignes de la première
page du formulaire suffisent. Ces débuts trouvés « à l'OCR près » ont leur
propre liste à revoir.

Le début du cahier ouvre une contribution, sauf si une page manuscrite,
que les règles ne lisent pas, précède la première page dactylographiée.

## Définition

Une contribution est un texte d'un même auteur, ou d'un même groupe, d'un
seul tenant. Une liste de propositions numérotées par une même personne
compte pour une contribution ; un compte rendu de réunion collective aussi.

## La référence : les cahiers délimités

La référence est faite à la main sur les cahiers du tirage : pour choisir
sa contribution, le lecteur note le début de toutes celles du cahier
(tâche « selection » de l'outil d'annotation, voir `panels.selection`). Un cahier
compte dès que sa dernière page est vue. `uv run python -m decoupage.contributions`
affiche la précision (part des débuts trouvés qui sont justes) et le rappel
(part des vrais débuts trouvés) sur leurs pages dactylographiées.

Un début trouvé est juste si une note tombe sur le même tronçon de page : à
moins de 30 points (environ deux lignes), ou jusqu'à 250 points sans passer
un autre début trouvé. Le lecteur ouvre un formulaire en haut de son
en-tête (logo, titre), la règle à sa ligne la plus fréquente, plus bas.

Au 9 octobre 2026, sur 32 cahiers délimités (361 débuts sur 614 pages
dactylographiées) : précision 86 %, rappel 34 %. Les formulaires sont
trouvés à 99 %, avec 97 % de précision ; les courriels sont trop rares
pour être mesurés (4 débuts). Le reste des débuts manqués est surtout des
lettres, qu'aucune règle ne découpe.

Au 13 octobre 2026, sur les 98 cahiers délimités du tirage qui ont des pages
dactylographiées (1 536 débuts sur 2 548 pages) : précision 77 %, rappel
48 % sans la règle des lettres ; 74 % et 66 % avec elle (64 % de précision
pour la règle seule). 19 cahiers restent sans aucune règle. Les indices de
mise en page (police du corps ou marge qui changent d'une page à l'autre)
n'atteignent qu'environ 46 % de précision : ils ne sont pas retenus.

Au 14 octobre 2026, les formulaires de deux feuilles (#64) : la tête du
gabarit est prise sur la première feuille, la plus riche en lignes du
gabarit, et jamais sur une ligne qui revient plusieurs fois par page ; une
seconde feuille n'ouvre ni formulaire ni lettre. Les gabarits passent de
85 % à 91 % de précision (562 à 540 débuts, 475 à 494 justes), rappel 96 % ;
toutes règles, 75 % de précision et 66 % de rappel. Dans un cahier, l'OCR ne
lit la première feuille qu'à partir de ses questions, à 270 points du haut :
ses débuts sont justes mais comptés faux, trop bas. Restent les feuilles de
suite d'un même auteur (numéro et « suite » écrits à la main), les
formulaires laissés vierges et les pages numérisées deux fois.

Le même jour, « propositions » ne compte plus comme titre de lettre : il
n'ouvrait une vraie lettre qu'une fois sur trois (33 débuts, 10 justes).
Lettres : 67 % de précision ; toutes règles : 76 % de précision, 65 % de
rappel. Quatre cahiers font plus de la moitié des lettres fausses
restantes, sans indice de forme commun (longueur de la ligne, rang, fin de
la page précédente) : ils sont à regarder dans la liste « Lettres
repérées ».

Regardés après masquage (GLiNER), ces quatre cahiers montrent des pages
qui continuent un document : numéro de page (« Page 2 sur 5 », « P.3/5 »),
pied et en-tête d'impression d'un courriel (« 3 sur 7 09:50 ») ou titre
courant, et des envois de la mairie sans contribution. Une page numérotée
au-delà de la première n'ouvre plus de lettre : 35 débuts de moins, dont
un seul juste ; lettres 73 % de précision, toutes règles 78 % et 65 % de
rappel. Le numéro de la page précédente et l'en-tête repris d'une page à
l'autre retirent autant de vrais débuts que de faux : écartés.

Les en-têtes « Sujet : » et « Pour : » (messageries d'entreprise, Lotus
Notes) sont reconnus : les envois de la mairie de Brest sont des courriels,
et non plus des lettres. La mesure n'en change pas (1 003 débuts justes au
lieu de 1 004) : un courriel de mairie seul sur sa page reste un début, car
la délimitation en compte un le plus souvent ; ne plus l'ouvrir retire 8
débuts justes.

Les listes « Courriels repérés », « Formulaires (gabarits) repérés » et
« Lettres repérées » montrent les débuts trouvés dans l'outil d'annotation, pour les revoir.

## Les pages sans règle : un modèle

Au 24 octobre 2026, sur les 98 cahiers délimités, 533 débuts restent
manqués par les règles, et 378 d'entre eux sont en haut d'une page où
aucune règle ne trouve rien. Sur ces pages, la question est de savoir si la
page ouvre une contribution ou continue la précédente : 27 % en ouvrent une.

Une régression logistique y répond (`decoupage.contributions.pages`), sur des
indices de forme comparés à la page lue précédente : police, taille du
corps et marge qui changent, mots communs aux deux pages, première ligne
courte ou en minuscule, date en tête, numéro de page, politesse en fin de
précédente, page manuscrite ou vierge intercalée. Les indices de mise en
page comptent aussi par leur rang dans le cahier, car chaque cahier a ses
habitudes. Le modèle tient en quelques poids, s'entraîne en quelques
secondes sur CPU, avec numpy seul.

Chaque cahier délimité est jugé par un modèle entraîné sans lui (validation
croisée en cinq plis, par cahier). Au seuil de 0,5, le modèle ouvre 332
pages, dont 60 % à raison ; toutes règles et modèle, la précision passe de
78 % à 74 % et le rappel de 65 % à 78 %. Les cahiers sans aucun début
trouvé passent de 19 à 10.

| seuil | débuts trouvés | précision | rappel |
|---|---|---|---|
| règles seules | 1 285 | 78 % | 65 % |
| 0,7 | 1 435 | 76 % | 71 % |
| 0,6 | 1 517 | 76 % | 75 % |
| 0,5 | 1 617 | 74 % | 78 % |
| 0,4 | 1 709 | 73 % | 81 % |

Seuls, la taille du corps (AUC 0,77) et la marge (0,71) sont les meilleurs
indices ; le modèle entier atteint 0,82. Cinq cahiers font la moitié des
pages ouvertes à tort. Les pages ouvertes sont dans la liste « Pages qui
ouvrent une contribution selon le modèle ». La mesure sur les tronçons de
test (`decoupage.troncons`, départements jamais vus) reste à faire.

## Les pages mixtes

Au 25 octobre 2026, le typage rend mixte toute page lisible dont la moitié
de l'encre est hors des mots imprimés (#165) : 18 % des pages jusqu'ici
dactylographiées, surtout des formulaires remplis à la main. Ne lire que
les pages dactylographiées aurait privé la règle des formulaires de
l'essentiel de ses débuts (540 → 197) : le découpage lit donc les pages
dactylographiées et mixtes, toutes celles qui ont une couche imprimée
lisible. Sur les 98 cahiers délimités (2 617 pages lues, dont 685 mixtes,
1 600 débuts) : règles et modèle, précision 75 %, rappel 81 % ; sur les
seules pages mixtes, 82 % et 74 % ; formulaires, 92 % et 99 %.

## Mesure sur l'édition Chabin

`uv run python -m decoupage.chabin` retrouve dans l'OCR les contributions que
Marie-Anne Chabin dit dactylographiées ou imprimées d'une messagerie
(Charente-Maritime) et y mesure les règles, sans relecture. Au 9 octobre 2026,
sur 134 cahiers :

- 269 contributions dactylographiées sur 340 et 17 courriels sur 22 sont
  retrouvés. Les autres sont surtout des textes collés que l'OCR du versement
  n'a presque pas lus (une vingtaine de mots par page).
- Les règles trouvent 11 % des débuts, avec une précision de 25 % (54 % sur
  les cahiers dont toutes les contributions sont retrouvées) : la plupart
  des contributions dactylographiées sont des lettres, qu'aucune règle ne
  découpe, et les manuscrits n'ont pas de position dans la référence.
- Le « début du cahier » tombait d'abord presque toujours en page 3 : la
  couverture imprimée de l'association des maires, que le typage ne marque
  pas comme page de service. `python -m corpus.ouvertures` repère ces pages dans
  tout le versement (3 115, dont 312 en Gironde et 180 en
  Charente-Maritime) ; les règles les sautent, ce qui double leur
  précision sur l'édition Chabin.
- Avec la règle des lettres (13 octobre 2026), écrite sur le tirage et
  non sur cette édition, les règles trouvent 50 % des débuts avec une
  précision de 49 %.
- Les formulaires repérés (3 cahiers, 44 débuts) sont des formulaires remplis
  à la main : l'édition les classe en manuscrits, sans position dans l'OCR.
  La référence ne peut pas les juger.
