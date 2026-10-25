# La couche texte du versement : qualité de l'OCR

Les pages dactylographiées sont lues par la couche texte des PDF du
versement (#12). On a beaucoup mesuré la lecture des manuscrits
([`htr.md`](htr.md)), presque pas cet OCR. État au 25 octobre 2026.

## D'où vient la couche texte

Les métadonnées des PDF (300 tirés au hasard) disent toutes la même chose :
OCR par ABBYY FineReader Engine 11, PDF assemblé par iText 5.5.12, une
bibliothèque Java. La lecture n'est donc pas celle des scanners des
départements, mais celle d'un seul moteur, passé ensuite sur tout le
versement. Ses écarts de qualité viennent surtout des documents et de leur
numérisation.

Deux problèmes étaient déjà connus : les pages tournées sont mal lues
(1,7 % des pages dactylographiées, #52), et des pages mixtes sont typées
dactylographiées.

## Taux d'erreur sur l'édition Chabin

`ocr.chabin` compare l'OCR aux transcriptions de Marie-Anne Chabin : 286
contributions imprimées de 76 communes de Charente-Maritime, retrouvées dans
l'OCR par `chabin`, soit un million de caractères. L'OCR est lu de la ligne
où la contribution commence jusqu'au début de la suivante, et sa fin est
celle qui ressemble le plus à la transcription (distance d'édition
semi-globale). Taux pondérés par la longueur, médiane par contribution entre
parenthèses :

| Forme | Contributions | CER brut | CER sans accents | WER normalisé | CER > 5 % | CER > 25 % |
|---|---|---|---|---|---|---|
| dactylographiées | 269 | 8,2 % (3,3 %) | 6,4 % (1,5 %) | 11,6 % (5,6 %) | 39 | 13 |
| courriels imprimés | 17 | 10,4 % (9,5 %) | 8,0 % (7,4 %) | 12,8 % (10,4 %) | 10 | 2 |

- **La contribution typique est bien lue** : 1,5 % d'erreurs par caractère
  sans les accents, six à dix fois mieux que les meilleurs HTR sur les
  manuscrits. Les accents et la casse comptent pour près de deux points.
- **Une queue tire la moyenne** : 28 contributions dépassent 10 %, dans 21
  communes. Pour un tiers d'entre elles, l'OCR a trop peu de texte (3 à
  75 % de la transcription) : une zone non lue, ou une contribution
  suivante mal placée par `chabin`. Pour les autres, le texte est là, mal
  lu ou dans le désordre. Deux seulement commencent sur une page tournée.
- Un nom anonymisé par l'édition reste dans l'OCR et compte comme erreur :
  la mesure est un peu pessimiste. Un seul département, une seule
  numérisation.

## Anomalies sur tout le corpus

`ocr.anomalies` recense, sur les 128 422 pages dactylographiées, des
signaux qui ne demandent pas de référence, par département :

- **Pas de texte mal décodé** : 14 pages avec un « Ã© » ou un « â€ ».
- **L'ordre de lecture est rarement brouillé** : 0,3 % des pages ont plus
  d'une ligne sur dix qui remonte sans changer de colonne, 3 % dans la Marne.
- **La couche texte n'est pas décalée de l'image.** Une première mesure
  trouvait 6 % de pages aux mots posés sur du blanc : sur 150 d'entre elles,
  c'était presque toujours une impression pâle, que le seuil de gris (128)
  ne voyait pas. À un gris plus clair (200), il reste 452 pages (0,35 %),
  dont 106 dans un seul cahier de Seine-Saint-Denis et 29 dans un de
  Gironde ; aucun décalage ni changement d'échelle ne les recale : pages
  très pâles ou à moitié illisibles, à regarder.
- **Environ 3 400 pages (2,7 %) sont presque illisibles** : plus de la
  moitié de leurs mots sont hors du lexique. Hauts-de-Seine et
  Alpes-de-Haute-Provence en tête (11 % de leurs pages). Mauvais scans ou
  pages mixtes typées dactylographiées : à regarder.
- **L'encre non lue n'est pas encore un signal** : un cinquième de l'encre
  d'une page typique n'est sous aucun mot (traits, logos, tampons, bords du
  scan). Il faudrait d'abord les écarter.

Sur les contributions de l'édition Chabin, ces signaux prédisent mal le
taux d'erreur (corrélation de rang de 0,22 au plus, pour les mots hors
lexique et les mots mêlant chiffres et lettres) : ils trouvent des pages
cassées, pas les fautes de lecture courantes.

## Ce qui reste à faire

- Regarder les pages signalées (mots sur du blanc, mots hors lexique) : un
  travail humain, les pages n'étant pas anonymisées.
- Comparer à un OCR moderne à poids ouverts sur un échantillon stratifié
  par département, comme le banc de vision de l'anonymisation : ses
  désaccords avec ABBYY pointeraient les pages à problème ailleurs qu'en
  Charente-Maritime.
- Une petite vérité terrain humaine (mode « transcrire » de l'outil
  d'annotation), sur les départements signalés.
