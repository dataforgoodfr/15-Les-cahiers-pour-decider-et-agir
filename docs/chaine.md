# La chaîne de traitement

Le travail se partage en deux parties, qui avancent chacune de leur côté :

- **Constituer la base des contributions** : des PDF du versement BnF,
  tirer des contributions délimitées, lues, anonymisées et modérées, prêtes
  à être indexées. Cette partie **ajoute** des données à la base.
- **Exploiter la base**, pour l'association : thèmes, propositions
  qui se ressemblent, fréquence des sujets, panels, votes des citoyens sur
  la plateforme. Cette partie **lit** la base.

Entre les deux, la base des contributions, celle de la plateforme ([`plateforme/`](../plateforme/),
application `cahiers`) sert de contrat. Une étape de la première partie peut
s'améliorer sans rien changer à la seconde, du moment qu'elle remplit les
mêmes tables. Une exploitation peut se construire sur les contributions déjà
chargées, sans attendre que tout le corpus le soit.

```mermaid
flowchart LR
    subgraph C[Constituer]
        V[Versement BnF<br>PDF + couche texte] --> M[Mesurer<br>type, orientation]
        M --> L[Lire<br>OCR, HTR]
        L --> D[Découper<br>en contributions]
        D --> A[Anonymiser]
        D --> Mo[Modérer]
    end
    A --> O[(Base des<br>contributions)]
    Mo --> O
    subgraph E[Exploiter]
        T[Thèmes, fréquence<br>des sujets]
        P[Propositions<br>regroupées]
        S[Panels, tirages]
        Vo[Votes, lecture<br>publique]
    end
    O --> T
    O --> P
    O --> S
    O --> Vo
```

Les modules sont dans [`analyse/`](../analyse/), sauf mention contraire ;
chacun lit et écrit dans `analyse/data/`, hors git. Une commande par module :
`uv run python -m <module>`, décrite dans sa docstring ou son README.

## La base des contributions

Ce que la base garde de chaque cahier (`plateforme/cahiers/models.py`) :

- le **document** du versement, sa commune (au 1er janvier 2019) et ses
  **pages** : type, rotation, pages de service et d'ouverture. C'est la
  provenance, jamais réécrite ;
- les **transcriptions** des pages, rattachées au run qui les a produites
  (la table existe, aucune commande ne la remplit encore) ;
- les **contributions** : début et fin sur les pages, texte anonymisé,
  extrait caviardé (le seul fichier que le public voit), et `publiable`, faux
  pour ce qui est à écarter.

Une contribution appartient à un **run** : un découpage fait à la main, par
l'édition Chabin, ou par un modèle. Plusieurs runs coexistent ; un seul est
actif. Remplacer un découpage revient donc à charger un nouveau run, pas à
réécrire l'ancien.

## Constituer

| Étape | Modules | Mesure | Où en lire plus |
|---|---|---|---|
| **Mesurer le corpus** : type de chaque page (vierge, dactylographiée, mixte, manuscrite), pages tournées, fichiers concaténés ou incomplets, pages d'ouverture imprimées | `corpus.typage`, `corpus.cascade`, `corpus.orientation`, `corpus.concatenes`, `corpus.inventaires`, `corpus.manquantes`, `corpus.ouvertures`, `corpus.communes` | 276 000 pages écrites : 38 % dactylographiées, 11 % mixtes, 51 % manuscrites | [`docs/corpus.md`](corpus.md), #17, #41, #43 |
| **Lire le texte imprimé** (OCR) | couche texte du versement ; `ocr.chabin`, `ocr.anomalies`, `ocr.modernes`, `ocr.tirage` | 1,5 % d'erreurs par caractère (médiane) ; 0,6 % avec un OCR récent ; ailleurs qu'en Charente-Maritime, 2 % des mots diffèrent d'une relecture par Claude Haiku | [`docs/ocr.md`](ocr.md), #12 |
| **Lire les manuscrits** (HTR) | [`htr/`](../htr/) | Aucun modèle local n'est encore assez fidèle pour publier | [`docs/htr.md`](htr.md), #6 |
| **Découper** les cahiers en contributions | `decoupage.contributions` (règles et modèle), `decoupage.corpus` (les mêmes, sur tout le corpus), `decoupage.vision` (modèle de vision) ; références : `decoupage.delimitation`, `decoupage.chabin`, `decoupage.troncons` | Règles et modèle, pages dactylographiées et mixtes : 75 % des débuts trouvés sont justes, 81 % des débuts sont trouvés. Qwen servi en Europe, toutes pages : 81 % et 84 % | [`analyse/decoupage/contributions/`](../analyse/decoupage/contributions/), #5, #64 |
| **Anonymiser** | `anonymisation` et ses sous-modules ; étalon `anonymisation.aude` | Texte seul : 92 à 94 % des données cachées ; image et modèle de vision : 88 à 89 % | [`docs/anonymisation.md`](anonymisation.md), #7, #128 |
| **Modérer** : écarter les contenus haineux ou illicites | Aucun : à la main, dans l'outil d'annotation (« à écarter ») | Pas d'étalon ; un modèle de vision peut préparer une relecture, pas trancher | #166 |
| **Charger** dans la base | `manage.py charger_corpus`, `charger_contributions`, `charger_extraits`, `charger_chabin`, `charger_decoupage` ([`plateforme/`](../plateforme/)) | — | [`plateforme/README.md`](../plateforme/README.md), #34 |

La lecture des manuscrits est un sous-projet à part, [`htr/`](../htr/),
pour une raison technique : kraken demande Python 3.12 et numpy 1, quand
`analyse/` est en Python 3.14 et numpy 2. Les modules `ocr` restent dans
`analyse/` : ils mesurent la couche texte du versement et interrogent des
modèles servis ailleurs, sans dépendance lourde.

Aujourd'hui, la base sert les contributions délimitées à la main (les
cahiers des 100 contributions tirées). Celles de l'édition Chabin et du
découpage automatique de tout le corpus (`decoupage.corpus`, pages imprimées
seules, arrêtées avant les pages manuscrites) y sont chargées sous des runs
jamais activés, pour comparer. L'anonymisation automatique est mesurée, mais
ses sorties ne sont pas encore chargées.

L'outil d'annotation (`annotation`) sert à toute la constitution : c'est là
qu'on note, à la main, les vérités terrain contre lesquelles tout est mesuré
(types de page, débuts de contributions, données personnelles, pages à
écarter).

## Exploiter

| Usage | Modules | État | Où en lire plus |
|---|---|---|---|
| **Thèmes** : rattacher chaque contribution aux thèmes de l'association, compter la place de chaque sujet | `classement.themes` | Grille V2 (8 thèmes, 42 sous-thèmes), repérage par mots-clés | #24 |
| **Types de discours** : témoignage, constat, revendication, proposition… | — | Typologie proposée | #25 |
| **Propositions regroupées** : retrouver la même idée d'un cahier à l'autre | `classement.propositions`, `classement.paires`, `classement.paires.accord` | Étalon de paires en cours d'annotation | #4, #94 |
| **Panels et tirages** : des contributions représentatives des habitants | `panels.tirage`, `panels.panel`, `corpus.communes.representativite` ; `panels.selection` et `panels.recueil` pour les exporter | 100 contributions tirées, exportées et réunies en recueil | [`docs/selection.md`](selection.md), #21, #22 |
| **Plateforme publique** : lire, voter, s'informer | [`plateforme/`](../plateforme/) | Page d'accueil qui tire une contribution au sort ; votes à venir | #29, #30, #38 |

Les modules d'exploitation lisent encore les sorties d'`analyse/` (par
exemple `classement.themes` lit `data/delimitation/`) plutôt que la base. À mesure que
la base s'étoffe, ils devraient la lire directement.

## Les références

Chaque mesure se fait contre un travail humain :

- **Les cahiers délimités** : les cahiers des 100 contributions tirées,
  délimités en entier dans l'outil d'annotation (`decoupage.delimitation`). Référence
  du découpage et de l'anonymisation des pages imprimées. Le tirage les a
  choisis : c'est le seul endroit où l'exploitation a nourri la constitution.
- **Les tronçons** (`decoupage.troncons`) : dix pages dans chacun des départements que
  les cahiers délimités ne couvrent pas. Jeu de test du découpage, à ne pas
  regarder pour régler les règles.
- **L'édition Chabin** : les cahiers de Charente-Maritime transcrits et
  anonymisés par Marie-Anne Chabin ([`extraction/`](../extraction/)).
  Référence du découpage, de l'OCR, de la HTR et de l'anonymisation.
- **L'Aude** : les cahiers caviardés par les Archives départementales
  (`anonymisation.aude`, `anonymisation.aude.etalon`). Seul étalon d'anonymisation avec des manuscrits.
- **Dole** : une transcription XML-TEI de manuscrits, étalon de la HTR.

## Lexique

- **Versement** : les PDF des cahiers déposés à la BnF, un dossier par
  département (`BnF_GDN_XX_PDF`).
- **Base des contributions** : la base de la plateforme, où la constitution
  écrit les contributions délimitées, anonymisées et modérées, et où
  l'exploitation les lit. Elle garde aussi ce qui ne sera pas publié
  (contributions à écarter, pages non anonymisées pour les administrateurs).
- **Cahier** : un fichier du versement ; une **contribution** : le texte d'un
  auteur (ou d'un groupe) dans un cahier ; une **proposition** : une idée
  dans une contribution.
- **Run** : une production de la chaîne (un découpage, une transcription),
  datée, avec son auteur ou son modèle et ses paramètres.
- **Découpage** : trouver où commence chaque contribution d'un cahier
  (`decoupage.contributions`). À ne pas confondre avec le découpage d'une contribution
  en propositions (`classement.propositions`).
- **Délimiter** : faire le découpage à la main, dans l'outil d'annotation.
- **Page mixte** : une page imprimée remplie à la main (un formulaire, le plus
  souvent). Sa couche texte lit l'imprimé, pas l'écriture.
- **Chabin** : trois modules portent ce nom. `extraction/chabin` télécharge
  et extrait l'édition ; `analyse/decoupage/chabin` en fait une référence de
  découpage ; `ocr.chabin` y mesure l'OCR.
- **Tirage** et **sélection** : le tirage choisit les 100 contributions
  (`panels.tirage`) ; la sélection les exporte, caviardées, une fois leur cahier
  délimité (`panels.selection`).
