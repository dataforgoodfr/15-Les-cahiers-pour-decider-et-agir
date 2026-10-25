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

## OCR modernes contre ABBYY

`ocr.modernes` relit les mêmes pages (725 pages dactylographiées des 286
contributions) avec des OCR récents à poids ouverts, servis par vLLM sur
une A100 louée en Europe (Verda), et avec Tesseract sur CPU. Chaque source
est alignée sur la transcription Chabin (début et fin libres) ; les écarts
mot à mot sont classés comme au banc HTR, pour 100 mots de la référence.

| Source | Taille, licence | CER sans accents | Mal lus | Inventés | Charabia | Omis |
|---|---|---|---|---|---|---|
| ABBYY FineReader 11 | — | 6,5 % (1,5 %) | 2,5 | 3,0 | 0,6 | 5,1 |
| Tesseract (CPU) | Apache 2.0 | 6,7 % (1,7 %) | 1,7 | 2,6 | 0,7 | 5,6 |
| OvisOCR3 | 0,8 Md, Apache 2.0 | 4,7 % (0,6 %) | 1,4 | 1,2 | 0,2 | 4,1 |
| OvisOCR3, mots et cadres | id. | 5,0 % (0,8 %) | 1,5 | 1,4 | 0,3 | 4,5 |
| LightOnOCR-2 | 1 Md, Apache 2.0 | 5,7 % (0,7 %) | 1,3 | 1,8 | 0,3 | 4,6 |
| Chandra OCR 2 | 5 Md, OpenRAIL-M modifiée | 4,8 % (0,6 %) | 1,2 | 1,3 | 0,2 | 4,2 |

- **Les OCR modernes divisent par deux ou plus l'erreur de la contribution
  typique** (médiane 1,5 % → 0,6 %), et **inventent deux fois moins** de
  mots qu'ABBYY. Sur l'imprimé, ils ne complètent pas le texte comme les
  modèles le font sur les manuscrits. Une part de l'écart peut venir de la
  forme (lignes rejointes, coupures de mots), plus proche d'une
  transcription humaine : la mesure sans ponctuation l'atténue.
- **OvisOCR3, le plus petit (0,8 Md), fait jeu égal avec Chandra (5 Md).**
  Tesseract ne fait pas mieux qu'ABBYY.
- **La queue est surtout du texte absent des pages lues.** Sur les 27
  contributions où ABBYY dépasse 10 %, les modèles modernes omettent encore
  32 à 35 mots sur 100 (ABBYY 40) : ce texte n'est pas sur les pages
  dactylographiées lues (pages typées manuscrites ou vierges, ou absentes du
  scan). Ils n'y gagnent que sur les fautes de lecture.
- **Le mode « mots » d'OvisOCR3 ne rend pas toujours des mots** : sur une
  page factice, il donne un cadre par ligne ou par paragraphe. Ses cadres
  ne sont pas encore mesurés sur les vraies pages ; 13 réponses sur 725
  n'étaient pas du JSON valide.
- **Coût** : avec 32 requêtes en parallèle et des images en JPEG (sept fois
  moins lourdes à envoyer que le PNG), OvisOCR3 lit environ 100 pages par
  minute sur une A100 : le corpus dactylographié (128 000 pages) en
  demanderait une vingtaine d'heures.

### Sur les pages presque illisibles

`ocr.modernes illisibles` tire 100 pages où ABBYY laisse plus de la moitié
des mots hors du lexique (au moins 20 mots), parmi 3 060 ; `ocr.modernes
lexique` compare, faute de référence, la part de mots hors lexique.

| Source | Mots hors lexique (médiane) | Pages au-delà de 50 % | Mots lus (médiane) |
|---|---|---|---|
| ABBYY | 78 % | 98 | 260 |
| OvisOCR3 | 15 % | 17 | 186 |

**Cet indice est trompeur.** Les trois pages de Paris de l'échantillon,
regardées à l'œil, sont des formulaires imprimés remplis à la main, dont
une tournée : les deux problèmes déjà connus. OvisOCR3 lit l'imprimé sans
faute, même sur la page tournée ; mais à la place de l'écriture à la main,
il écrit souvent du français plausible sans rapport avec la page, et perd
l'état des cases cochées. Un mot inventé est dans le lexique : l'indice
le compte comme une réussite. Ces pages relèvent de la lecture des
manuscrits (`htr.md`), avec son risque d'invention, et de leur typage
(mixtes, non dactylographiées). Le typage les avait classées
dactylographiées parce que son score de qualité (wordfreq, 0,57 en médiane
sur l'échantillon) prend ce bruit pour du texte.

## Ce qui reste à faire

- Regarder les pages signalées (mots sur du blanc, mots hors lexique) : un
  travail humain, les pages n'étant pas anonymisées.
- Passer un OCR moderne sur un échantillon stratifié par département, et
  sur les pages signalées : ses désaccords avec ABBYY pointeraient les pages
  à problème ailleurs qu'en Charente-Maritime.
- Mesurer les cadres de mots d'OvisOCR3 contre ceux d'ABBYY, avant de
  penser à remplacer la couche texte.
- Une petite vérité terrain humaine (mode « transcrire » de l'outil
  d'annotation), sur les départements signalés.
