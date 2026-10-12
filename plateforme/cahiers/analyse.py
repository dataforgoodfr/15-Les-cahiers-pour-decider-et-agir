"""Ce que les modules d'`analyse/` disent des pages, lu dans leurs sorties.

Des numéros de page et des catégories, jamais de texte :

- `typage/departements/*.csv` : type de chaque page, page de service ;
- `orientation/pages_tournees.csv` : pages tournées d'un quart de tour ;
- `ouvertures/ouvertures.csv` : pages d'ouverture imprimées ;
- `concatenes/concatenes.csv` : pages de garde d'une autre commune ;
- `annotation/notes.jsonl` : types et rotations vérifiés à la main, qui
  l'emportent sur les mesures.
"""

import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .models import Page

TYPES = {
    "vierge": Page.Type.VIERGE,
    "dactylographiée": Page.Type.DACTYLOGRAPHIEE,
    "mixte": Page.Type.MIXTE,
    "manuscrite": Page.Type.MANUSCRITE,
}
# `orientation` ne dit pas le sens du quart de tour ; l'outil d'annotation
# applique le sens horaire, le plus fréquent à la main.
ROTATION_DETECTEE = 90
# Catégories de `concatenes` dont une page de garde désigne une autre commune.
RATTACHES = {"concatene", "mal_rattache", "commune_retrouvee"}


@dataclass
class PageLue:
    type: str = ""
    rotation: int = 0
    service: bool = False
    ouverture: bool = False


def _lignes(chemin: Path):
    with chemin.open(encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f)


def pages(data: Path) -> dict[str, dict[int, PageLue]]:
    """Les pages de chaque fichier typé, avec ce qu'on en sait."""
    lues: dict[str, dict[int, PageLue]] = defaultdict(dict)
    for chemin in sorted((data / "typage" / "departements").glob("*.csv")):
        for ligne in _lignes(chemin):
            lues[ligne["fichier"]][int(ligne["page"])] = PageLue(
                type=TYPES.get(ligne["type_page"], ""),
                service=ligne["page_de_service"] == "1",
            )

    def page(fichier, numero):
        return lues.get(fichier, {}).get(numero)

    orientation = data / "orientation" / "pages_tournees.csv"
    if orientation.exists():
        for ligne in _lignes(orientation):
            for p in ligne["pages_tournees"].split():
                if lue := page(ligne["fichier"], int(p.removeprefix("p"))):
                    lue.rotation = ROTATION_DETECTEE

    ouvertures = data / "ouvertures" / "ouvertures.csv"
    if ouvertures.exists():
        for ligne in _lignes(ouvertures):
            if lue := page(ligne["fichier"], int(ligne["page"])):
                lue.ouverture = True

    for (fichier, numero, champ), valeur in qualifications(data).items():
        if not (lue := page(fichier, numero)):
            continue
        if champ == "rotation":
            lue.rotation = valeur
        elif champ == "type" and valeur in TYPES:
            lue.type = TYPES[valeur]
    return lues


def qualifications(data: Path) -> dict[tuple[str, int, str], object]:
    """Dernière valeur de chaque type ou rotation qualifié à la main."""
    notes = data / "annotation" / "notes.jsonl"
    valeurs = {}
    if not notes.exists():
        return valeurs
    with notes.open(encoding="utf-8") as f:
        for ligne in f:
            evenement = json.loads(ligne)
            if evenement.get("type") != "qualification":
                continue
            if evenement["champ"] not in ("type", "rotation"):
                continue
            cle = (evenement["fichier"], evenement["page"], evenement["champ"])
            valeurs[cle] = evenement["valeur"]
    return valeurs


def rattachements(data: Path) -> dict[str, list[tuple[int, str]]]:
    """Pour chaque fichier, les pages où commence le cahier d'une autre commune."""
    chemin = data / "concatenes" / "concatenes.csv"
    if not chemin.exists():
        return {}
    lus = {}
    for ligne in _lignes(chemin):
        if ligne["categorie"] not in RATTACHES:
            continue
        lus[ligne["fichier"]] = [
            (int(page.removeprefix("p")), code)
            for page, code in (m.split(":") for m in ligne["autres_communes"].split())
        ]
    return lus
