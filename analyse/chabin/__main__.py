"""Référence de découpage : les cahiers de l'édition Chabin, relus à la main.

    uv run python -m chabin
        [--extraction ../data/cahiers_chabin-extraction.json]
        [--versement data/versement] [--typage data/typage/departements]
        [--annotation data/annotation] [--sortie data/chabin]
        [--ouvertures data/ouvertures/ouvertures.csv]
        [--htr ../data/htr/manicule-2026]

L'extraction vient de `extraction/chabin` (échantillon ou édition complète).
Écrit la liste « chabin » de l'outil d'annotation : un élément par scan BnF
des cahiers extraits. Le lecteur y délimite toutes les contributions, puis
marque la dernière page vue, comme pour la sélection.

Retrouve aussi, dans l'OCR des scans, le début de chaque contribution
dactylographiée ou imprimée d'une messagerie, et celui de chaque manuscrit
dans la lecture HTR des pages manuscrites (`htr/`, si elle existe) :
`alignement.csv` dans la sortie, voir `chabin.alignement`. Mesure sur cette
référence les règles de découpage (`contributions.regles`) : précision et
rappel des débuts sur les pages dactylographiées. Mesure enfin le placement
des manuscrits sur les cahiers délimités à la main.

Compare enfin, pour chaque cahier délimité, ses débuts notés aux
contributions de l'édition (`comparaison.csv` dans la sortie). Des codes, des
noms de fichiers, des positions et des comptes, jamais de texte.
"""

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

import pymupdf

from annotation import listes
from annotation.carnet import Carnet
from annotation.corpus import Corpus
from chabin.alignement import IMPRIMEES, SEUIL_HTR, genre, localiser
from chabin.reference import cahiers, comparer, elements
from contributions.__main__ import lignes, pages_lues, premieres_ecrites
from contributions.regles import TOLERANCE, debuts, evaluer
from ouvertures.__main__ import lire as lire_ouvertures
from selection.contribution import delimites as cahiers_delimites

TACHE = "chabin"
DEBUT = "début de contribution"


def scans(e: dict) -> list[str]:
    return [Path(f).name for f in e["pdf_files"]]


def lecture_htr(dossier: Path | None, fichier: str) -> dict[int, list]:
    """Les lignes lues par `htr/` dans les pages d'un scan : numéro de page →
    [(texte, cadre)]. Vide si le scan n'a pas été lu."""
    chemin = dossier / f"{Path(fichier).stem}.jsonl" if dossier else None
    if not chemin or not chemin.exists():
        return {}
    sortie = {}
    with chemin.open(encoding="utf-8") as f:
        for ligne in f:
            page = json.loads(ligne)
            sortie[page["page"]] = [
                (x["texte"], pymupdf.Rect(x["cadre"])) for x in page["lignes"]
            ]
    return sortie


def aligner(
    extraction: list[dict | None], corpus: Corpus, htr: Path | None = None
) -> list[dict]:
    """Une ligne par contribution des cahiers dont tous les scans sont au
    versement : où elle commence, si on l'y retrouve. Une contribution
    imprimée se cherche dans l'OCR, un manuscrit dans la lecture HTR (dossier
    `htr`) ; sans lecture, il reste sans position."""
    sortie = []
    for e in extraction:
        if not e or not scans(e) or not all(f in corpus.chemins for f in scans(e)):
            continue
        ocr, manuscrit = [], []  # (fichier, page, ligne dans la page, texte, cadre)
        for f in scans(e):
            lues = lecture_htr(htr, f)
            with pymupdf.open(corpus.chemin(f)) as doc:
                for n, page in enumerate(doc, 1):
                    ocr += [
                        (f, n, i, texte, cadre)
                        for i, (texte, cadre) in enumerate(lignes(page))
                    ]
                    manuscrit += [
                        (f, n, i, texte, cadre)
                        for i, (texte, cadre) in enumerate(lues.get(n, []))
                    ]
        genres = [genre(c["title"]) for c in e["contributions"]]
        trouves = {}
        for source, positions, retenus, seuil in (
            ("ocr", ocr, [k for k, g in enumerate(genres) if g in IMPRIMEES], None),
            (
                "htr",
                manuscrit,
                [k for k, g in enumerate(genres) if g == "manuscrit"],
                SEUIL_HTR,
            ),
        ):
            if not positions:
                continue
            for k, t in zip(
                retenus,
                localiser(
                    [e["contributions"][k]["text"] for k in retenus],
                    [p[3] for p in positions],
                    [seuil] * len(retenus) if seuil else None,
                ),
            ):
                if t:
                    trouves[k] = (source, positions[t[0]], t[1])
        for k, g in enumerate(genres):
            ligne = {
                "insee": e["city"]["insee"],
                "rang": k + 1,
                "genre": g,
                "source": "",
                "fichier": "",
                "page": "",
                "ligne": "",
                "y0": "",
                "ressemblance": "",
            }
            if k in trouves:
                source, (f, n, i, _, cadre), ressemblance = trouves[k]
                ligne |= {
                    "source": source,
                    "fichier": f,
                    "page": n,
                    "ligne": i,
                    "y0": round(cadre.y0, 1),
                    "ressemblance": ressemblance,
                }
            sortie.append(ligne)
    return sortie


def mesurer_regles(
    alignement: list[dict],
    scans_par_cahier: dict[str, list[str]],
    corpus: Corpus,
    typage: Path,
    ouvertures: set[tuple[str, int]],
) -> list[tuple[str, str, float, float, int, int]]:
    """Précision et rappel des règles sur les pages dactylographiées, par
    règle et sur deux périmètres : (périmètre, règle, précision, rappel,
    débuts trouvés, débuts de la référence).

    - « cahiers à imprimés » : ceux qui ont au moins une contribution
      imprimée retrouvée. Les manuscrits n'ont pas de position : un début de
      manuscrit trouvé par une règle y compte comme une erreur, la précision
      est donc sous-estimée ;
    - « référence complète » : les cahiers dont toutes les contributions sont
      imprimées et retrouvées.
    """
    par_cahier: dict[str, list[dict]] = {}
    for a in alignement:
        par_cahier.setdefault(a["insee"], []).append(a)
    perimetres = {
        "cahiers à imprimés": {
            i
            for i, lignes_ in par_cahier.items()
            if any(a["source"] == "ocr" for a in lignes_)
        },
        "référence complète": {
            i
            for i, lignes_ in par_cahier.items()
            if all(a["source"] == "ocr" for a in lignes_)
        },
    }
    fichiers = {
        f for i in perimetres["cahiers à imprimés"] for f in scans_par_cahier[i]
    }
    lues = pages_lues([typage], fichiers, ouvertures)
    premieres = premieres_ecrites([typage], fichiers, ouvertures)
    trouves = []
    for fichier, numeros in sorted(lues.items()):
        with pymupdf.open(corpus.chemin(fichier)) as doc:
            pages = [lignes(doc[n - 1]) for n in numeros]
        for p, i, regle in debuts(
            [[t for t, _ in page] for page in pages],
            debut_du_cahier=numeros[0] == premieres.get(fichier),
        ):
            trouves.append((fichier, numeros[p], pages[p][i][1].y0, regle))
    mesures = []
    for nom, cahiers_ in perimetres.items():
        pages_vues = {
            (f, n)
            for i in cahiers_
            for f in scans_par_cahier[i]
            for n in lues.get(f, [])
        }
        reference = [
            (a["fichier"], a["page"], a["y0"])
            for i in cahiers_
            for a in par_cahier[i]
            if a["source"] == "ocr" and (a["fichier"], a["page"]) in pages_vues
        ]
        for regle in (None, "courriel", "gabarit", "début du cahier"):
            retenus = [
                (f, n, y)
                for f, n, y, r in trouves
                if (f, n) in pages_vues and (regle is None or r.startswith(regle))
            ]
            precision, rappel = evaluer(retenus, reference)
            mesures.append(
                (
                    nom,
                    regle or "toutes règles",
                    precision,
                    rappel,
                    len(retenus),
                    len(reference),
                )
            )
    return mesures


def mesurer_manuscrits(
    alignement: list[dict],
    delimites: set[str],
    scans_par_cahier: dict[str, list[str]],
    notes: list[dict],
    htr: Path,
) -> tuple[float, float, int, int, int]:
    """Placement des manuscrits sur les cahiers délimités à la main
    (`delimites`, codes INSEE) : (précision, rappel, manuscrits placés,
    débuts notés, manuscrits de l'édition).

    La référence est faite des débuts notés par le lecteur sur les pages lues
    par l'HTR. Un manuscrit placé est juste s'il tombe sur un début noté,
    à `TOLERANCE` points près (`contributions.regles.evaluer`)."""
    pages = {
        (f, n)
        for i in delimites
        for f in scans_par_cahier[i]
        for n in lecture_htr(htr, f)
    }
    manuscrits = [
        a for a in alignement if a["insee"] in delimites and a["genre"] == "manuscrit"
    ]
    predits = [
        (a["fichier"], a["page"], a["y0"]) for a in manuscrits if a["source"] == "htr"
    ]
    reference = [
        (n["fichier"], n["page"], n["y0"])
        for n in notes
        if n["etiquette"] == DEBUT and (n["fichier"], n["page"]) in pages
    ]
    precision, rappel = evaluer(predits, reference)
    return precision, rappel, len(predits), len(reference), len(manuscrits)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--extraction",
        type=Path,
        default=Path("../data/cahiers_chabin-extraction.json"),
    )
    parser.add_argument("--versement", type=Path, default=Path("data/versement"))
    parser.add_argument("--typage", type=Path, default=Path("data/typage/departements"))
    parser.add_argument("--annotation", type=Path, default=Path("data/annotation"))
    parser.add_argument("--sortie", type=Path, default=Path("data/chabin"))
    parser.add_argument(
        "--ouvertures", type=Path, default=Path("data/ouvertures/ouvertures.csv")
    )
    parser.add_argument("--htr", type=Path, default=Path("../data/htr/manicule-2026"))
    args = parser.parse_args()

    extraction = json.loads(args.extraction.read_text(encoding="utf-8"))
    liste = cahiers(extraction)
    corpus = Corpus(args.versement, args.typage)
    fichiers = [f for c in liste for f in c.fichiers if f in corpus.chemins]
    pages = {f: corpus.pages(f) for f in fichiers}
    manquants = sum(len(c.fichiers) for c in liste) - len(fichiers)

    listes.ecrire(
        args.annotation / "listes",
        "chabin",
        "Référence Chabin : délimiter les contributions",
        (
            "Cahiers transcrits par Marie-Anne Chabin, pour comparer son "
            "découpage au nôtre. Pour chaque cahier : cliquer chaque début de "
            "contribution, clic droit sur chaque fin, dans l'ordre de lecture "
            "(une contribution : un texte d'un même auteur, ou d'un même groupe, "
            "d'un seul tenant). Pas de caviardage. À la fin, le bouton « Cahier "
            "vu » sous la dernière page la marque vue : le cahier est alors "
            "délimité."
        ),
        elements(liste, {f: len(p) for f, p in pages.items()}),
        tache=TACHE,
    )
    print(
        f"Liste « chabin » : {len(liste)} cahiers, {len(fichiers)} scans"
        + (f" ({manquants} absents du versement)" if manquants else "")
    )

    htr = args.htr if args.htr.is_dir() else None
    alignement = aligner(extraction, corpus, htr)
    scans_par_cahier = {e["city"]["insee"]: scans(e) for e in extraction if e}
    if alignement:
        args.sortie.mkdir(parents=True, exist_ok=True)
        with (args.sortie / "alignement.csv").open(
            "w", encoding="utf-8", newline=""
        ) as f:
            ecrivain = csv.DictWriter(f, list(alignement[0]))
            ecrivain.writeheader()
            ecrivain.writerows(alignement)
        print("Contributions imprimées retrouvées dans l'OCR :")
        for g in sorted(IMPRIMEES):
            du_genre = [a for a in alignement if a["genre"] == g]
            n = sum(1 for a in du_genre if a["source"] == "ocr")
            print(f"  {g} : {n} sur {len(du_genre)}")
        manuscrits = [a for a in alignement if a["genre"] == "manuscrit"]
        if htr:
            n = sum(1 for a in manuscrits if a["source"] == "htr")
            print(
                f"Manuscrits retrouvés dans la lecture HTR : {n} sur {len(manuscrits)}"
            )
        else:
            print(f"Pas de lecture HTR ({args.htr}) : manuscrits non cherchés")
        print("Règles de découpage, sur les pages dactylographiées :")
        for perimetre, regle, precision, rappel, n, ref in mesurer_regles(
            alignement,
            scans_par_cahier,
            corpus,
            args.typage,
            lire_ouvertures(args.ouvertures),
        ):
            print(
                f"  {perimetre}, {regle} : {n} débuts trouvés pour {ref}, "
                f"précision {precision:.0%}, rappel {rappel:.0%}"
            )

    carnet = Carnet(args.annotation / "notes.jsonl")
    qualifications = carnet.qualifications(remarques=False)
    vues = {cle for cle, s in carnet.statuts(TACHE, exacte=True).items() if s == "vue"}
    delimites = cahiers_delimites(fichiers, pages, vues, qualifications)
    debuts = Counter(
        n["fichier"] for n in carnet.positions() if n["etiquette"] == DEBUT
    )
    if htr and alignement:
        par_scan = {f: i for i, fs in scans_par_cahier.items() for f in fs}
        cahiers_vus = {
            par_scan[f]
            for f in delimites
            if f in par_scan
            and all(s in delimites for s in scans_par_cahier[par_scan[f]])
        }
        precision, rappel, n, ref, total = mesurer_manuscrits(
            alignement, cahiers_vus, scans_par_cahier, carnet.positions(), htr
        )
        print(
            f"Placement des manuscrits sur {len(cahiers_vus)} cahiers délimités : "
            f"{n} placés sur {total}, {ref} débuts notés sur les pages lues, "
            f"précision {precision:.0%}, rappel {rappel:.0%} "
            f"(à {TOLERANCE} points près)"
        )
    lignes = comparer(liste, debuts, delimites)
    if not lignes:
        print("Aucun cahier délimité : pas encore de comparaison.")
        return

    args.sortie.mkdir(parents=True, exist_ok=True)
    with (args.sortie / "comparaison.csv").open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, list(lignes[0]))
        ecrivain.writeheader()
        ecrivain.writerows(lignes)
    egaux = sum(1 for x in lignes if x["ecart"] == 0)
    print(f"{len(lignes)} cahiers délimités, {egaux} au même compte que l'édition")
    print(
        f"  contributions : édition {sum(x['chabin'] for x in lignes)}, "
        f"lecteur {sum(x['lecteur'] for x in lignes)}"
    )
    for x in lignes:
        if x["ecart"]:
            print(
                f"  {x['commune']} ({x['insee']}) : édition {x['chabin']}, "
                f"lecteur {x['lecteur']}"
            )


if __name__ == "__main__":
    main()
