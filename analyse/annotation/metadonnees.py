"""Ce que les analyses ont détecté sur un cahier et sur chacune de ses pages.

Lit les sorties des modules, quand elles existent dans le dossier de données :

- `orientation/pages_tournees.csv` (#43) : pages tournées d'un quart de tour ;
- `manquantes/exemplaires.csv` (#43) : courriers et formulaires types
  incomplets, page voisine illisible ;
- `concatenes/concatenes.csv` (#42) : catégorie du fichier, autres communes,
  pages de garde illisibles, désordre des pages de service ;
- `inventaires/documents.csv` (#43) : pages attendues selon l'inventaire.

Des numéros et des codes, jamais de texte. Les pages se notent « p12 ».

Certaines détections cochent d'avance un problème de la page (`problemes`) :
la personne qui annote confirme ou décoche.
"""

import csv
from collections import defaultdict
from pathlib import Path

CATEGORIES = {
    "conforme": "conforme",
    "concatene": "contient le cahier d'autres communes",
    "commune_retrouvee": "commune retrouvée par la page de garde",
    "mal_rattache": "rattaché à une autre commune que celle du nom de fichier",
    "a_verifier": "page de garde à vérifier",
}


def _lire(chemin: Path) -> list[dict]:
    if not chemin.exists():
        return []
    with chemin.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _pages(liste: str) -> list[int]:
    """« p6 p7 » → [6, 7] ; « p3:garde_en_double » → [3]."""
    return [int(x.split(":")[0].removeprefix("p")) for x in liste.split()]


class Metadonnees:
    def __init__(self, dossier: Path):
        self.tournees = {
            r["fichier"]: set(_pages(r["pages_tournees"]))
            for r in _lire(dossier / "orientation/pages_tournees.csv")
            if r["pages_tournees"]
        }
        self.concatenes = {
            r["fichier"]: r for r in _lire(dossier / "concatenes/concatenes.csv")
        }
        self.exemplaires = defaultdict(list)
        for r in _lire(dossier / "manquantes/exemplaires.csv"):
            self.exemplaires[r["fichier"]].append(r)
        self.inventaires = {
            r["fichier"]: r for r in _lire(dossier / "inventaires/documents.csv")
        }

    def cahier(self, fichier: str) -> list[str]:
        """Constats sur le fichier entier."""
        constats = []
        c = self.concatenes.get(fichier)
        if c and c["categorie"] != "conforme":
            constats.append(CATEGORIES.get(c["categorie"], c["categorie"]))
            if c["autres_communes"]:
                constats.append(
                    f"autres communes : {c['autres_communes']} "
                    f"({c['pages_autres_communes']} pages)"
                )
        i = self.inventaires.get(fichier)
        if i and i["pages_attendues"] and i["pages_attendues"] != i["pages_presentes"]:
            constats.append(
                f"inventaire : {i['pages_attendues']} pages attendues, "
                f"{i['pages_presentes']} présentes"
            )
        if fichier in self.tournees:
            constats.append(f"{len(self.tournees[fichier])} pages tournées détectées")
        return constats

    def pages(self, fichier: str) -> dict[int, list[str]]:
        """Constats par numéro de page."""
        constats = defaultdict(list)
        for p in self.tournees.get(fichier, ()):
            constats[p].append("tournée d'un quart de tour (orientation)")
        c = self.concatenes.get(fichier)
        if c:
            for p in _pages(c["gardes_illisibles"]):
                constats[p].append("page de garde illisible (concatenes)")
            for x in c["desordre"].split():
                page, _, raison = x.partition(":")
                constats[int(page.removeprefix("p"))].append(
                    f"{raison.replace('_', ' ')} (concatenes)"
                )
        for e in self.exemplaires.get(fichier, ()):
            texte = f"formulaire type {e['modele']}, {e['statut']}"
            if e["pages_manquantes"] not in ("", "0"):
                texte += f" : {e['pages_manquantes']} page(s) manquante(s)"
            if e["voisine_illisible"] == "1":
                texte += ", page voisine illisible"
            for p in sorted(set(_pages(e["pages"]))):
                constats[p].append(f"{texte} (manquantes)")
        return dict(constats)

    def problemes(self, fichier: str) -> dict[int, set[str]]:
        """Problèmes que les analyses cochent d'avance, par numéro de page."""
        coches = defaultdict(set)
        for p in self.tournees.get(fichier, ()):
            coches[p].add("page tournée")
        c = self.concatenes.get(fichier)
        if c:
            for p in _pages(c["gardes_illisibles"]):
                coches[p].add("illisible")
            for x in c["desordre"].split():
                page, _, raison = x.partition(":")
                if "double" in raison:
                    coches[int(page.removeprefix("p"))].add("doublon")
        for e in self.exemplaires.get(fichier, ()):
            if e["pages_manquantes"] not in ("", "0"):
                for p in _pages(e["pages"]):
                    coches[p].add("page manquante")
        return dict(coches)
