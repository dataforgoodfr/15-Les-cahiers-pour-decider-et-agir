"""Panel de cahiers citoyens aligné sur l'échantillon du Campus Condorcet (issue #22).

Le Campus Condorcet travaille sur des départements choisis pour couvrir le
territoire, avec un profil socio-démographique et des tailles de communes
proches de la France, et sur les cahiers de Bordeaux (#21). Le panel reprend
cette liste : il n'a pas à être identique, mais s'en rapprocher permet de
comparer nos résultats aux leurs.

Méthode : on garde tous les cahiers citoyens (CC) de ces départements et
communes, sans tirage au hasard, si bien que le panel se refait à l'identique.
Le département est lu dans le code INSEE du nom de fichier ; les cahiers sans
commune (`00000`) ou de l'étranger (`99999`) n'en ont pas.
"""

import csv
import re
from collections import defaultdict
from pathlib import Path

from cascade.cascade import categorie

# Saint-Pierre-et-Miquelon (975) n'a aucun cahier citoyen dans le versement BnF.
DEPARTEMENTS_CAMPUS = (
    "04",
    "23",
    "25",
    "50",
    "80",
    "93",
    "971",
    "972",
    "973",
    "975",
    "976",
)
COMMUNES_CAMPUS = ("33063",)  # Bordeaux

_INSEE = re.compile(r"^CC_\d{5}_\d{6}_(\w{5})_")
SANS_COMMUNE = {"00000", "99999"}


def code_insee(fichier: str) -> str | None:
    m = _INSEE.match(fichier)
    return m.group(1) if m and m.group(1) not in SANS_COMMUNE else None


def departement(code: str) -> str:
    return code[:3] if code.startswith("97") else code[:2]


def dans_panel(code: str | None, departements, communes) -> bool:
    return code is not None and (code in communes or departement(code) in departements)


def lire_typage(chemins: list[Path]):
    """Les lignes de la sortie de `python -m typage` (fichiers ou dossiers)."""
    for chemin in chemins:
        for fichier in sorted(chemin.glob("*.csv")) if chemin.is_dir() else [chemin]:
            with fichier.open(encoding="utf-8", newline="") as f:
                yield from csv.DictReader(f)


def cahiers(lignes, departements, communes) -> list[dict]:
    """Une ligne par cahier du panel, avec ses pages comptées par type."""
    panel: dict[str, dict] = {}
    for ligne in lignes:
        fichier = ligne["fichier"]
        if categorie(fichier) != "CC":
            continue
        code = code_insee(fichier)
        if not dans_panel(code, departements, communes):
            continue
        cahier = panel.setdefault(
            fichier,
            {
                "fichier": fichier,
                "code_insee": code,
                "departement": departement(code),
                "pages": 0,
                "dactylographiees": 0,
                "mixtes": 0,
                "manuscrites": 0,
            },
        )
        cahier["pages"] += 1
        if ligne["page_de_service"] == "1" or ligne["type_page"] == "vierge":
            continue
        if ligne["type_page"] == "manuscrite":
            cahier["manuscrites"] += 1
        elif ligne["type_page"] == "mixte":
            cahier["mixtes"] += 1
        else:
            cahier["dactylographiees"] += 1
    return sorted(panel.values(), key=lambda c: c["fichier"])


def communes_du_panel(table: Path, departements, communes) -> list[dict]:
    """Les lignes de `communes.csv` (#19) des communes du panel.

    Même format que la table d'entrée : `python -m communes.representativite`
    la lit telle quelle pour comparer le panel à la France.
    """
    with table.open(encoding="utf-8", newline="") as f:
        return [
            ligne
            for ligne in csv.DictReader(f)
            if dans_panel(ligne["code_insee"], departements, communes)
        ]


def par_departement(panel: list[dict], communes) -> dict[str, dict]:
    """Cahiers et pages par département, ou par commune retenue à part."""
    compte: dict[str, dict] = defaultdict(lambda: defaultdict(int))
    for cahier in panel:
        code = cahier["code_insee"]
        cle = code if code in communes else cahier["departement"]
        c = compte[cle]
        c["cahiers"] += 1
        c["pages"] += cahier["pages"]
        c["ecrites"] += (
            cahier["dactylographiees"] + cahier["mixtes"] + cahier["manuscrites"]
        )
    return dict(sorted(compte.items()))
