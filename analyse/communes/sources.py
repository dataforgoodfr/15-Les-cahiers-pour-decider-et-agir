"""Téléchargement et lecture des référentiels de l'INSEE.

Seul module qui accède au réseau. Chaque fichier est gardé en cache local
(`data/sources/` par défaut) : une seconde exécution ne retélécharge rien.
"""

import csv
import io
import urllib.request
import zipfile
from pathlib import Path

import openpyxl

# Code officiel géographique au 1er janvier 2019 : https://www.insee.fr/fr/information/3720946
COG_COMMUNES = (
    "https://www.insee.fr/fr/statistiques/fichier/3720946/communes-01012019-csv.zip"
)
COG_DEPARTEMENTS = (
    "https://www.insee.fr/fr/statistiques/fichier/3720946/departement2019-csv.zip"
)
COG_REGIONS = "https://www.insee.fr/fr/statistiques/fichier/3720946/region2019-csv.zip"
# Populations légales millésimées 2017, dans les limites au 1er janvier 2019 :
# https://www.insee.fr/fr/statistiques/4265429
POPULATIONS = "https://www.insee.fr/fr/statistiques/fichier/4265429/ensemble.zip"
# Mouvements de communes depuis 1943 : https://www.insee.fr/fr/information/8740222
MOUVEMENTS = (
    "https://www.insee.fr/fr/statistiques/fichier/8740222/v_mvt_commune_2026.csv"
)
# Grille communale de densité à 4 niveaux, géographie au 1er janvier 2021 :
# https://www.insee.fr/fr/information/2114627
GRILLE_DENSITE = (
    "https://www.insee.fr/fr/statistiques/fichier/2114627/grille_densite_2021.zip"
)


def telecharger(url: str, cache: Path) -> bytes:
    """Récupère une URL, ou sa copie locale si elle existe déjà."""
    fichier = cache / url.rsplit("/", 1)[-1]
    if fichier.exists():
        return fichier.read_bytes()
    requete = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(requete, timeout=180) as reponse:
        contenu = reponse.read()
    cache.mkdir(parents=True, exist_ok=True)
    fichier.write_bytes(contenu)
    return contenu


def lignes_csv(texte: str, delimiteur: str = ",") -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(texte.lstrip("﻿")), delimiter=delimiteur))


def membre_zip(contenu: bytes, nom: str) -> str:
    with zipfile.ZipFile(io.BytesIO(contenu)) as archive:
        return archive.read(nom).decode("utf-8")


def premier_csv_zip(contenu: bytes) -> list[dict[str, str]]:
    """Lit l'unique CSV d'une archive du COG."""
    with zipfile.ZipFile(io.BytesIO(contenu)) as archive:
        nom = next(n for n in archive.namelist() if n.endswith(".csv"))
        return lignes_csv(archive.read(nom).decode("utf-8"))


def grille_densite(contenu: bytes) -> dict[str, int]:
    """Degré de densité (1 à 4) par code commune, depuis le fichier détaillé."""
    with zipfile.ZipFile(io.BytesIO(contenu)) as archive:
        nom = next(n for n in archive.namelist() if "detaille" in n)
        classeur = openpyxl.load_workbook(io.BytesIO(archive.read(nom)), read_only=True)
    feuille = classeur.worksheets[0]
    grille = {}
    for ligne in feuille.iter_rows(min_row=2, values_only=True):
        if ligne[0] and ligne[2]:
            grille[str(ligne[0]).strip()] = int(ligne[2])
    return grille
