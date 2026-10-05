"""Listes de pages à revoir, écrites par les modules d'analyse.

Une liste est un fichier JSON dans le dossier des listes :

    {
      "titre": "Gabarits repérés",
      "consigne": "Vérifier que chaque marque ouvre bien une contribution.",
      "elements": [
        {"fichier": "CC_….pdf", "page": 3,
         "marques": [{"x0": 0, "y0": 72.5, "x1": 595, "y1": 84.0,
                      "etiquette": "gabarit"}],
         "commentaire": "91 débuts sur 95 pages"}
      ]
    }

Les marques sont en points PDF, dans le repère de la page affichée. Une
liste a un mode :

- « accepter » (par défaut) : une marque qui porte un champ « note » (une
  étiquette de note) peut être acceptée d'un geste dans l'outil d'annotation, elle
  devient une note de cette étiquette ;
- « masquer » : chaque marque est cachée par défaut, et porte un « id ». Le
  relecteur rétablit les fausses alertes (`Carnet.retablir`) et encadre les
  oublis d'une note.

Une liste ne contient que des positions, des étiquettes et des commentaires
sur la méthode, jamais le texte d'un cahier.
"""

import json
import re
from pathlib import Path

NOM = re.compile(r"^[\w.-]+$")
MODES = ("accepter", "masquer")


def ecrire(
    dossier: Path,
    nom: str,
    titre: str,
    consigne: str,
    elements: list[dict],
    tache: str | None = None,
    mode: str = "accepter",
):
    """Écrit une liste. Sa tâche (« contributions », « anonymisation »…)
    sépare les statuts : une page vue pour une tâche ne l'est pas pour une
    autre."""
    if not NOM.match(nom):
        raise ValueError(f"nom de liste invalide : {nom}")
    if mode not in MODES:
        raise ValueError(f"mode inconnu : {mode}")
    if mode == "masquer" and not all(
        "id" in m for e in elements for m in e.get("marques", [])
    ):
        raise ValueError("une liste à masquer identifie chaque marque")
    dossier.mkdir(parents=True, exist_ok=True)
    contenu = {
        "titre": titre,
        "consigne": consigne,
        "tache": tache,
        "mode": mode,
        "elements": elements,
    }
    (dossier / f"{nom}.json").write_text(
        json.dumps(contenu, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def lire(dossier: Path, nom: str) -> dict:
    if not NOM.match(nom):
        raise KeyError(nom)
    chemin = dossier / f"{nom}.json"
    if not chemin.exists():
        raise KeyError(nom)
    return json.loads(chemin.read_text(encoding="utf-8"))


def sommaire(dossier: Path) -> list[dict]:
    """Nom, titre et taille de chaque liste."""
    listes = []
    for chemin in sorted(dossier.glob("*.json")):
        contenu = json.loads(chemin.read_text(encoding="utf-8"))
        listes.append(
            {
                "nom": chemin.stem,
                "titre": contenu.get("titre", chemin.stem),
                "elements": len(contenu.get("elements", [])),
            }
        )
    return listes
