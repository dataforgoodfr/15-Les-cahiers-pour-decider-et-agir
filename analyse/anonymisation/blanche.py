"""Une liste blanche du texte, mesurée sur les cahiers délimités (#128).

    uv run --group modeles python -m anonymisation.blanche
        [mêmes options que `anonymisation.delimites`]
        [--sortie data/anonymisation/blanche]

Au lieu de repérer les données personnelles, on ne garde que les mots sûrs :
ceux du lexique courant (Lexique 3.83), les lieux (France, régions,
départements, commune du cahier) et les noms publics du cahier
(`anonymisation.publics`). Tout autre mot de la couche texte est caché, si
bien qu'une lecture fautive de l'OCR est cachée au lieu de fuir. Un prénom
de l'INSEE à majuscule est caché, même s'il est dans le lexique (« Pierre »).

La liste blanche est mesurée seule, puis avec l'encre sans texte (l'écriture
à la main), les zones de signature, et les règles et le modèle de
`anonymisation.delimites`, sur les mêmes pages et la même référence.

Mesuré aussi pour une publication du texte seul, sans les images : une
donnée n'y fuit que par les mots de la couche texte qu'elle contient, son
écriture à la main n'étant pas publiée (sauf lue par l'OCR, en mots
souvent hors du lexique).

Pour les blocs de coordonnées des formulaires, où fuit l'essentiel : les
zones apprises (`detection.modele_appris`) sur les données encadrées
d'autres pages du même cahier, reportées sur la page mesurée. Deux
simulations : un relecteur encadre les deux pages à données les plus
proches, ou toutes les autres (la borne haute).

Écrit dans la sortie `mesure.md` : données encadrées couvertes, et part du
texte hors données qui est perdue, par raison du masquage. Des comptes,
jamais de texte.
"""

import argparse
import re
from collections import Counter, defaultdict
from pathlib import Path

import pymupdf

from anonymisation import delimites
from anonymisation.__main__ import PRENOMS, lignes_placees
from anonymisation.delimites import (
    DEDANS,
    ETAPES,
    _cadre,
    _ligne,
    charger_pages,
    gabarit,
    gardes_de,
    mesurer,
)
from anonymisation.detection import (
    EXEMPLAIRES,
    _simple,
    charger_prenoms,
    modele_appris,
)
from anonymisation.factices import pourcent, repandus
from anonymisation.masquage import dans
from anonymisation.publics import Publics, _jetons
from corpus.communes import sources

LIEUX = ("France", "Europe")
FIN_DE_PHRASE = re.compile(r"[.!?…]$")
BARRE = re.compile(r"[a-zà-ÿœæ]+/[a-zà-ÿœæ]+")
BLANCHE = "liste blanche"
TOUTES = "encre pâle, raturée, sous OCR"
SOURCES = {
    BLANCHE: {BLANCHE},
    f"{BLANCHE} + encre": {BLANCHE, "encre"},
    f"{BLANCHE} + encre + zones": {BLANCHE, "encre", "zones"},
    f"{BLANCHE} + {TOUTES} + zones": {BLANCHE, TOUTES, "zones"},
    f"règles + modèle + {BLANCHE} + {TOUTES} + zones": {
        "règles",
        "modèle",
        BLANCHE,
        TOUTES,
        "zones",
    },
}
TEXTE_SEUL = {
    "règles + modèle": {"règles", "modèle"},
    "règles + modèle + zones": {"règles", "modèle", "zones"},
    BLANCHE: {BLANCHE},
    f"{BLANCHE} + zones": {BLANCHE, "zones"},
    f"règles + {BLANCHE} + zones": {"règles", BLANCHE, "zones"},
    f"règles + modèle + {BLANCHE} + zones": {"règles", "modèle", BLANCHE, "zones"},
}
MEILLEURE = "règles + modèle + liste blanche + zones"
FORMULAIRES = {"formulaire, 2 pages voisines": EXEMPLAIRES, "formulaire, toutes": None}
for _nom in FORMULAIRES:
    TEXTE_SEUL[f"{MEILLEURE} + {_nom}"] = TEXTE_SEUL[MEILLEURE] | {_nom}


def lieux(cache: Path) -> set[str]:
    """Formes simplifiées des noms de la France, des régions et des
    départements, en un mot (« seinemaritime »)."""
    noms = list(LIEUX)
    for url in (sources.COG_REGIONS, sources.COG_DEPARTEMENTS):
        noms += [
            c["libelle"]
            for c in sources.premier_csv_zip(sources.telecharger(url, cache))
        ]
    return {"".join(_jetons(n)) for n in noms}


def debuts_de_phrase(mots: list[tuple]) -> set[int]:
    """Les rangs, dans `mots`, des mots qui ouvrent un bloc ou suivent une
    fin de phrase."""
    ordre = sorted(range(len(mots)), key=lambda i: mots[i][5:8])
    debuts, avant = set(), None
    for i in ordre:
        if (
            avant is None
            or mots[avant][5] != mots[i][5]
            or FIN_DE_PHRASE.search(mots[avant][4])
        ):
            debuts.add(i)
        avant = i
    return debuts


def raison(texte: str, admis: set[str], prenoms: set[str], noms: Publics) -> str | None:
    """Pourquoi un mot est caché, ou None s'il est sûr. `noms` : noms publics
    et lieux ; `admis` : le lexique."""
    jetons = _jetons(texte)
    if not jetons or "".join(jetons) in noms.seuls:
        return None
    majuscule = texte[:1].isupper()
    if majuscule and any(j in prenoms for j in jetons):
        return "prénom"
    if all(j in admis for j in jetons):
        return None
    # en minuscules seulement : « aujourd'hui » et « start-up », un seul mot
    # du lexique ; « et/ou » et « km/h », deux mots ; « œuvre », que Lexique
    # écrit « oeuvre »
    if texte.islower():
        lie = texte.replace("œ", "oe").replace("æ", "ae")
        if (
            "".join(jetons) in admis
            or all(j in admis for j in _jetons(lie))
            or (
                BARRE.fullmatch(lie)
                and all(_simple(j) in admis for j in lie.split("/"))
            )
        ):
            return None
    if any(c.isdigit() for c in texte):
        return "nombre"
    return "majuscule hors liste" if majuscule else "minuscule hors liste"


def reperes_blancs(
    mots: list[tuple],
    admis: set[str],
    prenoms: set[str],
    noms: Publics,
) -> list[dict]:
    """Un repérage par mot de la couche texte hors de la liste blanche."""
    sortie = []
    for m in mots:
        r = raison(m[4], admis, prenoms, noms)
        if r is not None:
            sortie.append(
                _cadre(m)
                | {"etiquette": "mot", "texte": "", "raison": r, "source": BLANCHE}
            )
    return sortie


def formulaires(
    pages: dict, lignes: dict[str, dict], voisines: int | None, source: str
) -> dict[tuple, list[dict]]:
    """Pour chaque page, les zones apprises sur les données encadrées des
    autres pages du cahier : les `voisines` plus proches, ou toutes (None).
    `lignes` : par cahier, les lignes placées de chaque page."""
    annotees = defaultdict(dict)
    for (fichier, n), p in pages.items():
        if p["donnees"]:
            annotees[fichier][n] = [d | {"page": n} for d in p["donnees"]]
    appris, sortie = {}, defaultdict(list)
    for fichier, n in pages:
        autres = sorted(m for m in annotees[fichier] if m != n)
        if voisines is not None:
            autres = sorted(sorted(autres, key=lambda m: (abs(m - n), m))[:voisines])
        if len(autres) < EXEMPLAIRES:
            continue
        cle = (fichier, tuple(autres))
        if cle not in appris:
            notes = [d for m in autres for d in annotees[fichier][m]]
            appris[cle] = modele_appris(lignes[fichier], notes)
        sortie[fichier, n] = [
            {k: z[k] for k in ("x0", "y0", "x1", "y1")}
            | {"etiquette": "formulaire", "texte": "", "source": source}
            for z in appris[cle]
            if z["page"] == n
        ]
    return sortie


def texte_seul(pages: dict) -> dict:
    """Les pages, sans l'encre de leurs données : publiée en texte, une donnée
    ne fuit que par ses mots de la couche texte."""
    return {
        cle: p | {"donnees": [{**d, "encre": None} for d in p["donnees"]]}
        for cle, p in pages.items()
    }


def hors_du_texte(pages: dict) -> int:
    """Les données sans aucun mot de la couche texte (hors ponctuation et
    gabarit) : absentes d'une publication du texte seul."""
    imprimes = gabarit(pages)
    return sum(
        not any(
            dans(_cadre(m), d) >= DEDANS
            and _simple(m[4])
            and _simple(m[4]) not in imprimes[fichier]
            for m in p["mots"]
        )
        for (fichier, _), p in pages.items()
        for d in p["donnees"]
    )


def fuites(
    pages: dict, gardees: set[str], noms: dict, surs: dict, repandus_: set[str]
) -> dict:
    """Les mots des données que la chaîne `gardees` laisse visibles, par
    sorte (nombre, nom public ou lieu de `surs`, majuscule, minuscule), et
    les données qui fuient, par étiquette."""
    imprimes = gabarit(pages)
    mots, donnees = Counter(), Counter()
    for (fichier, _), p in pages.items():
        gardes = gardes_de(p, gardees, len(ETAPES) - 1, noms[fichier], repandus_)
        debuts = debuts_de_phrase(p["mots"])
        for d in p["donnees"]:
            visibles = [
                (i, m)
                for i, m in enumerate(p["mots"])
                if dans(_cadre(m), d) >= DEDANS
                and _simple(m[4])
                and _simple(m[4]) not in imprimes[fichier]
                and not any(dans(_cadre(m), g) >= DEDANS for g in gardes)
            ]
            donnees[d["etiquette"]] += bool(visibles)
            for i, m in visibles:
                if any(c.isdigit() for c in m[4]):
                    mots["nombre"] += 1
                elif "".join(_jetons(m[4])) in surs[fichier].seuls:
                    mots["nom public ou lieu"] += 1
                elif m[4][:1].isupper():
                    mots[
                        "majuscule en début de phrase"
                        if i in debuts
                        else "majuscule dans la phrase"
                    ] += 1
                else:
                    mots["minuscule"] += 1
    return {"mots": mots, "donnees": donnees}


def raisons(pages: dict) -> Counter:
    """Les mots hors données cachés par la liste blanche, par raison."""
    compte = Counter()
    for p in pages.values():
        for r in p["reperes"]:
            if r["source"] == BLANCHE and not any(
                dans(r, d) >= DEDANS for d in p["donnees"]
            ):
                compte[r["raison"]] += 1
    return compte


def rapport(m: dict, seul: dict, fuites_: dict, pages: dict, mots: int) -> str:
    derniere = len(ETAPES) - 1
    donnees = sum(len(p["donnees"]) for p in pages.values())
    lignes = [
        "# Liste blanche sur les cahiers délimités à la main",
        "",
        (
            f"{len(pages)} pages dactylographiées ou mixtes vues à la délimitation, dans "
            f"{len({f for f, _ in pages})} cahiers : {donnees} données "
            f"personnelles ou signatures encadrées à la main, {mots} mots dans "
            "la couche texte."
        ),
        "",
        (
            "Liste blanche : Lexique 3.83, France, Europe, régions, départements, "
            "noms publics du cahier (commune, maire, présidents, ministres). Un "
            "prénom de l'INSEE à majuscule est caché. Encre, zones, règles et modèle : ceux de "
            "`anonymisation.delimites`."
        ),
        "",
        delimites.ENTETE,
        "|---|---|---|---|---|---|---|---|",
        _ligne(m, "règles + modèle + encre + zones", derniere),
        *(_ligne(m, s, derniere) for s in SOURCES),
        "",
        "## Texte seul",
        "",
        (
            f"Publiée en texte, sans les images. {hors_du_texte(pages)} données "
            "n'ont aucun mot dans la couche texte (écriture à la main que l'OCR "
            "n'a pas lue) : elles sont couvertes d'office."
        ),
        "",
        delimites.ENTETE,
        "|---|---|---|---|---|---|---|---|",
        *(_ligne(seul, s, derniere) for s in TEXTE_SEUL),
    ]
    for source, f in fuites_.items():
        total = sum(f["mots"].values())
        lignes += [
            "",
            f"## Ce qui fuit, texte seul : {source}",
            "",
            "| mot visible dans une donnée | mots | part |",
            "|---|---|---|",
            *(
                f"| {k} | {n} | {pourcent(n, total)} |"
                for k, n in f["mots"].most_common()
            ),
            "",
            "| donnée qui fuit | nombre |",
            "|---|---|",
            *(f"| {k} | {n} |" for k, n in f["donnees"].most_common() if n),
        ]
    compte = raisons(pages)
    total = sum(compte.values())
    lignes += [
        "",
        "## Mots hors données cachés par la liste blanche",
        "",
        "| raison | mots | part des mots cachés |",
        "|---|---|---|",
        *(f"| {r} | {n} | {pourcent(n, total)} |" for r, n in compte.most_common()),
    ]
    return "\n".join(lignes)


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
        "--sortie", type=Path, default=Path("data/anonymisation/blanche")
    )
    args = parser.parse_args()
    pages, noms, _, lexique = charger_pages(args)
    prenoms = {
        _simple(p) for p in charger_prenoms(sources.telecharger(PRENOMS, args.cache))
    }
    lieux_ = lieux(args.cache)
    surs = {f: n._replace(seuls=n.seuls | lieux_) for f, n in noms.items()}
    for (fichier, _), p in pages.items():
        p["reperes"] += reperes_blancs(p["mots"], lexique, prenoms, surs[fichier])
    textes = [{"insee": f, "reperes": p["reperes"]} for (f, _), p in pages.items()]
    repandus_ = repandus(textes)
    m = mesurer(
        pages,
        noms,
        repandus_,
        lexique,
        {"règles + modèle + encre + zones": delimites.SOURCES[delimites.COMPLETE]}
        | SOURCES,
    )
    fichiers = {f for f, _ in pages}
    chemins = {p.name: p for p in args.versement.rglob("*.pdf") if p.name in fichiers}
    lignes = {}
    for fichier in sorted(fichiers):
        with pymupdf.open(chemins[fichier]) as doc:
            lignes[fichier] = {
                k + 1: lignes_placees(doc[k]) for k in range(doc.page_count)
            }
    for nom, voisines in FORMULAIRES.items():
        for cle, zones_ in formulaires(pages, lignes, voisines, nom).items():
            pages[cle]["reperes"] += zones_
    sans_encre = texte_seul(pages)
    seul = mesurer(sans_encre, noms, repandus_, lexique, TEXTE_SEUL)
    fuites_ = {
        s: fuites(sans_encre, TEXTE_SEUL[s], noms, surs, repandus_)
        for s in (MEILLEURE, *(f"{MEILLEURE} + {n}" for n in FORMULAIRES))
    }
    texte = rapport(
        m, seul, fuites_, pages, sum(len(p["mots"]) for p in pages.values())
    )
    args.sortie.mkdir(parents=True, exist_ok=True)
    (args.sortie / "mesure.md").write_text(texte + "\n", encoding="utf-8")
    print(texte)


if __name__ == "__main__":
    main()
