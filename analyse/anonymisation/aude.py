"""Le repérage mesuré sur l'étalon de l'Aude, manuscrits compris (#128).

    uv run --group modeles python -m anonymisation.aude
        [--etalon data/aude] [--versement data/versement]
        [--communes data/communes/communes.csv] [--cache data/sources]
        [--modeles data/anonymisation/modeles] [--modele gliner]
        [--sortie data/anonymisation/aude]

La chaîne de `anonymisation.delimites` (règles, modèle, encre sans texte et
ses variantes, filtres), cette fois sur les pages BnF de l'étalon de l'Aude
(`aude.etalon`) : dactylographiées et manuscrites. La référence est ce que
les Archives départementales ont caché sous un rectangle gris ; une page
sans masque compte aussi. Un masque est couvert comme une donnée encadrée
de `delimites` : tous les mots de la couche texte qu'il contient (sur un
manuscrit, une lecture fautive de l'OCR) et 80 % de son encre hors mots.

Pas de zones de signature : elles demandent les contributions délimitées.
Ce que les Archives ont retiré par découpe ne laisse pas de rectangle : le
rappel est un peu surestimé, et la précision (« touchent un masque ») n'est
qu'un minorant. Seuls comptent les masques au report sûr (accord d'au moins
ACCORD_SUR, ou entourage blanc) : une page où un masque est douteux est
écartée, comme une page publiée deux fois n'est comptée qu'une fois.

Le coût se mesure aussi en encre : la part de l'encre hors masques que la
chaîne cache, seule mesure qui ait un sens sur un manuscrit, dont la couche
texte ne dit rien.

Écrit dans la sortie `mesure.md`. Des comptes, jamais de texte.
"""

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pymupdf

from anonymisation.__main__ import image_grise, mots_de_la_page
from anonymisation.delimites import (
    COMPLETE,
    DEDANS,
    FILTRAGE,
    VARIANTES,
    encre_de,
    gardes_de,
    mesurer,
    modele_et_cache,
    references,
    reperes_de_la_page,
)
from anonymisation.detection import _simple
from anonymisation.factices import ETAPES, pourcent, repandus
from anonymisation.masquage import CHAMPS, dans
from anonymisation.modeles import texte_de_la_page
from panel.panel import code_insee

TYPES = ("dactylographiée", "manuscrite")
# accord au-delà duquel un masque reporté est sûr, comme dans `aude.etalon`
# (qu'on n'importe pas : il demande OpenCV)
ACCORD_SUR = 0.5
SANS_ZONES = COMPLETE.removesuffix(" + zones")
SOURCES = {
    "modèle": {"modèle"},
    "règles": {"règles"},
    "règles + modèle": {"règles", "modèle"},
    SANS_ZONES: {"règles", "modèle", "encre"},
    **{f"règles + modèle + {v}": {"règles", "modèle", v} for v in VARIANTES},
}


def sur(masque: dict) -> bool:
    """Le report du masque sur la page BnF est-il sûr ?"""
    return not masque["accord"] or float(masque["accord"]) >= ACCORD_SUR


def charger_etalon(dossier: Path) -> tuple[dict, int]:
    """Les pages de l'étalon : type et masques au report sûr, par (fichier,
    page BnF) ; et le nombre de pages écartées pour un masque douteux."""
    with (dossier / "pages_etalon.csv").open(encoding="utf-8", newline="") as f:
        pages = {
            (p["fichier"], int(p["page_bnf"])): {"type": p["type_page"], "masques": []}
            for p in csv.DictReader(f)
            if p["a_verifier"] == "0" and p["type_page"] in TYPES
        }
    douteuses = set()
    with (dossier / "etalon.csv").open(encoding="utf-8", newline="") as f:
        for m in csv.DictReader(f):
            cle = (m["fichier"], int(m["page_bnf"]))
            if cle not in pages:
                continue
            if not sur(m):
                douteuses.add(cle)
                continue
            cadre = {k: float(m[k]) for k in CHAMPS}
            # une page publiée deux fois donne deux fois ses masques
            if not any(dans(cadre, autre) >= DEDANS for autre in pages[cle]["masques"]):
                pages[cle]["masques"].append(cadre)
    for cle in douteuses:
        del pages[cle]
    return pages, len(douteuses)


def encre_cachee(p: dict, gardes: list[dict]) -> tuple[int, int]:
    """L'encre de la page hors masques, et la part que les repérages gardés
    cachent : (pixels cachés, pixels)."""
    encre = p["gris"] < 128
    hors = encre.copy()
    for d in p["donnees"]:
        x0, y0, x1, y1 = (max(0, int(d[k])) for k in CHAMPS)
        hors[y0 : y1 + 1, x0 : x1 + 1] = False
    cache = np.zeros_like(hors)
    for g in gardes:
        x0, y0, x1, y1 = (max(0, int(g[k])) for k in CHAMPS)
        cache[y0 : y1 + 1, x0 : x1 + 1] = True
    return int((hors & cache).sum()), int(hors.sum())


def cout_en_encre(pages: dict, noms: dict, repandus_: set[str]) -> dict:
    """Par source et étape : la part de l'encre hors masques cachée."""
    sortie = {}
    for source, gardees in SOURCES.items():
        etapes = range(len(ETAPES)) if source in FILTRAGE else [len(ETAPES) - 1]
        for etape in etapes:
            caches = total = 0
            for (fichier, _), p in pages.items():
                gardes = gardes_de(p, gardees, etape, noms[fichier], repandus_)
                c, t = encre_cachee(p, gardes)
                caches, total = caches + c, total + t
            sortie[source, etape] = (caches, total)
    return sortie


ENTETE = (
    "| source | étape | repérages | touchent un masque | masques couverts "
    "| pages où un masque reste visible | mots hors masques cachés "
    "| encre hors masques cachée |"
)


def _ligne(m: dict, encre: dict, source: str, etape: int) -> str:
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
        f"| {pourcent(*encre[source, etape])} |"
    )


def rapport(
    mesures: dict, pages: dict, cahiers: int, douteuses: int, modele: str
) -> str:
    derniere = len(ETAPES) - 1
    lignes = [
        "# Repérage sur l'étalon de l'Aude",
        "",
        (
            f"{len(pages)} pages BnF de {cahiers} cahiers, rapprochées des pages "
            "publiées anonymisées par le CESE de l'Aude (`aude.etalon`) ; "
            f"{douteuses} pages écartées pour un masque au report douteux. "
            f"Modèle : {modele}."
        ),
        "",
        (
            "La référence est ce que les Archives ont caché sous un rectangle "
            "gris : le rappel est un peu surestimé (les découpes manquent), la "
            "précision (« touchent un masque ») n'est qu'un minorant. Pas de "
            "zones de signature, faute de contributions délimitées. Étapes de "
            "filtrage : celles de `anonymisation.factices`."
        ),
    ]
    for type_page in TYPES:
        de_ce_type = [p for p in pages.values() if p["type"] == type_page]
        m, encre = mesures[type_page]
        lignes += [
            "",
            f"## Pages {type_page}s",
            "",
            (
                f"{len(de_ce_type)} pages, "
                f"{sum(len(p['donnees']) for p in de_ce_type)} masques sur "
                f"{sum(bool(p['donnees']) for p in de_ce_type)} pages."
            ),
            "",
            ENTETE,
            "|---|---|---|---|---|---|---|---|",
            *(_ligne(m, encre, s, e) for s in FILTRAGE for e in range(len(ETAPES))),
            *(_ligne(m, encre, s, derniere) for s in SOURCES if s not in FILTRAGE),
        ]
    return "\n".join(lignes)


def charger_pages(args: argparse.Namespace) -> tuple[dict, dict, str, int]:
    """Les pages mesurées (mots, image, repérages, masques), les noms publics
    de chaque cahier, le nom du modèle et le nombre de pages écartées."""
    etalon, douteuses = charger_etalon(args.etalon)
    fichiers = {f for f, _ in etalon}
    chemins = {p.name: p for p in args.versement.rglob("*.pdf") if p.name in fichiers}
    prenoms, lexique, noms, nom_commune = references(args, fichiers)

    def imprime(texte: str) -> bool:
        return _simple(texte) in lexique

    modele, nom_modele, cache = modele_et_cache(args)
    par_fichier = defaultdict(list)
    for fichier, n in etalon:
        par_fichier[fichier].append(n)
    pages = {}
    for fichier, numeros in sorted(par_fichier.items()):
        commune = nom_commune.get(code_insee(fichier) or "", "")
        with pymupdf.open(chemins[fichier]) as doc:
            for n in sorted(numeros):
                page = doc[n - 1]
                mots = mots_de_la_page(page)
                gris = image_grise(page)
                passages = cache.obtenir(fichier, n, modele, texte_de_la_page(mots))
                donnees = [
                    m
                    | {
                        "etiquette": "masque",
                        # l'unité est la page : pas de contributions délimitées
                        "contribution": n,
                        "encre": encre_de(gris, mots, m),
                    }
                    for m in etalon[fichier, n]["masques"]
                ]
                pages[fichier, n] = {
                    "type": etalon[fichier, n]["type"],
                    "mots": mots,
                    "gris": gris,
                    "reperes": reperes_de_la_page(
                        mots, gris, commune, prenoms, imprime, passages
                    ),
                    "donnees": donnees,
                }
        print(f"{fichier} : {len(numeros)} pages", flush=True)
    return pages, noms, nom_modele, douteuses


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--etalon", type=Path, default=Path("data/aude"))
    parser.add_argument("--versement", type=Path, default=Path("data/versement"))
    parser.add_argument(
        "--communes", type=Path, default=Path("data/communes/communes.csv")
    )
    parser.add_argument("--cache", type=Path, default=Path("data/sources"))
    parser.add_argument(
        "--modeles", type=Path, default=Path("data/anonymisation/modeles")
    )
    parser.add_argument("--modele", default="gliner")
    parser.add_argument("--sortie", type=Path, default=Path("data/anonymisation/aude"))
    args = parser.parse_args()
    pages, noms, nom_modele, douteuses = charger_pages(args)
    textes = [{"insee": f, "reperes": p["reperes"]} for (f, _), p in pages.items()]
    repandus_ = repandus(textes)
    mesures = {}
    for type_page in TYPES:
        de_ce_type = {k: p for k, p in pages.items() if p["type"] == type_page}
        mesures[type_page] = (
            mesurer(de_ce_type, noms, repandus_, sources=SOURCES),
            cout_en_encre(de_ce_type, noms, repandus_),
        )
    texte = rapport(mesures, pages, len({f for f, _ in pages}), douteuses, nom_modele)
    args.sortie.mkdir(parents=True, exist_ok=True)
    (args.sortie / "mesure.md").write_text(texte + "\n", encoding="utf-8")
    print(texte)


if __name__ == "__main__":
    main()
