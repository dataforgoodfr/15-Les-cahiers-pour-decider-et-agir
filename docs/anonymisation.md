# Anonymiser sans tout relire : banc d'essai

Faute de bénévoles, le corpus ne peut pas être relu page par page avant
publication (#128). Ce document réunit les mesures de la chaîne
d'anonymisation automatique sur trois étalons, chacun caviardé par des
humains. État au 19 octobre 2026.

## La chaîne

- **Règles** (`anonymisation.detection`) : courriels, téléphones, noms
  (civilité, prénom de l'INSEE, capitales), adresses, dans la couche texte.
- **Modèle** : GLiNER (`urchade/gliner_multi_pii-v1`), local, sur la couche
  texte.
- **Filtres** (`anonymisation.factices`), cumulés : noms publics (titres,
  commune, maire, présidents, ministres), passages sans majuscule, noms
  répandus dans trois communes ou plus.
- **Encre sans texte** : sur l'image, les traits qu'aucun mot de la couche
  texte ne couvre (écriture à la main, tampons). Variantes : encre pâle,
  encre raturée, et encre sous un mot hors du lexique (une lecture fautive
  de l'OCR) ; « toutes » les réunit.
- **Zones de signature** (`anonymisation.zones`) : les dernières lignes
  courtes et la première ligne courte de chaque contribution, cachées en
  entier. Elles demandent les contributions délimitées.

## Les trois étalons

| Étalon | Ce qui est caché | Pages | Données | Mesure |
|---|---|---:|---:|---|
| Édition Chabin (Charente-Maritime) | crochets de l'éditrice, remplacés par de fausses données | 1 692 contributions | 2 445 | `anonymisation.factices` |
| 100 cahiers délimités à la main | encadrés de la délimitation et de la relecture | 2 413 dactylographiées | 1 935 | `anonymisation.delimites` |
| Aude | rectangles gris des Archives départementales, reportés sur nos pages BnF (`aude.etalon`) | 223 dactylographiées, 408 manuscrites | 88 et 285 | `anonymisation.aude` |

Chacun mesure autre chose :

- **Chabin** mesure le repérage dans un texte propre : ni erreur d'OCR, ni
  écriture à la main, ni image. C'est le plafond de la chaîne.
- **Les 100 cahiers** sont nos vraies pages dactylographiées, avec leur
  OCR, leurs formulaires et l'écriture à la main qui s'y mêle. Le rappel est
  fiable ; la précision n'est qu'un minorant, une page pouvant avoir été
  relue moins finement qu'une autre.
- **L'Aude** donne un second jugement humain, indépendant, et le seul sur
  des manuscrits. Les découpes des Archives (une signature coupée) n'y
  laissent pas de trace : le rappel y est un peu surestimé. Pas de zones de
  signature, faute de contributions délimitées.

## Résultats

Données couvertes, et ce que la chaîne cache en dehors : les mots (ou le
texte, pour Chabin) et, pour l'Aude, l'encre. Filtres jusqu'aux noms
répandus.

| Chaîne | Chabin | 100 cahiers | Aude, dactylographiées | Aude, manuscrites |
|---|---|---|---|---|
| règles + modèle | 97 % (0,7 % du texte) | 38 % (1 %) | 30 % (1 % des mots, 1 % de l'encre) | 4 % (0 %, 0 %) |
| + encre | — | 72 % (6 %) | 67 % (2 %, 5 %) | 55 % (33 %, 36 %) |
| + encre, toutes variantes | — | 94 % (30 %), zones comprises | 91 % (20 %, 25 %) | 91 % (92 %, 66 %) |
| + zones de signature | 99 % (4,8 %) | 74 % (8 %) | — | — |

Le détail par étape de filtrage et par variante est dans le `mesure.md` de
chaque mesure.

## Ce que ça dit

- **Le texte seul ne suffit pas.** La chaîne repère 97 % des données dans
  le texte propre de Chabin, mais 30 à 38 % sur nos pages dactylographiées :
  sur les vraies pages, les données sont surtout écrites à la main (blocs de
  coordonnées d'un formulaire, signatures), là où la couche texte ne lit
  rien ou lit faux. Les deux étalons humains, indépendants, s'accordent.
- **L'encre fait le travail, et coûte.** Cacher l'écriture à la main des
  pages dactylographiées porte la couverture à 67-72 %, pour 2 à 6 % des
  mots ; avec toutes les variantes, à 91-94 %, pour un mot sur cinq à un
  sur trois.
- **Sur un manuscrit, aucune donnée ne se repère : il faut cacher.** Les
  règles et le modèle, sur l'OCR fautif, couvrent 4 % des masques. L'encre
  en couvre 91 % avec toutes les variantes, mais en cachant les deux tiers
  de l'écriture, et laisse un masque visible sur 23 pages sur 201. C'est la
  proposition de #128 (cacher toute l'écriture manuscrite) : sûre, mais le
  manuscrit ne se publie alors qu'en transcription (#6), à anonymiser comme
  un texte.
- **Il reste un audit par échantillon.** Même la chaîne la plus large
  laisse visibles 6 % des données des 100 cahiers (dans 85 contributions
  sur 835) et 9 % des masques de l'Aude. `anonymisation.delimites` en écrit
  la liste, à vérifier dans l'outil d'annotation.

## Les formulaires du corpus

Encadrer deux exemplaires d'un formulaire en fait reporter les zones sur
les autres (`detection.modele_appris`). Encore faut-il savoir quels cahiers
en portent. Sur 174 cahiers jugés à l'œil, sur des planches de vignettes
anonymisées (tirage caviardé, Paris, scans de l'Aude), 74 ont un
formulaire. La règle de `contributions` n'en trouve que 46 (62 %) : elle
ne lit que les pages dactylographiées et veut une ligne sur un tiers des
pages. `anonymisation.formulaires` lit toutes les pages écrites, avec un
seuil absolu (quatre pages portant chacune trois lignes imprimées qui
reviennent sur quatre pages), et en trouve 62 (84 %). Ses 8 fausses alertes
sont surtout des copies de lettres types signées, utiles elles aussi ; les
formulaires manqués ont des pages que l'OCR ne lit pas.

Sur le corpus, 1 333 cahiers sur 19 847 ont un formulaire (33 752 pages de
formulaire, 12 % des pages écrites) : à deux pages encadrées par
formulaire, environ 2 700 pages à annoter. La part varie beaucoup : 77 %
des cahiers de Paris (le formulaire de la Ville), 22 % du tirage, 10 % de
l'Aude, au moins 2 % de l'édition Chabin.
