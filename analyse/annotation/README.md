# Annotation des cahiers

Outil d'annotation pour la chaîne de traitement du texte : on y pose, sur
les pages, les vérités terrain qui mesurent et corrigent les analyses
(débuts de contributions, données personnelles), et on y revoit les listes
qu'elles produisent. Ce n'est pas l'outil de consultation des cahiers du
backend (`backend/gradio_app`).

```bash
uv run python -m annotation
```

Ouvre http://127.0.0.1:8765 dans le navigateur. Le serveur n'écoute que sur
la machine : les pages, les notes et les listes ne la quittent pas.

## Ce qu'on peut faire

- **Feuilleter un cahier** : chercher par nom de fichier ou code INSEE, page
  par page, zoom, vignettes de toutes les pages avec leur type (D
  dactylographiée, M manuscrite, MD mixte, V vierge ; les pages de service
  sont pâlies).
- **Noter sur la page**, sans formulaire : un clic pose un début de
  contribution, un double clic une fin, un glisser caviarde la zone (note de
  l'étiquette de donnée personnelle choisie, bloc de coordonnées sinon).
  La note s'enregistre aussitôt et reste choisie : Suppr l'annule. Un clic
  sur une note l'ouvre pour changer son étiquette ou son texte. Chaque note a
  une étiquette et un texte libre ; la position est gardée en points PDF. Étiquettes de structure (début et fin de
  contribution, date, signature) et de données personnelles (nom, prénom,
  adresse, courriel, téléphone, autre donnée identifiante, bloc de
  coordonnées), à encadrer d'un
  rectangle : ce sera la référence de l'anonymisation (#7). Ne pas recopier
  la donnée dans le texte de la note. Une note ouverte se déplace en la glissant, et
  se redimensionne par les poignées de ses coins.
- **Passer d'une page à l'autre à la molette** : arrivée en bas de la page,
  la molette continue sur la suivante (en haut, sur la précédente).
- **Pivoter l'affichage** d'un quart de tour (`t`), page par page, pour lire
  une page numérisée de travers. Les notes restent justes : elles sont
  gardées dans le repère du PDF.
- **Voir les métadonnées de la page**, à droite : son typage (type, encre,
  qualité, mots, page de service) et ce que les analyses y ont détecté
  (`orientation`, `manquantes`, `concatenes`, inventaire), lus dans `data/`.
- **Qualifier la page** : ses problèmes (tournée, ordre des pages, page
  manquante, illisible, coupée, doublon) arrivent cochés d'avance quand une
  analyse les a détectés, avec la mention « détecté » ; décocher un faux
  positif est gardé. Le type arrive rempli par le typage : le corriger au
  besoin ; une page marquée vue sans correction confirme son typage. Une page
  à problème porte ⚠ dans les vignettes, un type corrigé ✓.
- **Écrire des remarques libres** sur la page ou sur le cahier.
- **Afficher la couche texte** (« Texte OCR ») : les cadres des lignes
  reconnues par l'OCR du versement ; survoler une ligne montre son texte.
- **Marquer une page** vue ou à revoir. Une page vue est une page dont toutes
  les notes de la tâche ont été posées : c'est elle qui compte dans les
  mesures. Le statut vaut pour la tâche de la liste ouverte (« contributions »,
  « anonymisation » ou « masquage ») : une page relue pour les données personnelles reste
  à relire pour les débuts de contribution. Hors liste, il vaut pour toutes.
- **Revoir une liste** : les modules d'analyse écrivent des listes de pages,
  avec leurs repérages en pointillés orange. On les parcourt une à une ; `a`
  accepte les repérages de la page comme notes.
- **Relire à l'envers une liste à masquer** (données personnelles) : chaque
  repérage arrive caché sous un voile sombre, car dans le doute on cache. Un
  clic sur une fausse alerte la rétablit (cadre vert « rétabli »), un second
  clic la recache ; `m` montre ou cache les repérages pour lire dessous. Les
  données oubliées s'encadrent d'un glisser : le rectangle devient tout de
  suite une note de l'étiquette courante, sans formulaire. Les touches 1 à 7
  y choisissent la donnée personnelle (1 nom… 6 autre donnée identifiante,
  comme un identifiant indirect, 7 bloc de coordonnées, qui réunit nom,
  adresse, téléphone… d'un seul rectangle) ;
  sur une note ouverte, elles changent son étiquette, et Suppr l'efface.

Raccourcis : ← → page, n p élément de liste, v vue puis élément suivant, r à
revoir, + − 0 zoom, t pivoter, 1 à 9 étiquette, a accepter les repérages,
m montrer ou cacher les repérages, Suppr supprimer la note ouverte, Échap
annuler, Ctrl+Entrée enregistrer la
note.

## Les données

Tout reste dans `data/annotation/`, hors de git :

- `notes.jsonl` : le carnet, en ajout seul (`carnet.py`). Le texte des notes
  et les remarques peuvent citer le cahier ; les analyses n'en lisent que les
  positions, les étiquettes et les qualifications sans remarques
  (`Carnet.positions`, `Carnet.qualifications(remarques=False)`).
- `listes/*.json` : les listes à revoir (`listes.py`), qui ne contiennent que
  des positions, des étiquettes et des commentaires sur la méthode. Une liste
  « à masquer » identifie chaque repérage ; ses rétablissements vont au
  carnet (`Carnet.retablir`).

Un module écrit une liste avec `annotation.listes.ecrire` (format dans la
docstring de `listes.py`).
