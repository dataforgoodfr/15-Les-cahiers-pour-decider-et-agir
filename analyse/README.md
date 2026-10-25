# Analyse du corpus

Mesures sur le versement BnF des cahiers citoyens : des comptes, jamais de
texte. Les commandes se lancent depuis ce dossier ; les sources et les sorties
vont dans `data/` (hors git).

```bash
cd analyse
uv sync
uv run pytest
```

Les modules suivent la chaîne décrite dans [`docs/chaine.md`](../docs/chaine.md) :
les uns constituent la couche « or » (contributions délimitées, lues,
anonymisées), les autres l'exploitent pour l'association.

Un dossier par étape, un sous-dossier par module : `corpus/typage` se lance
par `uv run python -m corpus.typage`.

## Constituer la couche « or »

### Mesurer le corpus : `corpus/`

| Module | Issue | Ce qu'il fait |
|---|---|---|
| `corpus.typage` | #17 | Type chaque page : vierge, dactylographiée, mixte ou manuscrite |
| `corpus.cascade` | #41 | Du versement aux pages écrites, niveau par niveau |
| `corpus.communes` | #19 | Variables INSEE de 2019 des communes du corpus |
| `corpus.communes.representativite` | #20 | Écart du corpus (ou d'un panel) à la France |
| `corpus.concatenes` | #42 | Fichiers qui contiennent le cahier d'une autre commune |
| `corpus.orientation` | #43 | Pages tournées d'un quart de tour |
| `corpus.inventaires` | #43 | Documents inventoriés sans fichier, fichiers sans inventaire |
| `corpus.manquantes` | #43 | Pages manquantes des courriers et formulaires types |
| `corpus.ouvertures` | #5 | Pages d'ouverture imprimées (couverture de l'association des maires…), qui ne sont pas des contributions |

### Lire le texte imprimé : `ocr/`

| Module | Issue | Ce qu'il fait |
|---|---|---|
| `ocr.chabin` | #12 | Qualité de l'OCR du versement (ABBYY FineReader Engine 11) : taux d'erreur par caractère et par mot sur les contributions imprimées de l'édition Chabin |
| `ocr.anomalies` | #12 | Anomalies de l'OCR page par page sur tout le corpus (encre non lue, mots sur du blanc, ordre de lecture, mots hors lexique, texte mal décodé), par département ; synthèse dans `docs/ocr.md` |
| `ocr.modernes` | #12 | OCR récents à poids ouverts (OvisOCR3, LightOnOCR-2, Chandra 2, servis par vLLM hors de la machine) et Tesseract contre ABBYY, sur les contributions de l'édition Chabin : CER, mots mal lus, inventés, omis |

### Découper les cahiers en contributions : `decoupage/`

| Module | Issue | Ce qu'il fait |
|---|---|---|
| `decoupage.contributions` | #5 | Débuts des contributions (courriels, formulaires, lettres), et pages qui en ouvrent une selon un petit modèle (`decoupage.contributions.pages`), mesurés sur les notes de l'outil d'annotation |
| `decoupage.delimitation` | #95 | Toutes les contributions délimitées à la main dans les cahiers tirés, en positions sur les pages ; la plateforme les charge |
| `decoupage.troncons` | #5 | Référence de test du découpage : un tronçon de 10 pages dans chaque département que les cahiers délimités ne couvrent pas, à délimiter dans l'outil d'annotation |
| `decoupage.chabin` | #5 | Référence de découpage : les cahiers de l'édition Chabin, délimités à la main et comparés à ses comptes ; ses contributions imprimées retrouvées dans l'OCR, pour mesurer les règles, et ses manuscrits dans la lecture HTR (`htr/`) |

### Anonymiser : `anonymisation/`

| Module | Issue | Ce qu'il fait |
|---|---|---|
| `anonymisation` | #7 | Données personnelles (règles, zones de formulaire, modèles locaux), à vérifier dans l'outil d'annotation |
| `anonymisation.publics` | #128 | Noms publics à ne pas cacher : titres, commune, maire (mandat 2014-2020), présidents de la Ve République, gouvernement de l'hiver 2018-2019 |
| `anonymisation.factices` | #128 | Repérage mesuré sur l'édition Chabin, avec de fausses coordonnées à la place des crochets : rappel et précision du modèle, des règles et des deux, par étape de filtrage |
| `anonymisation.zones` | #128 | Zones de signature d'une contribution (dernières lignes courtes, première ligne courte), à cacher en entier |
| `anonymisation.delimites` | #128 | La même chaîne (règles, modèle, encre, filtres, zones) mesurée sur les pages dactylographiées et mixtes des cahiers délimités à la main ; place des données qui restent visibles, à vérifier |
| `anonymisation.aude.mesure` | #128 | La même chaîne mesurée sur l'étalon de l'Aude, pages dactylographiées et manuscrites : masques des Archives couverts, et part des mots et de l'encre cachés hors masques ; synthèse des trois étalons dans `docs/anonymisation.md` |
| `anonymisation.vision` | #128 | Données personnelles encadrées sur l'image par un modèle de vision servi hors de la machine (vLLM, carte louée en Europe) : calibrage sur une page factice, boîtes sur l'étalon de l'Aude, masques couverts et encre cachée |
| `anonymisation.aude` | #128 | Pages des cahiers de l'Aude publiés anonymisés par le CESE (`../aude/`) rapprochées de leurs pages BnF par l'image (points SIFT) : commune de chaque page, doublons du versement, cahiers absents du versement |
| `anonymisation.aude.etalon` | #128 | Étalon d'anonymisation : les rectangles gris des Archives de l'Aude, repérés sur les pages publiées et reportés en points sur les pages BnF rapprochées (recalés localement, avec leur accord), manuscrits compris ; les découpes n'y figurent pas |

### Annoter : `annotation/`

| Module | Issue | Ce qu'il fait |
|---|---|---|
| `annotation` | #5, #7 | Outil local d'annotation : vérités terrain sur les pages, listes à revoir |

## Exploiter

### Tirer un panel : `panels/`

| Module | Issue | Ce qu'il fait |
|---|---|---|
| `panels.panel` | #22 | Panel aligné sur l'échantillon du Campus Condorcet |
| `panels.tirage` | #21 | Une centaine de contributions représentatives des habitants, pour l'association |
| `panels.selection` | #21 | Export caviardé des contributions tirées ; ordonne les cahiers à délimiter pour garder l'échantillon représentatif |
| `panels.recueil` | #21 | Recueil PDF des contributions exportées par `panels.selection`, avec leur représentativité, pour l'association |

### Classer : `classement/`

| Module | Issue | Ce qu'il fait |
|---|---|---|
| `classement.themes` | #24 | Place de chaque sous-thème de la grille de l'association dans les contributions délimitées, le corpus et le Vrai débat ; repérage par mots-clés |
| `classement.propositions` | #94 | Contributions de l'édition Chabin (déjà anonymisées) découpées en propositions, l'unité de l'étalon de regroupement ; un échantillon à vérifier par des volontaires |
| `classement.paires` | #94 | Paires de propositions à annoter (même proposition ou non), tirées par tranches de ressemblance de plongements locaux, plus une part au hasard ; lots de réglage et de test |
| `classement.paires.accord` | #94 | Accord des annotateurs sur les paires jugées dans l'outil d'annotation (kappa de Cohen), litiges et adjudications |

Les modèles locaux de l'anonymisation (GLiNER) sont dans un groupe à part :
`uv sync --group modeles` ; OpenCV, pour `anonymisation.aude`, aussi : `uv sync --group
images`. Les LLM passent par [Ollama](https://ollama.com/), sur cette machine ;
les modèles trop gros pour elle (vision, OCR récents), par vLLM sur une carte
louée en Europe.

Chaque module décrit sa commande dans sa docstring ou son README.
