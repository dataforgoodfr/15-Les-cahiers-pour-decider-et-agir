# Anonymiser sans tout relire : banc d'essai

Faute de bénévoles, le corpus ne peut pas être relu page par page avant
publication (#128). Ce document réunit les mesures de la chaîne
d'anonymisation automatique sur trois étalons, chacun caviardé par des
humains. État au 20 octobre 2026.

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
- **Liste blanche** (`anonymisation.blanche`) : à l'inverse, on ne garde que
  les mots sûrs (Lexique 3.83, France, Europe, régions, départements, noms
  publics du cahier) et l'on cache tout le reste de la couche texte, si bien
  qu'une lecture fautive est cachée au lieu de fuir. Un prénom de l'INSEE à
  majuscule est caché, même s'il est dans le lexique.

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

## Publier le texte seul

Publier le texte des pages, sans leurs images, change la donne : l'écriture
à la main n'y paraît que si l'OCR l'a lue, en mots presque toujours hors du
lexique, que la liste blanche cache. Sur les 100 cahiers
(`anonymisation.blanche`), une donnée n'y fuit que par ses mots de la couche
texte ; 686 des 1 935 n'en ont aucun et sont couvertes d'office.

| Chaîne, texte seul | Données couvertes | Contributions où une donnée reste visible | Mots hors données cachés (du lexique) |
|---|---|---|---|
| règles + modèle | 70 % | 404 sur 835 | 1 % (1 %) |
| liste blanche | 82 % | 253 | 10 % (1 %) |
| règles + modèle + liste blanche + zones | 92 % | 111 | 12 % (3 %) |

Sur les seules données qui ont des mots dans la couche texte, la chaîne
complète en couvre 88 %. Ce qui fuit encore est surtout dans les blocs de
coordonnées des formulaires (129 données sur 153), et ce sont des mots du
lexique : 63 % en minuscules, 35 % à majuscule (un nom de famille comme
« Petit », ou « Rue »). Une donnée compte comme visible dès qu'un seul de
ses mots l'est : la mesure est pessimiste.

Contre les blocs de coordonnées, un relecteur peut encadrer deux pages
d'un formulaire : leurs zones se reportent sur les autres exemplaires
(`detection.modele_appris`). Simulé en apprenant, pour chaque page, sur les
deux pages à données les plus proches du même cahier, la chaîne passe à
94 % (90 contributions où une donnée reste visible) pour un point de texte
de plus, sans mot du lexique en plus. Apprendre sur toutes les autres pages
ne gagne qu'un point (95 %, 69 contributions) et cache 20 % du texte, dont
11 % du lexique. Il reste 104 blocs de coordonnées qui fuient, hors des
formulaires répétés (lettres, pages libres).

Sur les images, la liste blanche n'apporte presque rien : jointe à la
chaîne la plus large, elle porte la couverture de 94 à 96 % (54
contributions où une donnée reste visible), pour 32 % des mots cachés.

Deux variantes, mesurées puis retirées du code : cacher les majuscules hors début de phrase (un
point de couverture pour cinq points de lexique perdus), et garder les
nombres sûrs (années, nombres suivis d'une unité), qui ne rend que 15 % des
nombres cachés et laisse fuir des années dans les blocs de coordonnées.

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
- **Publié en texte, le corpus se passe presque de repérage.** La liste
  blanche, avec les règles, le modèle et les zones, couvre 92 % des données
  en ne cachant que 3 % des mots du lexique, et vaudra pour les manuscrits
  transcrits (#6), dont les mots inventés tombent hors du lexique.
- **Il reste un audit par échantillon.** Même la chaîne la plus large
  laisse visibles 6 % des données des 100 cahiers (dans 85 contributions
  sur 835) et 9 % des masques de l'Aude. `anonymisation.delimites` en écrit
  la liste, à vérifier dans l'outil d'annotation.
