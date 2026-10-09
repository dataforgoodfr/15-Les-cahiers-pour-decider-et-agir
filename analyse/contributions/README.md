# Découpage des contributions (#5)

```bash
uv run python -m contributions
```

Repère où commencent les contributions des cahiers tirés pour l'association
(#21), par des règles décrites dans `regles.py` : courriels imprimés et
formulaires à gabarit répété. Les autres cahiers restent à découper, par une
méthode encore à décider.

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
(tâche « selection » de l'outil d'annotation, voir `selection`). Un cahier
compte dès que sa dernière page est vue. `uv run python -m contributions`
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

Les listes « Courriels repérés » et « Formulaires (gabarits) repérés »
montrent les débuts trouvés dans l'outil d'annotation, pour les revoir.

## Mesure sur l'édition Chabin

`uv run python -m chabin` retrouve dans l'OCR les contributions que
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
  pas comme page de service. `python -m ouvertures` repère ces pages dans
  tout le versement (3 115, dont 312 en Gironde et 180 en
  Charente-Maritime) ; les règles les sautent, ce qui double leur
  précision sur l'édition Chabin.
- Les formulaires repérés (3 cahiers, 44 débuts) sont des formulaires remplis
  à la main : l'édition les classe en manuscrits, sans position dans l'OCR.
  La référence ne peut pas les juger.
