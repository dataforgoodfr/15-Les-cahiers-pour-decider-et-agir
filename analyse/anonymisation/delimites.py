"""Le repérage mesuré sur les cahiers délimités à la main (#128).

    uv run --group modeles python -m anonymisation.delimites
        [--delimitation data/delimitation/contributions.csv]
        [--versement data/versement] [--typage data/typage/departements]
        [--annotation data/annotation] [--reperes data/anonymisation/reperes.csv]
        [--communes data/communes/communes.csv] [--cache data/sources]
        [--modeles data/anonymisation/modeles] [--modele gliner]
        [--sortie data/anonymisation/delimites]

La chaîne mesurée sur l'édition Chabin (`anonymisation.factices`), cette
fois sur les vraies pages dactylographiées des cahiers délimités à la main :
règles de `detection`, encre sans texte (l'écriture à la main), modèle
(GLiNER, réponses en cache dans `modeles/`), filtres (`factices.garde`) et
zones de signature (`anonymisation.zones`) de chaque contribution délimitée.

La référence : les données personnelles et signatures encadrées à la main
sur les pages vues à la délimitation ; sur les pages relues en masquage,
s'y ajoutent les repérages que la relecture a laissés cachés
(`mesure.reference`). Rien ne garantit que chaque page ait été relue avec
le même soin : le rappel est fiable, la précision n'est qu'un minorant (un
repérage hors des encadrés peut être une donnée oubliée).

Une donnée encadrée est couverte si tous les mots de la couche texte qu'elle
contient sont dans un repérage gardé, hors ponctuation et mots du gabarit
(imprimés sur trois pages ou plus du cahier : les libellés d'un formulaire),
et si 80 % de l'encre hors couche texte (l'écriture à la main) l'est. Un
nom répété sur trois pages passerait pour un libellé : le rappel est
légèrement surestimé. Les contributions sont rangées par page puis par
hauteur, sans colonnes ni doubles pages.

Écrit dans la sortie `mesure.md`, et `visibles.csv` : la place des données
que la chaîne complète laisse visibles, à vérifier dans l'outil
d'annotation. Des comptes et des positions, jamais de texte.
"""

import argparse
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pymupdf

from annotation import listes
from annotation.carnet import Carnet
from anonymisation.__main__ import (
    PRENOMS,
    RELECTURE,
    _ordonner,
    image_grise,
    mots_de_la_page,
)
from anonymisation.detection import (
    _simple,
    charger_prenoms,
    encre_sans_texte,
    mots_personnels,
)
from anonymisation.factices import ETAPES, garde, pourcent, repandus
from anonymisation.masquage import CHAMPS, dans
from anonymisation.mesure import A_CACHER, reference
from anonymisation.modeles import Cache, charger, localiser, texte_de_la_page
from anonymisation.publics import (
    COMMUNES,
    MAIRES,
    PERSONNALITES,
    Publics,
    charger_maires,
    publics,
)
from anonymisation.zones import zones
from communes import sources
from contributions.__main__ import pages_lues
from panel.panel import code_insee

TACHE = "selection"  # la délimitation, où l'on encadre aussi les données
DEDANS = 0.5  # part d'un mot dans un cadre pour qu'il y soit
ENCRE_MIN = 20  # pixels d'encre au moins pour qu'une donnée soit écrite à la main
ENCRE_COUVERTE = 0.8  # part de son encre à couvrir
GABARIT = 3  # pages d'un cahier où revient un mot imprimé du formulaire
TOUS = {"règles", "modèle", "encre"}
SOURCES = {
    "modèle": {"modèle"},
    "règles": {"règles"},
    "règles + modèle": {"règles", "modèle"},
    "règles + modèle + encre": TOUS,
    "règles + modèle + encre + zones": TOUS | {"zones"},
}
FILTRAGE = ("modèle", "règles", "règles + modèle")
COMPLETE = "règles + modèle + encre + zones"
LEXIQUE = "https://www.lexique.org/databases/Lexique383/Lexique383.tsv"
# variantes de la détection d'encre (`detection.encre_sans_texte`) : seuil de
# gris, densité au-delà de laquelle une zone est un aplat, et encre gardée
# sous les mots hors lexique (une lecture fautive de l'écriture à la main)
VARIANTES = {
    "encre pâle": {"seuil": 170},
    "encre raturée": {"densite_max": 0.4},
    "encre sous OCR": {"sous_ocr": True},
    "encre pâle, raturée, sous OCR": {
        "seuil": 170,
        "densite_max": 0.4,
        "sous_ocr": True,
    },
}
for _nom in VARIANTES:
    SOURCES[f"règles + modèle + {_nom} + zones"] = {"règles", "modèle", _nom, "zones"}


class Paresseux:
    """Le modèle, chargé seulement si une page manque à son cache."""

    def __init__(self, nom: str):
        self.nom_demande = nom
        self.modele = None

    def __call__(self, texte: str):
        if self.modele is None:
            self.modele = charger(self.nom_demande)
        return self.modele(texte)


def _cadre(m: tuple) -> dict:
    return dict(zip(CHAMPS, m[:4], strict=True))


def texte_du_cadre(mots: list[tuple], cadre: dict) -> str:
    """Les mots de la couche texte dans un cadre, dans l'ordre de la page."""
    dedans = [m for m in mots if dans(_cadre(m), cadre) >= DEDANS]
    return " ".join(m[4] for m in sorted(dedans, key=lambda m: (m[5], m[6], m[7])))


def lignes_de_la_page(mots: list[tuple]) -> list[dict]:
    """Les lignes de la couche texte : texte et cadre, de haut en bas."""
    lignes = defaultdict(list)
    for m in mots:
        lignes[m[5], m[6]].append(m)
    sortie = []
    for ligne in lignes.values():
        ligne.sort(key=lambda m: m[7])
        sortie.append(
            {
                "texte": " ".join(m[4] for m in ligne),
                "x0": min(m[0] for m in ligne),
                "y0": min(m[1] for m in ligne),
                "x1": max(m[2] for m in ligne),
                "y1": max(m[3] for m in ligne),
            }
        )
    return sorted(sortie, key=lambda li: (li["y0"], li["x0"]))


def contribution_de(debuts: list[tuple], page: int, y: float) -> int | None:
    """Le rang de la contribution où tombe (page, y) : la dernière qui
    commence avant. `debuts` : (page, y, fin_page, fin_y, rang), triés."""
    rang = None
    for p, yd, pf, yf, r in debuts:
        if (p, yd) <= (page, y):
            rang = r if (page, y) <= (pf, yf) else None
    return rang


def reperes_de_zones(lignes: dict[int, list[dict]], debuts: list[tuple]) -> list[dict]:
    """Les zones de signature de chaque contribution, en cadres de lignes."""
    par_contribution = defaultdict(list)
    for page, ls in sorted(lignes.items()):
        for li in ls:
            rang = contribution_de(debuts, page, li["y0"])
            if rang is not None:
                par_contribution[rang].append((page, li))
    sortie = []
    for rang, ls in par_contribution.items():
        texte, places = "", []
        for page, li in ls:
            places.append((len(texte), page, li))
            texte += li["texte"] + "\n"
        for a, _, _ in zones(texte, fin=2, debut=1):
            page, li = next((p, li) for d, p, li in places if d == a)
            sortie.append(
                {
                    "page": page,
                    **{k: li[k] for k in CHAMPS},
                    "etiquette": "zone",
                    "texte": "",
                    "source": "zones",
                }
            )
    return sortie


def gabarit(pages: dict) -> dict[str, set[str]]:
    """Par cahier, les mots imprimés sur GABARIT pages ou plus : les libellés
    d'un formulaire (« Nom », « Adresse »), qui n'ont pas à être cachés."""
    compte = defaultdict(Counter)
    for (fichier, _), p in pages.items():
        compte[fichier].update({_simple(m[4]) for m in p["mots"]})
    return {f: {s for s, n in c.items() if n >= GABARIT} for f, c in compte.items()}


def encre_de(gris: np.ndarray, mots: list[tuple], donnee: dict) -> np.ndarray:
    """L'encre du cadre d'une donnée, hors des mots de la couche texte : ce
    qui est écrit à la main (un pixel par point, repère de la page)."""
    encre = gris < 128
    for m in mots:
        encre[max(0, int(m[1])) : int(m[3]) + 1, max(0, int(m[0])) : int(m[2]) + 1] = (
            False
        )
    x0, y0, x1, y1 = (max(0, int(donnee[k])) for k in CHAMPS)
    return encre[y0 : y1 + 1, x0 : x1 + 1]


def _encre_couverte(donnee: dict, gardes: list[dict]) -> float:
    encre = donnee["encre"]
    x0, y0 = max(0, int(donnee["x0"])), max(0, int(donnee["y0"]))
    couvert = np.zeros_like(encre)
    for g in gardes:
        a, b = max(int(g["x0"]) - x0, 0), max(int(g["x1"]) - x0 + 1, 0)
        c, d = max(int(g["y0"]) - y0, 0), max(int(g["y1"]) - y0 + 1, 0)
        couvert[c:d, a:b] = True
    return (encre & couvert).sum() / encre.sum()


def couverte(
    donnee: dict,
    mots: list[tuple],
    gardes: list[dict],
    imprimes: set[str] = frozenset(),
) -> bool:
    """Tous les mots de la donnée sont couverts, hors ponctuation et mots du
    gabarit ; et, si elle porte de l'écriture à la main (`encre`), au moins
    ENCRE_COUVERTE de cette encre."""
    dedans = [
        _cadre(m)
        for m in mots
        if dans(_cadre(m), donnee) >= DEDANS
        and _simple(m[4])
        and _simple(m[4]) not in imprimes
    ]
    if not all(any(dans(m, g) >= DEDANS for g in gardes) for m in dedans):
        return False
    encre = donnee.get("encre")
    if encre is None or encre.sum() < ENCRE_MIN:
        return True
    return _encre_couverte(donnee, gardes) >= ENCRE_COUVERTE


def gardes_de(
    p: dict, gardees: set[str], etape: int, noms_: Publics, repandus_: set[str]
) -> list[dict]:
    """Les repérages d'une page venus de `gardees` qui survivent aux filtres
    jusqu'à `etape`."""
    return [
        r
        for r in p["reperes"]
        if r["source"] in gardees and garde(r, etape, noms_, repandus_)
    ]


def mesurer(
    pages: dict,
    noms: dict,
    repandus_: set[str],
    lexique: set[str] = frozenset(),
    sources: dict[str, set[str]] = SOURCES,
) -> dict:
    """Pour chaque source et étape : données couvertes par étiquette,
    repérages qui touchent une donnée, contributions où une donnée reste
    visible, mots hors données cachés."""
    sortie = {}
    imprimes = gabarit(pages)
    for source, gardees in sources.items():
        etapes = range(len(ETAPES)) if source in FILTRAGE else [len(ETAPES) - 1]
        for etape in etapes:
            rappel, ensemble = defaultdict(Counter), Counter()
            fuites, avec = set(), set()
            for (fichier, n), p in pages.items():
                gardes = gardes_de(p, gardees, etape, noms[fichier], repandus_)
                for d in p["donnees"]:
                    ok = couverte(d, p["mots"], gardes, imprimes[fichier])
                    c = rappel[d["etiquette"]]
                    c["donnees"] += 1
                    c["couvertes"] += ok
                    if d["contribution"] is not None:
                        avec.add((fichier, d["contribution"]))
                        if not ok:
                            fuites.add((fichier, d["contribution"]))
                for r in gardes:
                    ensemble["reperes"] += 1
                    ensemble["justes"] += any(
                        dans(r, d) >= DEDANS or dans(d, r) >= DEDANS
                        for d in p["donnees"]
                    )
                for mot in p["mots"]:
                    m = _cadre(mot)
                    if any(dans(m, d) >= DEDANS for d in p["donnees"]):
                        continue
                    cache = any(dans(m, g) >= DEDANS for g in gardes)
                    ensemble["hors_donnees"] += 1
                    ensemble["masques"] += cache
                    if _simple(mot[4]) in lexique:
                        ensemble["lexique_hors_donnees"] += 1
                        ensemble["lexique_masques"] += cache
            ensemble["fuites"], ensemble["avec_donnees"] = len(fuites), len(avec)
            sortie[source, etape] = {"rappel": rappel, "ensemble": ensemble}
    return sortie


def visibles(pages: dict, noms: dict, repandus_: set[str]) -> list[dict]:
    """Les données encadrées que la chaîne complète laisse visibles : des
    positions, à vérifier dans l'outil d'annotation."""
    imprimes = gabarit(pages)
    gardees = SOURCES[COMPLETE]
    sortie = []
    for (fichier, n), p in sorted(pages.items()):
        gardes = gardes_de(p, gardees, len(ETAPES) - 1, noms[fichier], repandus_)
        for d in p["donnees"]:
            if not couverte(d, p["mots"], gardes, imprimes[fichier]):
                sortie.append(
                    {"fichier": fichier, "page": n, **{k: d[k] for k in CHAMPS}}
                    | {"etiquette": d["etiquette"]}
                )
    return sortie


LISTE = "anonymisation-visibles"


def ecrire_liste(dossier: Path, visibles_: list[dict]) -> None:
    """La liste des pages où une donnée encadrée reste visible, pour l'outil
    d'annotation : les cahiers les plus touchés d'abord."""
    par_page = defaultdict(list)
    for v in visibles_:
        par_page[v["fichier"], int(v["page"])].append(v)
    par_cahier = Counter(v["fichier"] for v in visibles_)
    elements = [
        {
            "fichier": f,
            "page": n,
            "marques": [
                {"etiquette": v["etiquette"], "note": "reste visible"}
                | {k: float(v[k]) for k in CHAMPS}
                for v in vs
            ],
            "commentaire": f"{len(vs)} donnée(s) encadrée(s) que la chaîne laisse visible(s)",
        }
        for (f, n), vs in sorted(
            par_page.items(), key=lambda e: (-par_cahier[e[0][0]], e[0])
        )
    ]
    listes.ecrire(
        dossier,
        LISTE,
        "Données encadrées restées visibles",
        (
            "Chaque marque orange est une donnée encadrée à la main que la chaîne "
            "complète (règles, modèle, encre, filtres, zones) laisse visible. "
            "Regarder pourquoi : écriture à la main sous une couche OCR fautive, "
            "champ de formulaire, en-tête de courriel… Ne pas accepter les "
            "marques (« a ») : ce sont déjà des notes."
        ),
        elements,
        tache="verification-anonymisation",
    )


ENTETE = (
    "| source | étape | repérages | touchent une donnée | données couvertes "
    "| contributions où une donnée reste visible | mots hors données cachés "
    "| dont mots du lexique |"
)


def _ligne(m: dict, source: str, etape: int) -> str:
    r = Counter()
    for c in m[source, etape]["rappel"].values():
        r.update(c)
    e = m[source, etape]["ensemble"]
    return (
        f"| {source} | {etape}. {ETAPES[etape]} | {e['reperes']} "
        f"| {pourcent(e['justes'], e['reperes'])} "
        f"| {pourcent(r['couvertes'], r['donnees'])} "
        f"| {e['fuites']} sur {e['avec_donnees']} "
        f"| {pourcent(e['masques'], e['hors_donnees'])} "
        f"| {pourcent(e['lexique_masques'], e['lexique_hors_donnees'])} |"
    )


def rapport(m: dict, pages: int, cahiers: int, donnees: int, modele: str) -> str:
    derniere = len(ETAPES) - 1
    lignes = [
        "# Repérage sur les cahiers délimités à la main",
        "",
        (
            f"{pages} pages dactylographiées vues à la délimitation, dans "
            f"{cahiers} cahiers : {donnees} données personnelles ou signatures "
            f"encadrées à la main. Modèle : {modele}."
        ),
        "",
        (
            "Le rappel est fiable ; la précision (« touchent une donnée ») n'est "
            "qu'un minorant, un repérage hors des encadrés pouvant être une "
            "donnée oubliée. Étapes de filtrage : celles de "
            "`anonymisation.factices`."
        ),
        "",
        "## Filtrage",
        "",
        ENTETE,
        "|---|---|---|---|---|---|---|---|",
        *(_ligne(m, s, e) for s in FILTRAGE for e in range(len(ETAPES))),
        "",
        "## Chaîne complète",
        "",
        (
            "L'encre sans texte cache l'écriture à la main des pages "
            "dactylographiées ; les zones, les deux dernières lignes courtes et "
            "la première ligne courte de chaque contribution délimitée."
        ),
        "",
        ENTETE,
        "|---|---|---|---|---|---|---|---|",
        *(_ligne(m, s, derniere) for s in ("règles + modèle + encre", COMPLETE)),
        "",
        "## Variantes de l'encre",
        "",
        (
            "Encre pâle : pixel encré sous 170 au lieu de 128 (écriture effacée). "
            "Encre raturée : une zone n'est un aplat qu'au-delà de 40 % d'encre au "
            "lieu de 15 % (coordonnées barrées). Encre sous OCR : l'encre sous un "
            "mot de la couche texte hors du lexique courant (Lexique 3.83) reste à "
            "cacher, car c'est souvent une lecture fautive de l'écriture."
        ),
        "",
        ENTETE,
        "|---|---|---|---|---|---|---|---|",
        _ligne(m, COMPLETE, derniere),
        *(_ligne(m, f"règles + modèle + {v} + zones", derniere) for v in VARIANTES),
    ]
    source = COMPLETE
    lignes += [
        "",
        f"## Détail : {source}",
        "",
        "| donnée encadrée | nombre | couvertes |",
        "|---|---|---|",
        *(
            f"| {e} | {c['donnees']} | {pourcent(c['couvertes'], c['donnees'])} |"
            for e, c in sorted(m[source, derniere]["rappel"].items())
        ),
    ]
    return "\n".join(lignes)


def reperes_de_la_page(
    mots: list[tuple],
    gris: np.ndarray,
    commune: str,
    prenoms: set[str],
    imprime,
    passages: list,
) -> list[dict]:
    """Les repérages d'une page par chaque source : règles, encre sans texte
    et ses variantes, modèle (`passages` : ses réponses sur le texte de la
    page). Sans les zones, qui demandent les contributions délimitées."""
    reperes = [
        r | {"texte": texte_du_cadre(mots, r), "source": "règles"}
        for r in mots_personnels(mots, commune, frozenset(prenoms))
    ]
    reperes += [
        r | {"etiquette": "écriture", "texte": "", "source": "encre"}
        for r in encre_sans_texte(gris, mots)
    ]
    for nom, reglage in VARIANTES.items():
        reglage = dict(reglage)
        if reglage.pop("sous_ocr", False):
            reglage["imprime"] = imprime
        reperes += [
            r | {"etiquette": "écriture", "texte": "", "source": nom}
            for r in encre_sans_texte(gris, mots, **reglage)
        ]
    reperes += [
        r | {"texte": texte_du_cadre(mots, r), "source": "modèle"}
        for r in localiser(passages, mots)
    ]
    return reperes


def references(
    args: argparse.Namespace, fichiers: set[str]
) -> tuple[set[str], set[str], dict, dict[str, str]]:
    """Les prénoms de l'INSEE, les formes du lexique, les noms publics de
    chaque cahier et le nom de chaque commune (`args.cache`, `args.communes`)."""
    prenoms = charger_prenoms(sources.telecharger(PRENOMS, args.cache))
    lexique = {
        _simple(ligne.split("\t", 1)[0])
        for ligne in sources.telecharger(LEXIQUE, args.cache).decode().splitlines()[1:]
    }
    maires = charger_maires(sources.telecharger(MAIRES, args.cache))
    cog = {
        c["com"]: (c["libelle"], c["nccenr"])
        for c in sources.premier_csv_zip(sources.telecharger(COMMUNES, args.cache))
    }
    with args.communes.open(encoding="utf-8", newline="") as f:
        nom_commune = {
            c["code_insee"]: c["nom_2019"] or c["commune"] for c in csv.DictReader(f)
        }
    noms = {}
    for f in fichiers:
        code = code_insee(f) or ""
        maire = (maires[code],) if code in maires else ()
        noms[f] = publics(PERSONNALITES + maire, cog.get(code, ()), prenoms)
    return prenoms, lexique, noms, nom_commune


def modele_et_cache(args: argparse.Namespace) -> tuple[Paresseux, str, Cache]:
    """Le modèle (`args.modele`), chargé à la demande, son nom et le cache de
    ses réponses dans `args.modeles`."""
    nom_modele = (
        "gliner:urchade/gliner_multi_pii-v1" if args.modele == "gliner" else args.modele
    )
    cache = Cache(args.modeles / f"{re.sub(r'[^\w.-]', '_', nom_modele)}.jsonl")
    return Paresseux(args.modele), nom_modele, cache


def charger_pages(args: argparse.Namespace) -> tuple[dict, dict, str, set[str]]:
    """Les pages mesurées (mots, repérages, données encadrées), les noms
    publics de chaque cahier, le nom du modèle et les formes du lexique."""

    with args.delimitation.open(encoding="utf-8", newline="") as f:
        contributions = list(csv.DictReader(f))
    fichiers = {c["fichier"] for c in contributions}
    chemins = {p.name: p for p in args.versement.rglob("*.pdf") if p.name in fichiers}
    carnet = Carnet(args.annotation / "notes.jsonl")
    vues = {cle for cle, s in carnet.statuts(TACHE).items() if s == "vue"}
    relues = {
        cle for cle, s in carnet.statuts(RELECTURE, exacte=True).items() if s == "vue"
    }
    lues = {
        f: [n for n in numeros if (f, n) in vues]
        for f, numeros in pages_lues(args.typage, fichiers).items()
    }
    notes = defaultdict(list)
    for n in carnet.positions():
        if n["etiquette"] in A_CACHER:
            notes[n["fichier"], n["page"]].append(
                {**n, **dict(zip(CHAMPS, _ordonner(n), strict=True))}
            )
    with args.reperes.open(encoding="utf-8", newline="") as f:
        anciens = defaultdict(list)
        for r in csv.DictReader(f):
            cle = (r["fichier"], int(r["page"]))
            if cle in relues:
                anciens[cle].append(
                    {**r, "page": int(r["page"]), **{k: float(r[k]) for k in CHAMPS}}
                )
    retablis = defaultdict(list)
    for r in carnet.retablis().values():
        retablis[r["fichier"], r["page"]].append(r)

    prenoms, lexique, noms, nom_commune = references(args, fichiers)

    def imprime(texte: str) -> bool:
        return _simple(texte) in lexique

    modele, nom_modele, cache = modele_et_cache(args)
    par_fichier = defaultdict(list)
    for c in contributions:
        par_fichier[c["fichier"]].append(c)
    pages = {}
    for fichier in sorted(lues):
        if not lues[fichier]:
            continue
        commune = nom_commune.get(code_insee(fichier) or "", "")
        with pymupdf.open(chemins[fichier]) as doc:
            debuts = []
            for c in par_fichier[fichier]:
                page_debut, page_fin = int(c["page_debut"]), int(c["page_fin"])
                debut = pymupdf.Point(float(c["x_debut"]), float(c["y_debut"]))
                debut = debut * doc[page_debut - 1].rotation_matrix
                fin_y = (
                    (
                        pymupdf.Point(float(c["x_fin"]), float(c["y_fin"]))
                        * doc[page_fin - 1].rotation_matrix
                    ).y
                    if c["y_fin"]
                    else float("inf")
                )
                debuts.append((page_debut, debut.y, page_fin, fin_y, int(c["rang"])))
            debuts.sort()
            lignes = {}
            for n in lues[fichier]:
                page = doc[n - 1]
                mots = mots_de_la_page(page)
                lignes[n] = lignes_de_la_page(mots)
                gris = image_grise(page)
                reperes = reperes_de_la_page(
                    mots,
                    gris,
                    commune,
                    prenoms,
                    imprime,
                    cache.obtenir(fichier, n, modele, texte_de_la_page(mots)),
                )
                ref = (
                    reference(
                        anciens[fichier, n], retablis[fichier, n], notes[fichier, n]
                    )
                    if (fichier, n) in relues
                    else notes[fichier, n]
                )
                donnees = [
                    d
                    | {
                        "contribution": contribution_de(debuts, n, d["y0"]),
                        "encre": encre_de(gris, mots, d),
                    }
                    for d in ref
                ]
                pages[fichier, n] = {
                    "mots": mots,
                    "reperes": reperes,
                    "donnees": donnees,
                }
            for r in reperes_de_zones(lignes, debuts):
                pages[fichier, r["page"]]["reperes"].append(r)
        print(f"{fichier} : {len(lues[fichier])} pages", flush=True)

    return pages, noms, nom_modele, lexique


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--delimitation", type=Path, default=Path("data/delimitation/contributions.csv")
    )
    parser.add_argument("--versement", type=Path, default=Path("data/versement"))
    parser.add_argument(
        "--typage", type=Path, nargs="+", default=[Path("data/typage/departements")]
    )
    parser.add_argument("--annotation", type=Path, default=Path("data/annotation"))
    parser.add_argument(
        "--reperes", type=Path, default=Path("data/anonymisation/reperes.csv")
    )
    parser.add_argument(
        "--communes", type=Path, default=Path("data/communes/communes.csv")
    )
    parser.add_argument("--cache", type=Path, default=Path("data/sources"))
    parser.add_argument(
        "--modeles", type=Path, default=Path("data/anonymisation/modeles")
    )
    parser.add_argument("--modele", default="gliner")
    parser.add_argument(
        "--sortie", type=Path, default=Path("data/anonymisation/delimites")
    )
    args = parser.parse_args()
    pages, noms, nom_modele, lexique = charger_pages(args)
    textes = [{"insee": f, "reperes": p["reperes"]} for (f, _), p in pages.items()]
    repandus_ = repandus(textes)
    m = mesurer(pages, noms, repandus_, lexique)
    texte = rapport(
        m,
        len(pages),
        len({f for f, _ in pages}),
        sum(len(p["donnees"]) for p in pages.values()),
        nom_modele,
    )
    args.sortie.mkdir(parents=True, exist_ok=True)
    (args.sortie / "mesure.md").write_text(texte + "\n", encoding="utf-8")
    with (args.sortie / "visibles.csv").open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, ["fichier", "page", *CHAMPS, "etiquette"])
        ecrivain.writeheader()
        visibles_ = visibles(pages, noms, repandus_)
        ecrivain.writerows(visibles_)
    ecrire_liste(args.annotation / "listes", visibles_)
    print(texte)


if __name__ == "__main__":
    main()
