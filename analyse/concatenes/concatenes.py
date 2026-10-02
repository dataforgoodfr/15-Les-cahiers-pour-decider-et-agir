"""Fichiers de cahiers citoyens qui contiennent le cahier d'une autre commune (issue #42).

Le rattachement à la commune (#19) lit le code INSEE dans le nom du fichier.
Chaque cahier numérisé commence par une page de garde, ajoutée à la
numérisation : « Cahier citoyen », le nom de la commune, son code INSEE (parfois
tronqué aux trois derniers chiffres) et son code postal. On lit ces pages dans
la couche texte, sans OCR.

Une page de garde désigne une commune quand son nom et son code y figurent
ensemble ; c'est la même commune que le fichier si elle a son code INSEE, son
code postal (des noms de fichier les inversent) ou la même commune parente
(arrondissement, commune déléguée). Chaque fichier reçoit une catégorie :

- `conforme` : aucune page de garde ne désigne une autre commune ;
- `concatene` : le cahier d'une autre commune suit celui du fichier ;
- `mal_rattache` : la première page de garde désigne une autre commune, et
  aucune ne désigne celle du fichier : le code du nom de fichier est faux ;
- `commune_retrouvee` : le nom de fichier n'a pas de commune (`00000`), la page
  de garde la donne ;
- `a_verifier` : aucune autre commune n'est lue, mais une page de garde après
  la première a une commune illisible (écrite à la main, le plus souvent) : un
  autre cahier commence peut-être là. Ses pages sont données, pour une
  vérification à la main ou par un modèle de vision.

Une page de garde manuscrite est fréquente (8 % d'entre elles), mais presque
toujours la première du fichier : elle ne cache alors pas de concaténation.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path

import pymupdf

_GARDE = re.compile(r"cahier\s+citoyen", re.IGNORECASE)
_INTERCALAIRE = re.compile(r"fin\s+des\s+pages\s+[ée]crites", re.IGNORECASE)
MOTS_MAX = 30  # une page de garde est courte
_NOM_FICHIER = re.compile(r"^CC_(\w{5})_\d{6}_(\w+?)_")
_CODE = re.compile(r"(?<!\d)(\d{5}|2[AB]\d{3})(?!\d)")
_CODE_TRONQUE = re.compile(r"-\s*(\d{3})(?!\d)")
_ESPACE_DANS_CODE = re.compile(r"(?<!\d)(\d{2}) (\d{3})(?!\d)")  # « 14 542 »
SANS_COMMUNE = {"00000", "99999"}
DEBUT_DE_FICHIER = 3  # pages : couverture, page de garde et son verso

CONFORME = "conforme"
CONCATENE = "concatene"
MAL_RATTACHE = "mal_rattache"
COMMUNE_RETROUVEE = "commune_retrouvee"
A_VERIFIER = "a_verifier"


@dataclass
class Fichier:
    nom: str
    pages: int
    # page de garde : numéro de page et texte
    gardes: list[tuple[int, str]] = field(default_factory=list)


def lire(chemin) -> Fichier:
    """Les pages de garde d'un PDF, repérées dans la couche texte."""
    with pymupdf.open(chemin) as doc:
        fichier = Fichier(Path(chemin).name, doc.page_count)
        for numero, page in enumerate(doc, start=1):
            texte = page.get_text()
            mots = texte.split()
            if len(mots) > MOTS_MAX or _INTERCALAIRE.search(texte):
                continue
            if _GARDE.search(texte):
                fichier.gardes.append((numero, " ".join(mots)))
    return fichier


def normaliser(texte: str) -> str:
    texte = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    texte = re.sub(r"\bsainte\b", "ste", re.sub(r"\bsaint\b", "st", texte.lower()))
    return re.sub(r"[^a-z0-9]", "", texte)


def departement(code: str) -> str:
    return code[:3] if code.startswith("97") else code[:2]


def communes_nommees(texte: str, insee: str, noms: dict[str, str]) -> set[str]:
    """Les codes INSEE dont le code et le nom figurent sur la page de garde.

    Un code tronqué (« - 288 ») est complété par le département du fichier.
    """
    apres = _GARDE.split(texte, maxsplit=1)[-1]
    compact = _ESPACE_DANS_CODE.sub(r"\1\2", apres)
    codes = set(_CODE.findall(compact))
    if insee:
        codes |= {departement(insee) + c for c in _CODE_TRONQUE.findall(compact)}
    lu = normaliser(apres)
    return {
        c
        for c in codes
        if c in noms and len(nom := normaliser(noms[c])) > 2 and nom in lu
    }


def codes_du_nom(nom: str) -> tuple[str, str]:
    """Code INSEE et code postal lus dans le nom du fichier ('' sans commune)."""
    m = _NOM_FICHIER.match(nom)
    if not m:
        return "", ""
    postal, insee = m.group(1), m.group(2)[:5]  # « 31588s » : suffixe ignoré
    if insee in SANS_COMMUNE or not _CODE.fullmatch(insee):
        insee = ""
    return insee, postal


def classer(fichier: Fichier, noms: dict[str, str], parentes: dict[str, str]):
    """Catégorie du fichier, pages de garde d'autres communes {page: codes} et
    pages de garde illisibles après la première."""
    insee, postal = codes_du_nom(fichier.nom)

    def racine(code):
        return parentes.get(code, code)

    meme = autres = 0
    trouvees: dict[int, list[str]] = {}
    illisibles: list[int] = []
    for rang, (page, texte) in enumerate(fichier.gardes):
        nommees = communes_nommees(texte, insee, noms)
        if not nommees:
            if rang > 0:
                illisibles.append(page)
            continue
        if insee and (
            {insee, postal} & nommees or racine(insee) in map(racine, nommees)
        ):
            meme += 1
        else:
            autres += 1
            trouvees[page] = sorted(nommees)
    if not trouvees:
        return (A_VERIFIER if illisibles else CONFORME), {}, illisibles
    if not insee:
        return COMMUNE_RETROUVEE, trouvees, illisibles
    if not meme and min(trouvees) <= DEBUT_DE_FICHIER:
        return MAL_RATTACHE, trouvees, illisibles
    return CONCATENE, trouvees, illisibles


def pages_d_autres_communes(fichier: Fichier, trouvees: dict[int, list[str]]) -> int:
    """Pages depuis chaque page de garde d'une autre commune jusqu'à la suivante."""
    debuts = sorted(page for page, _ in fichier.gardes) + [fichier.pages + 1]
    return sum(
        suivante - page for page, suivante in pairwise(debuts) if page in trouvees
    )
