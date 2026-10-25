# Anonymiser sans tout relire : banc d'essai

Faute de bénévoles, le corpus ne peut pas être relu page par page avant
publication (#128). Ce document réunit les mesures de la chaîne
d'anonymisation automatique sur trois étalons, chacun caviardé par des
humains. État au 25 octobre 2026.

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
- **Vision** (`anonymisation.vision`) : un modèle de vision à poids ouverts,
  servi sur une carte louée en Europe (Verda), encadre chaque donnée
  personnelle sur l'image de la page, sans la recopier. On n'en garde que
  les boîtes.
- **Liste blanche** (`anonymisation.blanche`) : à l'inverse, on ne garde que
  les mots sûrs (Lexique 3.83, France, Europe, régions, départements, noms
  publics du cahier) et l'on cache tout le reste de la couche texte, si bien
  qu'une lecture fautive est cachée au lieu de fuir. Un prénom de l'INSEE à
  majuscule est caché, même s'il est dans le lexique.

## Les trois étalons

| Étalon | Ce qui est caché | Pages | Données | Mesure |
|---|---|---:|---:|---|
| Édition Chabin (Charente-Maritime) | crochets de l'éditrice, remplacés par de fausses données | 1 692 contributions | 2 445 | `anonymisation.factices` |
| 100 cahiers délimités à la main | encadrés de la délimitation et de la relecture | 2 482 dactylographiées et mixtes | 1 938 | `anonymisation.delimites` |
| Aude | rectangles gris des Archives départementales, reportés sur nos pages BnF (`anonymisation.aude.etalon`) | 223 dactylographiées, 408 manuscrites | 88 et 285 | `anonymisation.aude.mesure` |

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

## Les modèles de vision

L'encre cache l'écriture à la main sans savoir ce qu'elle dit. Un modèle
de vision regarde la page et n'encadre que les données personnelles :
noms, signatures, adresses, téléphones, courriels. Deux modèles à poids
ouverts (Apache 2.0) qui tiennent sur une A100 80 Go, servis par vLLM :
Qwen3.8-27B (août 2026) et Gemma 4 31B (mars 2026). Une page factice, aux
fausses coordonnées placées à des endroits connus, vérifie d'abord la forme
de leurs boîtes : les deux recouvrent chaque fausse donnée à 0,6-0,75
(intersection sur union).

Sur l'étalon de l'Aude (`anonymisation.aude --vision`, même critère que
plus haut, filtres jusqu'aux noms répandus), le 25 octobre 2026, Qwen et
Gemma réunis :

| Chaîne | Dactylographiées : masques couverts | mots, encre cachés | Manuscrites : masques couverts | mots, encre cachés | Pages manuscrites où un masque reste visible |
|---|---|---|---|---|---|
| règles + modèle | 30 % | 1 %, 1 % | 4 % | 0 %, 0 % | 191 sur 201 |
| règles + modèle + encre, toutes variantes | 91 % | 20 %, 25 % | 91 % | 92 %, 66 % | 23 sur 201 |
| vision seule | 88 % | 1 %, 1 % | 89 % | 2 %, 1 % | 28 sur 201 |
| règles + modèle + vision | 88 % | 2 %, 2 % | 89 % | 2 %, 1 % | 28 sur 201 |
| règles + modèle + encre + vision | 91 % | 3 %, 6 % | 95 % | 35 %, 36 % | 13 sur 201 |
| règles + modèle + encre, toutes variantes, + vision | 95 % | 21 %, 25 % | 98 % | 92 %, 66 % | 6 sur 201 |

Les deux modèles ne se valent pas. Avec un critère sur l'encre seule (80 %
de l'encre du masque sous une boîte, `anonymisation.vision mesurer`), Qwen
couvre 81 % des masques des pages dactylographiées et 85 % des manuscrites ;
Gemma, 61 % et 53 %, mais trois fois plus vite (10 s par requête contre 26,
huit en parallèle). Réunis, ils couvrent 82 % et 91 % : Gemma rattrape une
partie de ce que Qwen manque. Chacun cache environ 1 % de l'encre hors
masques. Une seule réponse illisible sur 1 262 requêtes.

Une passe des deux modèles sur l'étalon (631 pages) a pris environ une
heure d'A100 louée. Le corpus (276 000 pages écrites) en demanderait de
l'ordre de 440 heures à ce rythme, pour les deux modèles.

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
- **Sur un manuscrit, la couche texte ne repère rien : il faut cacher, ou
  regarder l'image.** Les
  règles et le modèle, sur l'OCR fautif, couvrent 4 % des masques. L'encre
  en couvre 91 % avec toutes les variantes, mais en cachant les deux tiers
  de l'écriture, et laisse un masque visible sur 23 pages sur 201. C'est la
  proposition de #128 (cacher toute l'écriture manuscrite) : sûre, mais le
  manuscrit ne se publie alors qu'en transcription (#6), à anonymiser comme
  un texte.
- **Un modèle de vision cache presque autant, pour vingt à cinquante fois
  moins.**
  Sur l'Aude, Qwen et Gemma réunis couvrent 88 à 89 % des masques en ne
  cachant que 1 à 2 % du reste, contre 91 % pour 25 à 66 % avec toute
  l'encre. Les pages manuscrites redeviennent publiables en image, mais un
  masque reste visible sur une page à masques sur sept (28 sur 201). Jointe à l'encre, la vision couvre
  95 à 98 % des masques, mais retrouve le coût de l'encre. Cela suppose
  d'envoyer les pages à un modèle hors de nos machines, sur une carte louée
  en Europe.
- **Publié en texte, le corpus se passe presque de repérage.** La liste
  blanche, avec les règles, le modèle et les zones, couvre 92 % des données
  en ne cachant que 3 % des mots du lexique, et vaudra pour les manuscrits
  transcrits (#6), dont les mots inventés tombent hors du lexique.
- **Il reste un audit par échantillon.** Même la chaîne la plus large
  laisse visibles 6 % des données des 100 cahiers (dans 85 contributions
  sur 835) et 9 % des masques de l'Aude. `anonymisation.delimites` en écrit
  la liste, à vérifier dans l'outil d'annotation.

## Les formulaires du corpus

Encadrer deux exemplaires d'un formulaire en fait reporter les zones sur
les autres (`detection.modele_appris`). Encore faut-il savoir quels cahiers
en portent. Sur 174 cahiers jugés à l'œil, sur des planches de vignettes
anonymisées (tirage caviardé, Paris, scans de l'Aude), 74 ont un
formulaire. La règle de `decoupage.contributions` n'en trouve que 46 (62 %) : elle
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
