# Lire les manuscrits : banc d'essai HTR

La moitié des pages écrites du corpus sont manuscrites (142 000 sur 276 000)
et ne sont pas encore lues (#6). Ce document réunit les mesures faites
jusqu'ici pour choisir comment les lire. État au 19 octobre 2026.

## L'étalon

Deux étalons : la Charente-Maritime, décrite ici, et Dole (plus bas).

19 pages manuscrites de trois cahiers de Charente-Maritime (`01024`,
`00722`, `01193`), recadrées sur les scans BnF à leur résolution d'origine
(environ 150 ppp). Une 20ᵉ page, tronquée, est exclue.

- **Trois mains.** `00722` et `01024` sont lisibles ; `01193` est difficile,
  et c'est elle qui sépare les modèles.
- **Deux références humaines.** La lecture diplomatique de Hugo (orthographe
  d'origine conservée), qui sert de référence ci-dessous, et l'édition de
  Marie-Anne Chabin (orthographe corrigée, noms anonymisés). Les deux
  lectures humaines diffèrent entre elles de 2,8 % des caractères : c'est
  la précision qu'on peut espérer mesurer.
- **Petit.** 2 241 mots. Les écarts de moins d'un point ne veulent rien dire.

Les scans ne sont pas anonymisés : l'étalon reste hors du dépôt, avec les
scripts de mesure (`metriques.py`, `invention.py`) et de transcription.

## Ce qu'on mesure

- **CER, WER** : taux d'erreur par caractère et par mot, distance d'édition
  rapportée à la longueur de la référence. Variante normalisée : minuscules,
  sans ponctuation, apostrophes unifiées.
- **Mots inventés** : mots faux mais qui existent en français. Plausibles,
  ils ne se voient pas à la relecture sans l'image. C'est le défaut le plus
  grave pour une publication.
- **Charabia** : mots faux hors du vocabulaire. Faux, mais repérables.
- **Omis** : mots de la référence absents de la transcription. Une page
  rendue vide compte comme entièrement omise.

## Résultats

Référence : lecture de Hugo, 19 pages. Mots inventés, charabia et omis
contre la même lecture passée en orthographe corrigée.

| Modèle | Où il tourne | CER | WER | inventés | charabia | omis |
|---|---|---:|---:|---:|---:|---:|
| *Chabin (humaine)* | — | *2,8 %* | *11,9 %* | *1,9 %* | *0,2 %* | *1,0 %* |
| Claude Opus 5.5 | hébergé (Anthropic) | 2,2 % | 7,9 % | 2,0 % | 0,3 % | 0,3 % |
| Gemini 3.1 Pro | hébergé (Google) | 2,6 % | 9,4 % | 2,5 % | 0,1 % | 0,6 % |
| Kimi K3 | hébergé (Fireworks) | 4,1 % | 12,0 % | 3,4 % | 0,7 % | 0,3 % |
| Ember 1 | hébergé (Fireworks) | 4,9 % | 13,3 % | 4,4 % | 0,4 % | 0,7 % |
| Muse Spark | hébergé (Fireworks) | 5,0 % | 13,6 % | 4,9 % | 0,7 % | 1,1 % |
| Claude Haiku | hébergé (Anthropic) | 5,4 % | 14,7 % | 4,9 % | 0,6 % | 1,1 % |
| Gemma 4 31b, page entière | loué (Verda, UE), modèle de vision | 6,4 % | 17,3 % | 6,6 % | 1,1 % | 0,8 % |
| Gemma 4 31b, page entière, *reasoning* | loué (Verda, UE), modèle de vision | 6,7 % | 17,5 % | 7,0 % | 1,0 % | 0,6 % |
| Inkling | hébergé (Fireworks) | 8,2 % | 18,8 % | 7,2 % | 0,9 % | 2,0 % |
| DeepSeek V4.1 Flash | hébergé (Fireworks) | 8,9 % | 20,9 % | 10,0 % | 1,1 % | 0,8 % |
| Ornith-1.5 9b | local, modèle de vision | 9,6 % | 21,7 % | 9,1 % | 0,8 % | 1,2 % |
| GLM 5.3 Flash | hébergé (Fireworks) | 24,0 % | 31,6 % | 5,5 % | 0,9 % | 18,1 % |
| Gemma 4 31b, ligne par ligne, *reasoning* | loué (Verda, UE), modèle de vision | 24,4 % | 40,7 % | 26,5 % | 3,7 % | 1,5 % |
| Qwen 3.8 Max | hébergé (Fireworks) | 26,6 % | 32,9 % | 3,8 % | 1,1 % | 22,9 % |
| Manicule 2026 | local, HTR (kraken) | 27,8 % | 64,0 % | 17,7 % | 15,2 % | 4,7 % |
| McCATMuS | local, HTR (kraken) | 33,1 % | 75,3 % | 25,2 % | 22,5 % | 3,3 % |
| Manu McFondue | local, HTR (kraken) | 36,0 % | 77,9 % | 25,0 % | 23,5 % | 3,1 % |
| PyLaia RIMES | local, HTR | 41,8 % | 77,6 % | 17,2 % | 25,3 % | 19,1 % |
| Gemma 4 31b, ligne par ligne | loué (Verda, UE), modèle de vision | 39,5 % | 55,9 % | 41,3 % | 3,9 % | 1,3 % |
| PyLaia RIMES + 6-grammes | local, HTR | 43,5 % | 72,6 % | 26,5 % | 14,0 % | 19,9 % |
| Gemma 4 e2b, page entière | local, modèle de vision | 50,8 % | 60,9 % | 8,4 % | 2,1 % | 44,1 % |
| Gemma 4 e2b, ligne par ligne | local, modèle de vision | 96,8 % | 116,6 % | 88,8 % | 12,6 % | 1,9 % |
| GLM-OCR | local, modèle de vision | 187,9 % | 215,3 % | boucle | | |

Un CER au-delà de 100 % veut dire que le modèle écrit plus de texte que la
page n'en contient.

### Modèles hébergés

Opus 5.5 et Gemini 3.1 Pro lisent ces pages comme un humain, et Opus
n'invente pas plus que Chabin. Haiku se tient sur les mains lisibles mais
fait des contresens sur `01193` (« mécanicien » pour « médicament »,
« 85 » pour « 25 »).

Ils ne sont pas utilisables pour le corpus : les scans partent chez le
fournisseur, aux États-Unis, alors que les cahiers contiennent des opinions
politiques signées (RGPD, article 9). Ils donnent le plafond de ce qu'on
peut attendre d'une lecture automatique.

Les modèles de Fireworks (19 octobre 2026, `transcrire_fireworks.py`, même
consigne et même retirage que pour Ollama) sont dans le même cas : l'offre
serverless répartit les requêtes entre ses régions, États-Unis compris.

- **Kimi K3 s'approche d'Opus et de Gemini** (3,4 % de mots inventés), Ember
  1 et Muse Spark suivent, au niveau de Haiku.
- **Qwen 3.8 Max et GLM 5.3 Flash lisent bien les pages qu'ils rendent**,
  mais en rendent vides 3 et 2 sur 19.
- **Sur la main difficile, aucun ne tient** : 18 à 48 % de mots inventés
  sur `01193_p19`, contre 6 % pour Opus.
- Les poids de ces modèles ne sont pas vérifiés : seul un modèle à poids
  ouverts pourrait tourner chez un hébergeur européen pour le corpus.

### Modèles à poids ouverts

- **Gemma 4 31b, page entière, est le meilleur modèle qu'on puisse faire
  tourner nous-mêmes** (#44) : 6,6 % de mots inventés contre 9,1 % pour
  Ornith, mais trois fois plus qu'Opus. Sur la main difficile, il invente
  encore 28 % des mots de `01193_p19`. Q4_K_M (20 Go) sous Ollama, sur une
  A100 40 Go louée chez Verda (Finlande) : environ 5 s par page.
- **Le *reasoning* n'apporte rien** à Gemma 4 31b en page entière (7,0 %),
  pour un temps dix fois plus long (49 s par page). Il faut relever le
  plafond de jetons : à 2 048, la réflexion l'épuise et une page sur deux
  sort vide.
- **Le ligne par ligne du Campus Condorcet est à proscrire** : 41 % de mots
  inventés, 27 % avec le *reasoning* (10 à 24 min par page sur `01193`).
  Privé du contexte de la page, le modèle complète chaque fragment de ligne
  par du français plausible.
- **Ornith-1.5 9b**, le meilleur petit modèle, invente : sur la main
  difficile, il écrit un français fluide sans rapport avec la page (57 % de
  mots inventés sur `01193_p19`). Aucun indicateur automatique ne le
  détecte.
- **Les HTR légers ne sont pas utilisables tels quels** : un caractère sur
  trois faux. Leurs erreurs se voient davantage (autant de charabia que de
  mots inventés). Manicule 2026 (LaMOP, XIXᵉ-XXᵉ siècles) arrive en tête,
  devant McCATMuS, à l'inverse des cahiers de 1789.
- **PyLaia RIMES**, le seul entraîné sur des lettres manuscrites
  contemporaines, lit bien les écritures posées (10 % sur `00722_p11`) mais
  soude les mots et en omet un sur cinq. Son modèle de langage n'aide pas :
  il remplace du charabia par des mots inventés.
- **Les petits modèles de vision** (Gemma 4 e2b, GLM-OCR) omettent la moitié
  de la page ou bouclent.

### La segmentation pèse

Les HTR lisent ligne par ligne, après une segmentation par kraken. Sur
`01193`, elle coupe les lignes en fragments (56 lignes trouvées pour 11 sur
`p19`), et tous les HTR y dépassent 50 % d'erreur, même sur des pages
qu'Ornith lit à 13-17 %. Une partie de l'écart se gagnera en segmentant
mieux.

### Un second étalon : Dole

La transcription du cahier citoyen de Dole (Jura), réalisée en 2019 par
Anaïs Rico--Perrier (alors en M2 Analyse du discours, université Marie et
Louis Pasteur, anciennement de Franche-Comté) et Marion Bendinelli, qui nous
autorise à la réutiliser. Faite sur le cahier consulté en mairie le
4 février 2019, avant sa clôture ; ses pages sont rapprochées des pages BnF
par les feuilles dactylographiées collées, retrouvées sans doute dans la
couche texte. 31 pages manuscrites, 5 204 mots, pages entières non
recadrées ; l'étalon reste hors du dépôt (`../dole/`).

| Modèle | Où il tourne | CER | WER | inventés | charabia | omis |
|---|---|---:|---:|---:|---:|---:|
| Gemma 4 31b, page entière | loué (Verda, UE), modèle de vision | 11,1 % | 23,6 % | 12,2 % | 2,0 % | 3,1 % |

Gemma 4 31b y invente deux fois plus qu'en Charente-Maritime, à 13 s par
page sur une A100. La comparaison reste fragile tant que l'étalon n'a
qu'une lecture humaine (sa version régularisée n'en diffère que de 0,4 %) :
sans plancher humain, on ne sait pas quelle part de l'écart tient aux
choix de la transcription, faite pour l'analyse du discours (numéros de
page, ajouts en marge). Une seconde lecture est en cours. Les modèles
hébergés n'y ont pas été passés : les scans ne sont pas anonymisés.

## Ce que ça dit pour la suite

Aucun modèle à poids ouverts ne lit aujourd'hui les manuscrits assez bien
pour publier : le meilleur, Gemma 4 31b, invente encore un mot sur quinze,
et bien plus sur les mains difficiles ou à Dole. Il lirait les 142 000
pages manuscrites en huit à vingt jours sur une A100 louée en Europe, selon
la taille des pages (5 à 13 s chacune). Deux pistes, à mesurer sur ces
étalons :

1. **Affiner Manicule 2026 sur nos écritures.** Les transcriptions de
   Chabin, alignées sur les lignes des scans, donnent des données
   d'entraînement, comme les transcriptions des Archives du Morbihan pour
   1789 (CER de 0,24 à 0,09 après affinage). Les trois cahiers de l'étalon
   sont exclus de l'entraînement. Les pages de Dole hors étalon (incertaines
   au rapprochement, ou dactylographiées et manuscrites mêlées) en donnent
   d'autres.
2. **Mieux segmenter** les pages recadrées et les écritures irrégulières.

Une HTR médiocre suffit déjà pour une autre tâche : retrouver dans les scans
la page où commence une contribution manuscrite de l'édition Chabin, par un
alignement approximatif de son texte.

## Sources des modèles

| Modèle | Licence | Référence |
|---|---|---|
| Manicule 2026 Français moderne | CC0 | [10.5281/zenodo.21195087](https://doi.org/10.5281/zenodo.21195087) |
| McCATMuS | CC BY 4.0 | [10.5281/zenodo.13788177](https://doi.org/10.5281/zenodo.13788177) |
| Manu McFondue v4 | CC BY 4.0 | [10.5281/zenodo.10886224](https://doi.org/10.5281/zenodo.10886224) |
| PyLaia RIMES (Teklia) | MIT | [huggingface.co/Teklia/pylaia-rimes](https://huggingface.co/Teklia/pylaia-rimes) |

Kraken 7.1.1 et PyLaia 1.1.2, sur CPU. Kraken 7.1.1 perd des lignes sous
numpy 2 (« Extracting line failed ») : il faut `numpy<2`.
