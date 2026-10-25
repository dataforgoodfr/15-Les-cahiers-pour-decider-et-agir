"""Anomalies de l'OCR du versement, page par page, sur tout le corpus (issue #12).

    uv run python -m ocr.anomalies [--typage data/typage/departements]
        [--versement data/versement] [--cache data/sources]
        [--chabin data/ocr/chabin.csv] [--processus 8] [--sortie data/ocr]

La mesure sur l'édition Chabin (`ocr.chabin`) donne le taux d'erreur d'un
seul département. Pour trouver des problèmes qu'on ne connaît pas encore,
on recense sur chaque page dactylographiée (typage, hors pages de service)
des signaux qui ne demandent pas de référence :

- `encre_hors_mots` : part de l'encre (pixels sombres, un par point) que ne
  couvre aucun mot de la couche texte : ce que l'OCR n'a pas lu (zone
  oubliée, impression pâle, tableau), ou de l'écriture à la main ;
- `mots_sans_encre` : part des mots dont le cadre est presque blanc, même
  à un gris clair (une impression pâle n'y compte pas) : une
  couche texte décalée de l'image, qui fausserait les positions dont se
  servent l'anonymisation et le découpage ;
- `retours` : part des lignes qui remontent sur la page sans passer dans
  une colonne à droite : un ordre de lecture brouillé ;
- `hors_lexique` : part des mots alphabétiques d'au moins trois lettres
  absents de Lexique 3.83 (noms propres compris : le niveau compte moins
  que les écarts) ;
- `mal_encodes` : mots où paraît un caractère mal décodé (« Ã© », « â€ ») ;
- `chiffres_lettres` : part des mots qui mêlent chiffres et lettres hors
  ordinaux (« d0rt », « l1berté »).

Écrit `anomalies.csv` (une ligne par page) et `anomalies.md` : les signaux
par département, et leur lien avec le taux d'erreur mesuré sur l'édition
Chabin, s'il existe. Des nombres, jamais de texte.
"""

import argparse
import csv
import re
from collections import defaultdict
from itertools import pairwise
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pymupdf

from corpus.communes import sources

LEXIQUE = "https://www.lexique.org/databases/Lexique383/Lexique383.tsv"
_DEPARTEMENT = re.compile(r"GDN_(\w+?)_PDF")
SOMBRE = 128  # niveau de gris en deçà duquel un pixel est de l'encre
# pour juger qu'un mot est posé sur du blanc : un gris plus clair, sans quoi
# une impression pâle passe pour une couche texte décalée (sur 150 pages
# signalées au seuil de 128, presque toutes l'étaient)
PALE = 200
MARGE_MOT = 2  # points autour d'un mot qui comptent comme lus
ENCRE_MOT = 0.03  # part de pixels sombres en deçà de laquelle un mot est sans encre
REMONTEE = 20  # points dont une ligne doit remonter pour un retour en arrière
ALPHA = re.compile(r"^[a-zà-öø-ÿœæ'-]{3,}$", re.IGNORECASE)
MAL_ENCODE = re.compile(r"Ã[\x80-\xbf©¨ª«®´¹¼½§ ]|â€|Â[ «»°]")
ORDINAL = re.compile(r"^\d+(er|re|e|ème|eme|è|ère|nd|nde|°)s?$", re.IGNORECASE)
CHIFFRES_LETTRES = re.compile(r"(?=.*\d)(?=.*[a-zà-ÿ])", re.IGNORECASE)
SIGNAUX = (
    "encre_hors_mots",
    "mots_sans_encre",
    "retours",
    "hors_lexique",
    "mal_encodes",
    "chiffres_lettres",
)

_lexique: set[str] = set()


def _simple(mot: str) -> str:
    return mot.lower().strip("'-")


def signaux(page: pymupdf.Page, lexique: set[str]) -> dict[str, float]:
    """Les signaux d'une page, dans le repère de la page affichée."""
    pix = page.get_pixmap(dpi=72, colorspace=pymupdf.csGRAY)
    gris = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
    encre, trace = gris < SOMBRE, gris < PALE
    lus = np.zeros_like(encre)
    mots, sans_encre = [], 0
    for x0, y0, x1, y1, texte, *_ in page.get_text("words"):
        r = pymupdf.Rect(x0, y0, x1, y1) * page.rotation_matrix
        a, b = max(0, int(r.x0)), max(0, int(r.y0))
        c, d = int(r.x1) + 1, int(r.y1) + 1
        lus[
            max(0, b - MARGE_MOT) : d + MARGE_MOT, max(0, a - MARGE_MOT) : c + MARGE_MOT
        ] = True
        zone = trace[b:d, a:c]
        if len(texte) >= 3 and zone.size and zone.mean() < ENCRE_MOT:
            sans_encre += 1
        mots.append(texte)

    lignes = [
        pymupdf.Rect(ligne["bbox"]) * page.rotation_matrix
        for bloc in page.get_text("dict")["blocks"]
        for ligne in bloc.get("lines", [])
    ]
    retours = sum(
        1
        for avant, apres in pairwise(lignes)
        if apres.y0 < avant.y0 - REMONTEE and apres.x0 <= avant.x1
    )
    alphabetiques = [m for m in mots if ALPHA.match(m)]
    longs = [m for m in mots if len(m) >= 3]
    return {
        "mots": len(mots),
        "encre_hors_mots": (encre & ~lus).sum() / max(encre.sum(), 1),
        "mots_sans_encre": sans_encre / max(len(longs), 1),
        "retours": retours / max(len(lignes) - 1, 1),
        "hors_lexique": sum(_simple(m) not in lexique for m in alphabetiques)
        / max(len(alphabetiques), 1),
        "mal_encodes": sum(bool(MAL_ENCODE.search(m)) for m in mots),
        "chiffres_lettres": sum(
            bool(CHIFFRES_LETTRES.match(m)) and not ORDINAL.match(m) for m in longs
        )
        / max(len(longs), 1),
    }


def _initialiser(lexique: set[str]) -> None:
    global _lexique
    _lexique = lexique


def _un_fichier(tache: tuple[str, str, list[int]]) -> list[dict]:
    chemin, departement, pages = tache
    sortie = []
    with pymupdf.open(chemin) as doc:
        for n in pages:
            sortie.append(
                {"fichier": Path(chemin).name, "departement": departement, "page": n}
                | {
                    k: round(float(v), 4)
                    for k, v in signaux(doc[n - 1], _lexique).items()
                }
            )
    return sortie


def pages_dactylographiees(typage: Path) -> dict[str, tuple[str, list[int]]]:
    """Par fichier : son département de versement et ses pages
    dactylographiées, hors pages de service."""
    sortie: dict[str, tuple[str, list[int]]] = {}
    for chemin in sorted(typage.glob("*.csv")):
        departement = _DEPARTEMENT.search(chemin.name).group(1)
        with chemin.open(encoding="utf-8", newline="") as f:
            for ligne in csv.DictReader(f):
                if (
                    ligne["type_page"] == "dactylographiée"
                    and ligne["page_de_service"] != "1"
                ):
                    sortie.setdefault(ligne["fichier"], (departement, []))[1].append(
                        int(ligne["page"])
                    )
    return sortie


def correlations(pages: list[dict], chabin: Path) -> list[str]:
    """Lien entre chaque signal de la page où commence une contribution de
    l'édition Chabin et le taux d'erreur de cette contribution (rang de
    Spearman)."""
    if not chabin.exists():
        return []
    signaux_page = {(p["fichier"], p["page"]): p for p in pages}
    couples = []
    with chabin.open(encoding="utf-8", newline="") as f:
        for c in csv.DictReader(f):
            p = signaux_page.get((c["fichier"], int(c["page"])))
            if p:
                couples.append((p, float(c["cer sans accents"])))
    if len(couples) < 10:
        return []

    def rangs(v):
        return np.argsort(np.argsort(v))

    cer = rangs(np.array([c for _, c in couples]))
    lignes = [
        "",
        "## Signaux et taux d'erreur sur l'édition Chabin",
        "",
        (
            f"{len(couples)} contributions dont la première page est lue : corrélation "
            "de rang (Spearman) entre le signal de cette page et le CER sans accents "
            "de la contribution."
        ),
        "",
        "| signal | corrélation |",
        "|---|---|",
    ]
    for s in SIGNAUX:
        v = rangs(np.array([p[s] for p, _ in couples]))
        r = np.corrcoef(v, cer)[0, 1] if v.std() else 0.0
        lignes.append(f"| {s} | {r:+.2f} |")
    return lignes


def rapport(pages: list[dict], chabin: Path) -> str:
    seuils = {
        "encre_hors_mots": 0.3,
        "mots_sans_encre": 0.2,
        "retours": 0.1,
        "hors_lexique": 0.5,
        "mal_encodes": 1,
        "chiffres_lettres": 0.1,
    }
    par_departement = defaultdict(list)
    for p in pages:
        par_departement[p["departement"]].append(p)
    entete = " | ".join(
        f"{s} ≥ {v:g}" if s == "mal_encodes" else f"{s} > {v:.0%}"
        for s, v in seuils.items()
    )
    lignes = [
        "# Anomalies de l'OCR du versement",
        "",
        (
            f"{len(pages)} pages dactylographiées de {len({p['fichier'] for p in pages})} "
            "fichiers. Médiane de chaque signal, et part des pages au-delà d'un seuil "
            "(à lire comme un repère, pas comme une limite de qualité)."
        ),
        "",
        "| département | pages | "
        + " | ".join(f"médiane {s}" for s in SIGNAUX)
        + " | "
        + entete
        + " |",
        "|---|---|" + "---|" * (2 * len(SIGNAUX)),
    ]
    for departement, groupe in [("tous", pages), *sorted(par_departement.items())]:
        medianes = " | ".join(
            f"{np.median([p[s] for p in groupe]):.2f}"
            if s == "mal_encodes"
            else f"{np.median([p[s] for p in groupe]):.0%}"
            for s in SIGNAUX
        )
        parts = " | ".join(
            f"{np.mean([p[s] >= v if s == 'mal_encodes' else p[s] > v for p in groupe]):.1%}"
            for s, v in seuils.items()
        )
        lignes.append(f"| {departement} | {len(groupe)} | {medianes} | {parts} |")
    return "\n".join(lignes + correlations(pages, chabin))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--typage", type=Path, default=Path("data/typage/departements"))
    parser.add_argument("--versement", type=Path, default=Path("data/versement"))
    parser.add_argument("--cache", type=Path, default=Path("data/sources"))
    parser.add_argument("--chabin", type=Path, default=Path("data/ocr/chabin.csv"))
    parser.add_argument("--processus", type=int, default=8)
    parser.add_argument("--sortie", type=Path, default=Path("data/ocr"))
    args = parser.parse_args()

    lexique = {
        _simple(ligne.split("\t", 1)[0])
        for ligne in sources.telecharger(LEXIQUE, args.cache).decode().splitlines()[1:]
    }
    a_lire = pages_dactylographiees(args.typage)
    chemins = {p.name: p for p in args.versement.rglob("*.pdf") if p.name in a_lire}
    taches = [
        (str(chemins[f]), departement, numeros)
        for f, (departement, numeros) in sorted(a_lire.items())
        if f in chemins
    ]
    pages = []
    with Pool(args.processus, _initialiser, (lexique,)) as pool:
        for k, resultat in enumerate(pool.imap_unordered(_un_fichier, taches), 1):
            pages += resultat
            if k % 1000 == 0:
                print(f"{k}/{len(taches)} fichiers", flush=True)
    args.sortie.mkdir(parents=True, exist_ok=True)
    with (args.sortie / "anomalies.csv").open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, list(pages[0]))
        ecrivain.writeheader()
        ecrivain.writerows(sorted(pages, key=lambda p: (p["fichier"], p["page"])))
    texte = rapport(pages, args.chabin)
    (args.sortie / "anomalies.md").write_text(texte + "\n", encoding="utf-8")
    print(texte)


if __name__ == "__main__":
    main()
