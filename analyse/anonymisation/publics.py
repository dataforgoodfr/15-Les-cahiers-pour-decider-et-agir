"""Noms publics qu'il ne faut pas cacher (issue #128).

GLiNER prenait à tort pour des particuliers trois sortes de noms : la
commune du cahier, son maire, et les ministres de l'époque. Ce module les
réunit par cahier, pour écarter ces repérages.
"""

import csv
import re
from collections.abc import Iterable
from typing import NamedTuple

from anonymisation.detection import _simple

# Personnalités nationales que GLiNER prenait à tort pour des particuliers :
# les présidents de la Ve République et le gouvernement Édouard Philippe II,
# de décembre 2018 à mars 2019
# (https://fr.wikipedia.org/wiki/Gouvernement_Édouard_Philippe_(2))
PERSONNALITES = (
    ("Charles", "de Gaulle"),
    ("Georges", "Pompidou"),
    ("Valéry", "Giscard d'Estaing"),
    ("Valéry", "Giscard"),
    ("François", "Mitterrand"),
    ("Jacques", "Chirac"),
    ("Nicolas", "Sarkozy"),
    ("François", "Hollande"),
    ("Emmanuel", "Macron"),
    ("Édouard", "Philippe"),
    ("François", "de Rugy"),
    ("Christophe", "Castaner"),
    ("Nicole", "Belloubet"),
    ("Jean-Yves", "Le Drian"),
    ("Florence", "Parly"),
    ("Agnès", "Buzyn"),
    ("Bruno", "Le Maire"),
    ("Muriel", "Pénicaud"),
    ("Jean-Michel", "Blanquer"),
    ("Gérald", "Darmanin"),
    ("Frédérique", "Vidal"),
    ("Annick", "Girardin"),
    ("Jacqueline", "Gourault"),
    ("Franck", "Riester"),
    ("Didier", "Guillaume"),
    ("Roxana", "Maracineanu"),
    ("Élisabeth", "Borne"),
    ("Marc", "Fesneau"),
    ("Nathalie", "Loiseau"),
    ("Benjamin", "Griveaux"),
    ("Marlène", "Schiappa"),
    ("Sophie", "Cluzel"),
    ("Brune", "Poirson"),
    ("Emmanuelle", "Wargon"),
    ("Jean-Baptiste", "Lemoyne"),
    ("Geneviève", "Darrieussecq"),
    ("Christelle", "Dubos"),
    ("Adrien", "Taquet"),
    ("Mounir", "Mahjoubi"),
    ("Agnès", "Pannier-Runacher"),
    ("Gabriel", "Attal"),
    ("Olivier", "Dussopt"),
    ("Laurent", "Nuñez"),
    ("Julien", "Denormandie"),
    ("Sébastien", "Lecornu"),
    ("Amélie", "de Montchalin"),
    ("Sibeth", "Ndiaye"),
    ("Cédric", "O"),
)
# Maires au 14 janvier 2020, avant les municipales de mars : ceux du mandat
# 2014-2020, en fonction pendant le Grand débat (Répertoire national des
# élus ; la version de janvier 2020 n'est plus en ligne que sur archive.org)
MAIRES = (
    "https://web.archive.org/web/20200629074355id_/https://static.data.gouv.fr/"
    "resources/repertoire-national-des-elus-1/20200114-183638/9-rne-maires.txt"
)
COMMUNES = (
    "https://www.insee.fr/fr/statistiques/fichier/3720946/communes-01012019-csv.zip"
)
# Nouvelle-Calédonie et Polynésie : 988xx et 987xx ; les autres Z…, 97xxx
OUTRE_MER = {"ZN": "98", "ZP": "98"}
NOM_SEUL = 3  # lettres au moins pour qu'un nom public compte seul
# civilités et fonctions, seules ou devant un nom public (« M. le maire
# Dupont », « Monsieur le Président de la République »)
TITRES = {
    "m",
    "mr",
    "mme",
    "mlle",
    "monsieur",
    "madame",
    "mademoiselle",
    "le",
    "la",
    "les",
    "l",
    "de",
    "du",
    "des",
    "d",
    "president",
    "presidente",
    "ministre",
    "premier",
    "premiere",
    "maire",
    "republique",
    "etat",
    "chef",
    "general",
    "gouvernement",
    "senateur",
    "depute",
}


class Publics(NamedTuple):
    """Noms publics d'un cahier : formes simplifiées qui comptent seules, et
    suites de mots qui ne comptent qu'ensemble."""

    seuls: frozenset[str]
    suites: frozenset[tuple[str, ...]]


def _jetons(texte: str) -> tuple[str, ...]:
    return tuple(s for s in map(_simple, re.split(r"[\s'’\-]+", texte)) if s)


def publics(
    personnes: Iterable[tuple[str, str]], lieux: Iterable[str], prenoms: set[str]
) -> Publics:
    """Une personne : prénom et nom qui se suivent ; son nom seul, s'il est
    fait de plusieurs mots (« de Rugy ») ou s'il n'est pas un prénom et a
    NOM_SEUL lettres au moins (« Philippe » seul ne compte pas). Un lieu :
    son nom entier, en un mot ou en plusieurs."""
    exclus = {_simple(p) for p in prenoms}
    seuls, suites = set(), set()
    for prenom, nom in personnes:
        jetons = _jetons(nom)
        suites.add(_jetons(prenom) + jetons)
        if len(jetons) > 1:
            suites.add(jetons)
            seuls.add("".join(jetons))
        elif jetons and len(jetons[0]) >= NOM_SEUL and jetons[0] not in exclus:
            seuls.add(jetons[0])
    for lieu in lieux:
        jetons = _jetons(lieu)
        if jetons:
            seuls.add("".join(jetons))
            if len(jetons) > 1:
                suites.add(jetons)
    return Publics(frozenset(seuls), frozenset(suites))


def charger_maires(contenu: bytes) -> dict[str, tuple[str, str]]:
    """Code INSEE de la commune → (prénom, nom) de son maire. Outre-mer, le
    RNE code le département ZA, ZB… et la commune sur trois chiffres qui
    portent déjà le dernier chiffre du département (ZA, 101 : 97101)."""
    lignes = csv.DictReader(contenu.decode("latin-1").splitlines()[1:], delimiter="\t")
    sortie = {}
    for ligne in lignes:
        departement = ligne["Code du département (Maire)"].zfill(2)
        if departement.startswith("Z"):
            departement = OUTRE_MER.get(departement, "97")
        code = ligne["Code Insee de la commune"].zfill(3)
        sortie[departement + code] = (
            ligne["Prénom de l'élu"],
            ligne["Nom de l'élu"],
        )
    return sortie


def est_public(passage: str, noms: Publics) -> bool:
    """Un passage repéré n'est qu'un titre (« Monsieur le Président de la
    République »), ou un nom public après d'éventuels titres : « M. Macron »,
    « général de Gaulle », « Saint-Jean-de-Luz »."""
    jetons = _jetons(passage)
    if not jetons:
        return False
    for i in range(len(jetons) + 1):
        if any(j not in TITRES for j in jetons[:i]):
            break
        suite = jetons[i:]
        if not suite or "".join(suite) in noms.seuls or suite in noms.suites:
            return True
    return False
