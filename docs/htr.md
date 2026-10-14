# Lire les manuscrits : banc d'essai HTR

La moitié des pages écrites du corpus sont manuscrites (142 000 sur 276 000)
et ne sont pas encore lues (#6). Ce document réunit les mesures faites
jusqu'ici pour choisir comment les lire. État au 14 octobre 2026.

## L'étalon

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
- **Omis** : mots de la référence absents de la transcription.

## Résultats

Référence : lecture de Hugo, 19 pages. Mots inventés, charabia et omis
contre la même lecture passée en orthographe corrigée.

| Modèle | Où il tourne | CER | WER | inventés | charabia | omis |
|---|---|---:|---:|---:|---:|---:|
| *Chabin (humaine)* | — | *2,8 %* | *11,9 %* | *1,9 %* | *0,2 %* | *1,0 %* |
| Claude Opus 5.5 | hébergé (Anthropic) | 2,2 % | 7,9 % | 2,0 % | 0,3 % | 0,3 % |
| Gemini 3.1 Pro | hébergé (Google) | 2,6 % | 9,4 % | 2,5 % | 0,1 % | 0,6 % |
| Claude Haiku | hébergé (Anthropic) | 5,4 % | 14,7 % | 4,9 % | 0,6 % | 1,1 % |
| Ornith-1.5 9b | local, modèle de vision | 9,6 % | 21,7 % | 9,1 % | 0,8 % | 1,2 % |
| Manicule 2026 | local, HTR (kraken) | 27,8 % | 64,0 % | 17,7 % | 15,2 % | 4,7 % |
| McCATMuS | local, HTR (kraken) | 33,1 % | 75,3 % | 25,2 % | 22,5 % | 3,3 % |
| Manu McFondue | local, HTR (kraken) | 36,0 % | 77,9 % | 25,0 % | 23,5 % | 3,1 % |
| PyLaia RIMES | local, HTR | 41,8 % | 77,6 % | 17,2 % | 25,3 % | 19,1 % |
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

### Modèles locaux

- **Ornith-1.5 9b est le meilleur modèle local**, mais il invente : sur la
  main difficile, il écrit un français fluide sans rapport avec la page
  (57 % de mots inventés sur `01193_p19`). Aucun indicateur automatique ne
  le détecte.
- **Les HTR légers ne sont pas utilisables tels quels** : un caractère sur
  trois faux. Leurs erreurs se voient davantage (autant de charabia que de
  mots inventés). Manicule 2026 (LaMOP, XIXᵉ-XXᵉ siècles) arrive en tête,
  devant McCATMuS, à l'inverse des cahiers de 1789.
- **PyLaia RIMES**, le seul entraîné sur des lettres manuscrites
  contemporaines, lit bien les écritures posées (10 % sur `00722_p11`) mais
  soude les mots et en omet un sur cinq. Son modèle de langage n'aide pas :
  il remplace du charabia par des mots inventés.
- **Les petits modèles de vision** (Gemma 4 e2b, GLM-OCR) omettent la moitié
  de la page ou bouclent. Gemma 4 31b, utilisé par le Campus Condorcet,
  reste à mesurer (#44).

### La segmentation pèse

Les HTR lisent ligne par ligne, après une segmentation par kraken. Sur
`01193`, elle coupe les lignes en fragments (56 lignes trouvées pour 11 sur
`p19`), et tous les HTR y dépassent 50 % d'erreur, même sur des pages
qu'Ornith lit à 13-17 %. Une partie de l'écart se gagnera en segmentant
mieux.

## Ce que ça dit pour la suite

Aucun modèle local ne lit aujourd'hui les manuscrits assez bien pour
publier. Deux pistes, à mesurer sur cet étalon :

1. **Affiner Manicule 2026 sur nos écritures.** Les transcriptions de
   Chabin, alignées sur les lignes des scans, donnent des données
   d'entraînement, comme les transcriptions des Archives du Morbihan pour
   1789 (CER de 0,24 à 0,09 après affinage). Les trois cahiers de l'étalon
   sont exclus de l'entraînement.
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
