"""Lecture des référentiels publics, repris du module `insee` du POC.

- Code officiel géographique au 1er janvier 2019 :
  https://www.insee.fr/fr/information/3720946
- Populations légales millésimées 2017, publiées dans les limites du
  1er janvier 2019, colonne PMUN : https://www.insee.fr/fr/statistiques/4265429
- Découpage actuel et mouvements de communes depuis 1943 :
  https://www.insee.fr/fr/information/8740222
- Centre des communes, découpage actuel : https://geo.api.gouv.fr

Toutes sous Licence Ouverte 2.0 : « Source : Insee », « Source : IGN ».
"""

import csv
import io
import json
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

INSEE = "https://www.insee.fr/fr/statistiques/fichier"
COG_COMMUNES = f"{INSEE}/3720946/communes-01012019-csv.zip"
COG_DEPARTEMENTS = f"{INSEE}/3720946/departement2019-csv.zip"
COG_REGIONS = f"{INSEE}/3720946/region2019-csv.zip"
POPULATIONS = f"{INSEE}/4265429/ensemble.zip"
COG_COURANT = f"{INSEE}/8740222/v_commune_2026.csv"
MOUVEMENTS = f"{INSEE}/8740222/v_mvt_commune_2026.csv"
CENTRES = "https://geo.api.gouv.fr/communes?fields=code,centre"
CENTRES_ARRONDISSEMENTS = CENTRES + "&type=arrondissement-municipal"

COMMUNE = "COM"
ARRONDISSEMENT = "ARM"
# Quand un code figure sous plusieurs types (une commune nouvelle garde souvent
# le code de son chef-lieu, qui devient aussi commune déléguée), la commune de
# plein exercice l'emporte : c'est elle que désigne le code d'un cahier.
PRIORITE = {COMMUNE: 0, ARRONDISSEMENT: 1, "COMD": 2, "COMA": 3}
PIVOT = "2019-01-01"
# Un mouvement peut mener à un code lui-même disparu : on suit la chaîne, avec
# une borne contre les boucles.
CHAINE_MAX = 10


def telecharger(url: str, cache: Path) -> bytes:
    """Récupère une URL, ou sa copie locale si elle existe déjà."""
    fichier = cache / url.rsplit("/", 1)[-1].replace("?", "_").replace("&", "_")
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


@dataclass
class Commune:
    code: str
    type: str
    nom: str
    departement: str
    commune_parente: str = ""
    population: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    code_courant: str = ""
    nom_courant: str = ""


def communes_2019(cog: list[dict[str, str]]) -> dict[str, Commune]:
    """Une commune par code, la commune de plein exercice d'abord.

    Les entités rattachées n'ont pas de département dans le COG : elles
    prennent celui de leur commune parente.
    """
    retenues: dict[str, dict[str, str]] = {}
    for ligne in sorted(cog, key=lambda l: PRIORITE[l["typecom"]], reverse=True):
        retenues[ligne["com"]] = ligne
    departements = {code: l["dep"] for code, l in retenues.items() if l["dep"]}
    return {
        code: Commune(
            code=code,
            type=l["typecom"],
            nom=l["libelle"],
            departement=l["dep"] or departements[l["comparent"]],
            commune_parente=l["comparent"] if l["comparent"] != code else "",
        )
        for code, l in retenues.items()
    }


def collectivites_outre_mer(lignes: list[dict[str, str]]) -> dict[str, Commune]:
    """Saint-Pierre-et-Miquelon, Saint-Barthélemy et Saint-Martin.

    Absentes du COG des communes, mais pas du Grand débat : on les prend dans
    le fichier des populations légales.
    """
    return {
        l["CODCOL"] + l["CODCOM"][-2:]: Commune(
            code=l["CODCOL"] + l["CODCOM"][-2:],
            type=COMMUNE,
            nom=l["COM"],
            departement=l["CODCOL"],
            population=int(l["PMUN"]),
        )
        for l in lignes
    }


def populations(fichiers: list[list[dict[str, str]]]) -> dict[str, int]:
    """Population municipale par code.

    Une commune déléguée porte souvent le code de sa commune nouvelle : la
    ligne de plein exercice, lue en premier, reste la bonne.
    """
    resultat: dict[str, int] = {}
    for lignes in fichiers:
        for ligne in lignes:
            resultat.setdefault(ligne["DEPCOM"].strip(), int(ligne["PMUN"]))
    return resultat


def passage(
    communes: dict[str, Commune],
    courant: list[dict[str, str]],
    mouvements: list[dict[str, str]],
) -> None:
    """Renseigne ce que chaque commune de 2019 est devenue aujourd'hui."""
    courantes = {
        l["COM"]: l["LIBELLE"]
        for l in courant
        if l["TYPECOM"] in (COMMUNE, ARRONDISSEMENT)
    }
    apres: dict[str, list[dict[str, str]]] = {}
    for m in mouvements:
        if m["DATE_EFF"] > PIVOT:
            apres.setdefault(m["COM_AV"], []).append(m)

    for commune in communes.values():
        # Une entité déjà rattachée en 2019 suit sa commune parente.
        code = (
            commune.commune_parente
            if commune.type in ("COMD", "COMA")
            else commune.code
        )
        vus = {code}
        for _ in range(CHAINE_MAX):
            if code in courantes:
                commune.code_courant, commune.nom_courant = code, courantes[code]
                break
            suite = [
                m
                for m in apres.get(code, [])
                if m["TYPECOM_AP"] == COMMUNE and m["COM_AP"] not in vus
            ]
            if not suite:
                break
            code = min(suite, key=lambda m: m["DATE_EFF"])["COM_AP"]
            vus.add(code)


def centres(reponses: list[list[dict]]) -> dict[str, tuple[float, float]]:
    """(latitude, longitude) par code, depuis geo.api.gouv.fr."""
    resultat = {}
    for reponse in reponses:
        for c in reponse:
            if (c.get("centre") or {}).get("coordinates"):
                longitude, latitude = c["centre"]["coordinates"]
                resultat[c["code"]] = (latitude, longitude)
    return resultat


def lire(cache: Path) -> tuple[dict, dict, dict[str, Commune]]:
    """Régions, départements et communes de 2019, prêts à charger.

    Returns:
        ({code: nom}, {code: (nom, code région)}, {code: Commune}).
    """
    regions = {
        l["reg"]: l["libelle"]
        for l in lignes_csv(
            membre_zip(telecharger(COG_REGIONS, cache), "region2019.csv")
        )
    }
    departements = {
        l["dep"]: (l["libelle"], l["reg"])
        for l in lignes_csv(
            membre_zip(telecharger(COG_DEPARTEMENTS, cache), "departement2019.csv")
        )
    }
    communes = communes_2019(
        lignes_csv(
            membre_zip(telecharger(COG_COMMUNES, cache), "communes-01012019.csv")
        )
    )

    archive = telecharger(POPULATIONS, cache)
    com = lignes_csv(membre_zip(archive, "Collectivites_d_outre_mer.csv"), ";")
    communes |= collectivites_outre_mer(com)
    for l in com:
        departements[l["CODCOL"]] = (l["COL"], "")
    pmun = populations(
        [
            lignes_csv(membre_zip(archive, "Communes.csv"), ";"),
            lignes_csv(membre_zip(archive, "Communes_associees_ou_deleguees.csv"), ";"),
        ]
    )
    for commune in communes.values():
        commune.population = pmun.get(commune.code, commune.population)
    # Paris, Lyon et Marseille n'ont de population que par arrondissement.
    for commune in communes.values():
        if commune.type == ARRONDISSEMENT and commune.population is not None:
            parente = communes[commune.commune_parente]
            parente.population = (parente.population or 0) + commune.population

    passage(
        communes,
        lignes_csv(telecharger(COG_COURANT, cache).decode("utf-8")),
        lignes_csv(telecharger(MOUVEMENTS, cache).decode("utf-8")),
    )
    for code in collectivites_outre_mer(com):
        # Hors du COG actuel aussi : leur code n'a pas bougé.
        communes[code].code_courant = code
        communes[code].nom_courant = communes[code].nom

    coordonnees = centres(
        [
            json.loads(telecharger(CENTRES, cache)),
            json.loads(telecharger(CENTRES_ARRONDISSEMENTS, cache)),
        ]
    )
    for commune in communes.values():
        # Le centre actuel ne vaut que pour une commune qui existe encore.
        if commune.code_courant == commune.code and commune.code in coordonnees:
            commune.latitude, commune.longitude = coordonnees[commune.code]

    return regions, departements, communes
