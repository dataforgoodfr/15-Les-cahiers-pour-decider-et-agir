"""Le repérage mesuré sur l'édition Chabin, avec de fausses coordonnées (#128).

    uv run --group modeles python -m anonymisation.factices
        [--extraction ../data/cahiers_chabin-extraction.json]
        [--modele gliner] [--graine 0] [--cache data/sources]
        [--sortie data/anonymisation/factices]

L'édition Chabin est bien transcrite et déjà anonymisée : chaque donnée
retirée y est marquée à sa place par un crochet typé (« [Prénom NOM] »,
« [Adresse] », « [Téléphone] »…). On y remet de fausses données de la même
forme : prénoms de l'INSEE (naissances de 1930 à 2000), noms des maires du
Répertoire national des élus, adresses de la commune tirées de la Base
adresse nationale, téléphones et courriels construits. Le repérage
(`anonymisation.modeles`, GLiNER par défaut) lit ces textes ; on sait où
sont les données, sans erreur de lecture et sans donnée réelle.

Les signatures et paraphes, qui ne sont que dans l'image, sont retirés ;
les mots restitués par l'éditrice (« [de] ») sont gardés, les autres notes
retirées. Les données indirectes (« le seul médecin du village ») ne sont
pas marquées par l'édition : elles échappent à la mesure.

On mesure le modèle, les règles de `detection` et les deux réunis, à
chaque étape d'un filtrage cumulé (ETAPES) : noms publics
(`anonymisation.publics` : titres, commune, maire, présidents, ministres),
pronoms et passages sans majuscule, noms répandus dans plusieurs communes.
On y ajoute les zones de signature (`anonymisation.zones`) : dernières
lignes courtes et première ligne courte, cachées en entier. Pour chacun :

- le rappel : la part des données injectées entièrement couvertes, ou en
  partie ;
- la précision : la part des repérages qui touchent une donnée injectée ;
- les contributions où une donnée reste visible, et la part du texte
  masquée hors données injectées (ce que coûte le masquage).

Écrit dans la sortie `textes.jsonl` (les textes et leurs données
injectées), le cache des réponses du modèle et `mesure.md`. La commande
n'affiche que des comptes.
"""

import argparse
import csv
import gzip
import hashlib
import io
import json
import random
import re
import unicodedata
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from anonymisation.__main__ import PRENOMS
from anonymisation.detection import REPANDUE, charger_prenoms, mots_personnels
from anonymisation.modeles import Cache, charger
from anonymisation.publics import (
    COMMUNES,
    MAIRES,
    PERSONNALITES,
    TITRES,
    Publics,
    _jetons,
    charger_maires,
    est_public,
    publics,
)
from anonymisation.zones import MOTS, zones
from communes import sources

BAN = "https://adresse.data.gouv.fr/data/ban/adresses/latest/csv/adresses-{}.csv.gz"
NAISSANCES = (1930, 2000)  # années de naissance des prénoms tirés
DOMAINES = (
    "orange.fr",
    "wanadoo.fr",
    "gmail.com",
    "free.fr",
    "laposte.net",
    "sfr.fr",
    "hotmail.fr",
    "yahoo.fr",
)
# jetons d'un crochet de donnée personnelle, dans l'ordre où les essayer
JETON = re.compile(
    r"(?P<courriel>adresses?\s+(?:e-?)?mails?|e-?mails?|courriels?|mails?)"
    r"|(?P<adresse>adresses?)"
    r"|(?P<telephone>(?:n°\s*de\s*)?t[ée]l[ée]phones?(?:\s+portable)?|t[ée]l\b\.?"
    r"|portable)"
    r"|(?P<localite>localit[ée])"
    r"|(?P<signature>(?:deux|\d+)\s+signatures|signatures?|paraphes?)"
    r"|(?P<initiales>initiales)"
    r"|(?P<initiale>initiale(?:\s+pr[ée]nom)?)"
    r"|(?P<prenom>(?:deux\s+)?pr[ée]noms?)"
    r"|(?P<nom>noms?)"
    r"|(?P<initiale_prenom>P\b\.?)"
    r"|(?P<initiale_nom>N\b\.?)",
    re.IGNORECASE,
)
SEPARATEUR = r"(?:[\s,/]+|\bet\b)"
_JETON = re.sub(r"\(\?P<\w+>", "(?:", JETON.pattern)  # sans noms, pour répéter
CROCHET_PERSONNEL = re.compile(
    rf"\s*(?:{_JETON})(?:{SEPARATEUR}*(?:{_JETON}))*\s*", re.IGNORECASE
)
CROCHET = re.compile(r"\[([^\]]*)\]")
# un mot que l'éditrice restitue (« [de] », « c[om]mune ») ; pas ses notes
MOT_RESTITUE = re.compile(r"[a-zà-ÿ’'\-]+")
NOTES = {"sic", "manuscrit", "tampon", "illisible"}
ETIQUETTES = {
    "prenom": "prénom",
    "nom": "nom",
    "initiale": "initiale",
    "initiale_prenom": "initiale",
    "initiale_nom": "initiale",
    "initiales": "initiale",
    "adresse": "adresse",
    "localite": "adresse",
    "telephone": "téléphone",
    "courriel": "courriel",
}
PARTICULES = {"de", "du", "des", "d", "le", "la"}
DEUX = {"modèle", "règles"}
# sources réunies ; « fin k » : les k dernières lignes courtes (`zones`)
SOURCES = {
    "modèle": {"modèle"},
    "règles": {"règles"},
    "les deux": DEUX,
    "les deux + 1 ligne de fin": DEUX | {"fin 1"},
    "les deux + 2 lignes de fin": DEUX | {"fin 2"},
    "les deux + 3 lignes de fin": DEUX | {"fin 3"},
    "les deux + 2 lignes de fin + début": DEUX | {"fin 2", "début"},
}
FILTRAGE = ("modèle", "règles", "les deux")  # sources comparées à chaque étape
ETAPES = ("brut", "noms publics", "pronoms et minuscules", "noms répandus")
DESCRIPTIONS = (
    "brut : tous les repérages ;",
    (
        "noms publics retirés : titres seuls (« Monsieur le Président »), "
        "commune, maire (mandat 2014-2020), présidents de la Ve République, "
        "gouvernement de l'hiver 2018-2019 ;"
    ),
    (
        "pronoms et minuscules retirés : un nom, un prénom ou une « autre "
        "donnée » sans majuscule, ou fait de pronoms et de titres ;"
    ),
    f"noms répandus retirés : un nom repéré dans {REPANDUE} communes ou plus.",
)
# étiquettes où un repérage sans majuscule n'est pas un nom propre
SANS_MAJUSCULE = {"nom", "prénom", "autre donnée identifiante"}
MOTS_OUTILS = {
    "je",
    "j",
    "tu",
    "il",
    "elle",
    "on",
    "nous",
    "vous",
    "ils",
    "elles",
    "moi",
    "toi",
    "lui",
    "eux",
    "me",
    "te",
    "se",
    "mon",
    "ma",
    "mes",
    "ton",
    "ta",
    "tes",
    "son",
    "sa",
    "ses",
    "notre",
    "nos",
    "votre",
    "vos",
    "leur",
    "leurs",
    "personne",
    "chacun",
    "bonjour",
}


def _casse(nom: str) -> str:
    """« DE LA FONTAINE » → « De la Fontaine », « JEAN-PIERRE » → « Jean-Pierre »."""
    mots = re.split(r"([\s\-'’])", nom.lower())
    sortie = [
        m if (m in PARTICULES and i > 0) else m.capitalize() for i, m in enumerate(mots)
    ]
    return "".join(sortie)


def _ascii(texte: str) -> str:
    sans = unicodedata.normalize("NFD", texte.lower()).encode("ascii", "ignore")
    return re.sub(r"[^a-z]", "", sans.decode())


def charger_prenoms_ponderes(contenu: bytes) -> dict[str, int]:
    """Prénoms du fichier national de l'INSEE et leurs naissances, sur les
    années NAISSANCES."""
    totaux: Counter = Counter()
    with zipfile.ZipFile(io.BytesIO(contenu)) as archive:
        texte = io.TextIOWrapper(archive.open(archive.namelist()[0]), encoding="utf-8")
        for ligne in csv.DictReader(texte, delimiter=";"):
            annee = ligne["annais"]
            if (
                ligne["preusuel"].startswith("_")
                or not annee.isdigit()
                or not NAISSANCES[0] <= int(annee) <= NAISSANCES[1]
            ):
                continue
            totaux[_casse(ligne["preusuel"])] += int(ligne["nombre"])
    return dict(totaux)


def charger_adresses(contenu: bytes) -> dict[str, list[tuple[str, str, str]]]:
    """Code INSEE → adresses de la BAN : (numéro et voie, code postal, commune)."""
    sortie = defaultdict(list)
    with gzip.open(io.BytesIO(contenu), "rt", encoding="utf-8") as f:
        for ligne in csv.DictReader(f, delimiter=";"):
            numero = (ligne["numero"] + " " + ligne["rep"]).strip()
            sortie[ligne["code_insee"]].append(
                (
                    f"{numero} {ligne['nom_voie']}",
                    ligne["code_postal"],
                    ligne["nom_commune"],
                )
            )
    return dict(sortie)


class Faussaire:
    """Tire de fausses données, toujours les mêmes pour une même graine."""

    def __init__(
        self,
        prenoms: dict[str, int],
        noms: list[str],
        adresses: dict[str, list],
        graine: int,
    ):
        self.alea = random.Random(graine)
        self.prenoms, self.poids = list(prenoms), list(prenoms.values())
        self.noms = noms
        self.adresses = adresses
        self.communes = sorted({a[2] for liste in adresses.values() for a in liste})

    def prenom(self) -> str:
        return self.alea.choices(self.prenoms, self.poids)[0]

    def nom(self, exclus: set[str]) -> str:
        while True:
            nom = _casse(self.alea.choice(self.noms))
            if _ascii(nom) not in exclus:
                return nom

    def adresse(self, insee: str) -> str:
        choix = self.adresses.get(insee) or [
            a for liste in self.adresses.values() for a in liste
        ]
        voie, code, commune = self.alea.choice(choix)
        return self.alea.choice(
            (
                f"{voie}, {code} {commune}",
                f"{voie} {code} {commune}",
                f"{voie} à {commune}",
                voie,
            )
        )

    def localite(self) -> str:
        return self.alea.choice(self.communes)

    def telephone(self) -> str:
        chiffres = self.alea.choice(("05", "06", "07")) + "".join(
            str(self.alea.randrange(10)) for _ in range(8)
        )
        paires = [chiffres[i : i + 2] for i in range(0, 10, 2)]
        return self.alea.choice((" ", ".", "", "-")).join(paires)

    def courriel(self, prenom: str, nom: str) -> str:
        p, n = _ascii(prenom), _ascii(nom)
        local = self.alea.choice(
            (f"{p}.{n}", f"{p[:1]}{n}", f"{n}.{p}", f"{p}{n}{self.alea.randrange(100)}")
        )
        return f"{local}@{self.alea.choice(DOMAINES)}"


def _autre_prenom(vus: list[str], faussaire: Faussaire) -> str:
    while (prenom := faussaire.prenom()) in vus:
        pass
    return prenom


def _valeur(jeton: str, groupe: str, personne: dict, faussaire: Faussaire, insee):
    """La fausse valeur d'un jeton, dans sa casse (« NOM » → « DUPONT »)."""
    prenom, nom = personne["prenom"], personne["nom"]
    majuscules = jeton.isupper() and len(jeton) > 2
    if groupe == "prenom":
        # « [Prénom et Prénom NOM] » : un couple, deux prénoms différents
        vus = personne.setdefault("vus", [])
        valeur = prenom if not vus else _autre_prenom(vus, faussaire)
        vus.append(valeur)
        if jeton.lower().endswith("s") or jeton.lower().startswith("deux"):
            autre = _autre_prenom(vus, faussaire)
            vus.append(autre)
            valeur = f"{valeur} et {autre}"
    elif groupe == "nom":
        valeur = nom
    elif groupe in ("initiale", "initiale_prenom"):
        return prenom[0] + "."
    elif groupe == "initiale_nom":
        return nom[0] + "."
    elif groupe == "initiales":
        return f"{prenom[0]}.{nom[0]}."
    elif groupe == "adresse":
        return faussaire.adresse(insee)
    elif groupe == "localite":
        valeur = faussaire.localite()
    elif groupe == "telephone":
        return faussaire.telephone()
    elif groupe == "courriel":
        return faussaire.courriel(prenom, nom)
    else:
        return ""
    return valeur.upper() if majuscules else valeur


def injecter(
    texte: str, insee: str, faussaire: Faussaire, exclus: set[str]
) -> tuple[str, list[dict]]:
    """Le texte où chaque crochet de donnée personnelle reçoit de fausses
    données, et la place de chacune : (début, fin, étiquette)."""
    sortie, donnees, fin = "", [], 0
    for c in CROCHET.finditer(texte):
        sortie += texte[fin : c.start()]
        fin = c.end()
        contenu = c.group(1)
        if CROCHET_PERSONNEL.fullmatch(contenu):
            personne = {"prenom": faussaire.prenom(), "nom": faussaire.nom(exclus)}
            reste = 0
            for j in JETON.finditer(contenu):
                separateur = contenu[reste : j.start()]
                reste = j.end()
                valeur = _valeur(j.group(), j.lastgroup, personne, faussaire, insee)
                if not valeur:
                    continue
                if donnees and donnees[-1]["fin"] == len(sortie):
                    sortie += separateur if separateur.strip() else " "
                elif sortie and not sortie[-1].isspace():
                    sortie += " "
                debut = len(sortie)
                sortie += valeur
                donnees.append(
                    {
                        "debut": debut,
                        "fin": len(sortie),
                        "etiquette": ETIQUETTES[j.lastgroup],
                    }
                )
        elif MOT_RESTITUE.fullmatch(contenu.strip()) and contenu.strip() not in NOTES:
            sortie += contenu.strip()
    sortie += texte[fin:]
    return sortie, donnees


def localiser(passages: list[tuple[str, str]], texte: str) -> list[dict]:
    """Toutes les places de chaque passage dans le texte, comme `modeles.
    localiser` le fait sur une page : un passage repéré est caché partout."""
    places = {}
    for passage, etiquette in passages:
        if len(passage.strip()) < 2:
            continue
        for m in re.finditer(re.escape(passage.strip()), texte, re.IGNORECASE):
            places.setdefault(
                (m.start(), m.end()),
                {
                    "debut": m.start(),
                    "fin": m.end(),
                    "etiquette": etiquette,
                    "texte": m.group(),
                },
            )
    return sorted(places.values(), key=lambda r: (r["debut"], r["fin"]))


def regles(texte: str, commune: str, prenoms: frozenset) -> list[dict]:
    """Les règles de `detection` sur le texte : chaque mot reçoit pour cadre
    ses positions dans le texte, si bien que le cadre d'un repérage rend sa
    place."""
    mots, decalage = [], 0
    for i, ligne in enumerate(texte.split("\n")):
        for k, m in enumerate(re.finditer(r"\S+", ligne)):
            a, b = decalage + m.start(), decalage + m.end()
            mots.append((a, 0, b, 1, m.group(), 0, i, k))
        decalage += len(ligne) + 1
    return [
        {
            "debut": int(r["x0"]),
            "fin": int(r["x1"]),
            "etiquette": r["etiquette"],
            "texte": texte[int(r["x0"]) : int(r["x1"])],
            "source": "règles",
        }
        for r in mots_personnels(mots, commune, prenoms)
    ]


def _signes(texte: str, debut: int, fin: int) -> set[int]:
    return {i for i in range(debut, fin) if texte[i].isalnum()}


def _cle(passage: str) -> str:
    return "".join(j for j in _jetons(passage) if j not in TITRES)


def repandus(textes: list[dict]) -> set[str]:
    """Noms repérés dans REPANDUE communes ou plus : une personnalité, pas un
    particulier (la règle de `detection.retirer_repandues`)."""
    communes = defaultdict(set)
    for t in textes:
        for r in t["reperes"]:
            if r["etiquette"] in ("nom", "prénom"):
                communes[_cle(r["texte"])].add(t["insee"])
    return {c for c, s in communes.items() if c and len(s) >= REPANDUE}


def garde(r: dict, etape: int, noms: Publics, repandus_: set[str]) -> bool:
    """Le repérage survit-il aux filtres jusqu'à l'étape `etape` (ETAPES) ?"""
    if etape >= 1 and est_public(r["texte"], noms):
        return False
    if etape >= 2 and r["etiquette"] in SANS_MAJUSCULE:
        jetons = set(_jetons(r["texte"]))
        if not any(c.isupper() for c in r["texte"]) or jetons <= MOTS_OUTILS | TITRES:
            return False
    if etape >= 3 and r["etiquette"] in ("nom", "prénom"):
        return _cle(r["texte"]) not in repandus_
    return True


def reperes_de_zones(texte: str) -> list[dict]:
    """Les zones de signature (`zones`), en repérages : « fin 1 » à « fin 3 »
    selon le nombre de lignes de fin, « début » pour l'en-tête."""
    sortie = []
    for k in (1, 2, 3):
        sortie += [
            {
                "debut": a,
                "fin": b,
                "etiquette": "zone",
                "texte": texte[a:b],
                "source": f"fin {k}",
            }
            for a, b, _ in zones(texte, fin=k, debut=0)
        ]
    sortie += [
        {
            "debut": a,
            "fin": b,
            "etiquette": "zone",
            "texte": texte[a:b],
            "source": "début",
        }
        for a, b, cote in zones(texte, fin=2, debut=1)
        if cote == "début"
    ]
    return sortie


def mesurer(textes: list[dict], noms: dict[str, Publics]) -> dict:
    """Pour chaque source et chaque étape de filtrage : rappel par étiquette
    injectée, précision par étiquette repérée ; contributions où une donnée
    reste visible, et part du texte masquée hors données injectées."""
    repandus_ = repandus(textes)
    sortie = {}
    for source, gardees in SOURCES.items():
        for etape in range(len(ETAPES)):
            rappel, precision = defaultdict(Counter), defaultdict(Counter)
            ensemble = Counter()
            for t in textes:
                reperes = [
                    r
                    for r in t["reperes"]
                    if r["source"] in gardees
                    and garde(r, etape, noms[t["insee"]], repandus_)
                ]
                caches, donnees = set(), set()
                for r in reperes:
                    caches |= _signes(t["texte"], r["debut"], r["fin"])
                fuite = False
                for d in t["donnees"]:
                    signes = _signes(t["texte"], d["debut"], d["fin"])
                    donnees |= signes
                    c = rappel[d["etiquette"]]
                    c["donnees"] += 1
                    c["entieres"] += bool(signes) and signes <= caches
                    c["touchees"] += bool(signes & caches)
                    fuite |= not signes <= caches
                for r in reperes:
                    c = precision[r["etiquette"]]
                    c["reperes"] += 1
                    c["justes"] += any(
                        r["debut"] < d["fin"] and d["debut"] < r["fin"]
                        for d in t["donnees"]
                    )
                ensemble["avec_donnees"] += bool(t["donnees"])
                ensemble["fuites"] += fuite
                ensemble["hors_donnees"] += len(
                    _signes(t["texte"], 0, len(t["texte"])) - donnees
                )
                ensemble["masques"] += len(caches - donnees)
            sortie[source, etape] = {
                "rappel": rappel,
                "precision": precision,
                "ensemble": ensemble,
            }
    return sortie


def pourcent(a: int, b: int) -> str:
    return f"{a / b:.0%}" if b else "–"


def _somme(compte: dict) -> Counter:
    total = Counter()
    for c in compte.values():
        total.update(c)
    return total


ENTETE = (
    "| source | étape | repérages | précision | données entièrement couvertes "
    "| touchées | contributions où une donnée reste visible "
    "| texte masqué hors données |"
)


def _ligne(m: dict, source: str, etape: int, nom: str) -> str:
    r = _somme(m[source, etape]["rappel"])
    p = _somme(m[source, etape]["precision"])
    e = m[source, etape]["ensemble"]
    return (
        f"| {source} | {nom} | {p['reperes']} "
        f"| {pourcent(p['justes'], p['reperes'])} "
        f"| {pourcent(r['entieres'], r['donnees'])} "
        f"| {pourcent(r['touchees'], r['donnees'])} "
        f"| {e['fuites']} sur {e['avec_donnees']} "
        f"| {e['masques'] / e['hors_donnees']:.1%} |"
    )


def rapport(m: dict, modele: str, contributions: int, injectees: int) -> str:
    lignes = [
        "# Repérage sur l'édition Chabin, avec de fausses coordonnées",
        "",
        (
            f"{contributions} contributions transcrites de Charente-Maritime, "
            f"{injectees} fausses données remises à la place des crochets de "
            f"l'édition. Modèle : {modele} ; règles : `anonymisation.detection`."
        ),
        "",
        (
            "Une donnée est entièrement couverte si toutes ses lettres et chiffres "
            "sont dans un repérage ; touchée, s'il y en a au moins un. Un "
            "repérage est juste s'il touche une donnée injectée. Les repérages "
            "justes qui ne touchent pas de donnée de l'édition (contacts "
            "d'associations, de mairies) comptent comme faux."
        ),
        "",
        "Étapes de filtrage, cumulées :",
        "",
        *(f"{k}. {e}" for k, e in enumerate(DESCRIPTIONS)),
        "",
        "## Filtrage",
        "",
        ENTETE,
        "|---|---|---|---|---|---|---|---|",
    ]
    for source in FILTRAGE:
        for etape, nom in enumerate(ETAPES):
            lignes.append(_ligne(m, source, etape, f"{etape}. {nom}"))
    derniere = len(ETAPES) - 1
    lignes += [
        "",
        "## Zones de signature",
        "",
        (
            "Les dernières lignes courtes (au plus "
            f"{MOTS} mots) de chaque contribution, et sa première ligne si elle "
            "est courte, cachées en entier (`anonymisation.zones`), en plus des "
            f"repérages filtrés jusqu'à l'étape {derniere}."
        ),
        "",
        ENTETE,
        "|---|---|---|---|---|---|---|---|",
        *(
            _ligne(m, source, derniere, ETAPES[derniere])
            for source in SOURCES
            if source == "les deux" or source not in FILTRAGE
        ),
    ]
    for source, etape in (("modèle", 0), ("les deux + 2 lignes de fin", derniere)):
        rappel, precision = m[source, etape]["rappel"], m[source, etape]["precision"]
        lignes += [
            "",
            f"## Détail : {source}, étape {etape} ({ETAPES[etape]})",
            "",
            "| donnée injectée | nombre | entièrement couvertes | touchées |",
            "|---|---|---|---|",
            *(
                f"| {e} | {c['donnees']} | {pourcent(c['entieres'], c['donnees'])} "
                f"| {pourcent(c['touchees'], c['donnees'])} |"
                for e, c in sorted(rappel.items())
            ),
            "",
            "| repérage | nombre | précision |",
            "|---|---|---|",
            *(
                f"| {e} | {c['reperes']} | {pourcent(c['justes'], c['reperes'])} |"
                for e, c in sorted(precision.items())
            ),
        ]
    return "\n".join(lignes)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--extraction",
        type=Path,
        default=Path("../data/cahiers_chabin-extraction.json"),
    )
    parser.add_argument("--modele", default="gliner")
    parser.add_argument("--graine", type=int, default=0)
    parser.add_argument("--cache", type=Path, default=Path("data/sources"))
    parser.add_argument(
        "--sortie", type=Path, default=Path("data/anonymisation/factices")
    )
    args = parser.parse_args()

    extraction = [e for e in json.loads(args.extraction.read_text()) if e]
    departements = sorted({e["city"]["insee"][:2] for e in extraction})
    adresses = {}
    for d in departements:
        adresses |= charger_adresses(sources.telecharger(BAN.format(d), args.cache))
    maires = charger_maires(sources.telecharger(MAIRES, args.cache))
    prenoms_insee = charger_prenoms(sources.telecharger(PRENOMS, args.cache))
    communes = {
        c["com"]: (c["libelle"], c["nccenr"])
        for c in sources.premier_csv_zip(sources.telecharger(COMMUNES, args.cache))
    }
    noms, exclus = {}, {_ascii(n) for _, n in PERSONNALITES}
    for e in extraction:
        insee = e["city"]["insee"]
        maire = [maires[insee]] if insee in maires else []
        noms[insee] = publics(
            PERSONNALITES + tuple(maire), communes.get(insee, ()), prenoms_insee
        )
        exclus |= {_ascii(n) for _, n in maire}
    faussaire = Faussaire(
        charger_prenoms_ponderes(sources.telecharger(PRENOMS, args.cache)),
        sorted({n for _, n in maires.values()}),
        adresses,
        args.graine,
    )

    modele = charger(args.modele)
    cache = Cache(
        args.sortie / f"{re.sub(r'[^\w.-]', '_', modele.nom)}-{args.graine}.jsonl"
    )
    textes = []
    for e in extraction:
        insee = e["city"]["insee"]
        for rang, c in enumerate(e["contributions"], 1):
            texte, donnees = injecter(c["text"], insee, faussaire, exclus)
            # la clé suit le texte injecté : un autre tirage n'est pas resservi
            cle = f"{insee}:{hashlib.sha1(texte.encode()).hexdigest()[:12]}"
            passages = cache.obtenir(cle, rang, modele, texte)
            textes.append(
                {
                    "insee": insee,
                    "rang": rang,
                    "texte": texte,
                    "donnees": donnees,
                    "reperes": [
                        r | {"source": "modèle"} for r in localiser(passages, texte)
                    ]
                    + regles(texte, e["city"]["commune"], prenoms_insee)
                    + reperes_de_zones(texte),
                }
            )
        print(
            f"{e['city']['commune']} : {len(e['contributions'])} contributions",
            flush=True,
        )
    args.sortie.mkdir(parents=True, exist_ok=True)
    with (args.sortie / f"textes-{args.graine}.jsonl").open("w", encoding="utf-8") as f:
        for t in textes:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    m = mesurer(textes, noms)
    texte = rapport(m, modele.nom, len(textes), sum(len(t["donnees"]) for t in textes))
    (args.sortie / "mesure.md").write_text(texte + "\n", encoding="utf-8")
    print(texte)


if __name__ == "__main__":
    main()
