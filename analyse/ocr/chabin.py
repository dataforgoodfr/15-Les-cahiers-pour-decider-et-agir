"""Qualité de l'OCR du versement, mesurée sur l'édition Chabin (issue #12).

    uv run python -m ocr.chabin
        [--extraction ../data/cahiers_chabin-extraction.json]
        [--alignement data/chabin/alignement.csv]
        [--versement data/versement] [--sortie data/ocr]

La couche texte des PDF du versement vient d'ABBYY FineReader Engine 11
(métadonnées des fichiers). Marie-Anne Chabin a transcrit à la main les
contributions de Charente-Maritime : pour celles qu'elle dit dactylographiées
ou imprimées d'une messagerie, `python -m chabin` a retrouvé dans l'OCR la
ligne où elles commencent (`alignement.csv`). On en tire le taux d'erreur de
l'OCR par caractère (CER) et par mot (WER).

L'OCR est lu à partir de cette ligne, dans l'ordre de la couche texte, page
après page, jusqu'au début de la contribution suivante retrouvée. Sa fin est
celle qui ressemble le plus à la transcription (distance d'édition
semi-globale) : un manuscrit qui suit, mal lu, ne compte pas.

Trois variantes, comme au banc HTR (`docs/htr.md`) : brute, normalisée
(minuscules, sans ponctuation), sans accents. Les ajouts entre crochets de
l'édition (anonymisation, [sic]) sont retirés de la référence ; le nom
qu'ils cachent reste dans l'OCR et compte comme erreur : la mesure est
un peu pessimiste.

Écrit `chabin.csv` (une ligne par contribution : commune, rang, forme,
longueur, erreurs) et `chabin.md` dans la sortie. Des codes et des taux,
jamais de texte.
"""

import argparse
import csv
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import numpy as np
import pymupdf

from contributions.__main__ import lignes

CROCHETS = re.compile(r"\[[^\]]*\]")
MARGE = 1.5  # longueur d'OCR lue au plus, rapportée à la transcription
SEUILS = (0.02, 0.05, 0.10, 0.25)  # CER au-delà desquels compter les contributions


def brute(texte: str) -> str:
    return " ".join(texte.split())


def normalisee(texte: str) -> str:
    texte = unicodedata.normalize("NFC", texte).lower().replace("’", "'")
    return " ".join(re.sub(r"[^\w']+", " ", texte).split())


def sans_accents(texte: str) -> str:
    texte = normalisee(texte).replace("œ", "oe").replace("æ", "ae")
    return "".join(
        c for c in unicodedata.normalize("NFD", texte) if not unicodedata.combining(c)
    )


VARIANTES = {"brute": brute, "normalisée": normalisee, "sans accents": sans_accents}


def distance_semi_globale(reference: list, ocr: list) -> tuple[int, int]:
    """La plus petite distance d'édition entre `reference` et un début de
    `ocr`, et la longueur de ce début. Fonctionne sur des caractères comme
    sur des mots."""
    if not reference:
        return 0, 0
    codes = {s: k for k, s in enumerate(dict.fromkeys([*reference, *ocr]))}
    ref = np.array([codes[s] for s in reference])
    hyp = np.array([codes[s] for s in ocr])
    colonnes = np.arange(len(hyp) + 1)
    ligne = colonnes.copy()  # distance de la référence vide aux débuts de l'OCR
    for i, r in enumerate(ref, start=1):
        precedente = ligne
        ligne = np.empty_like(precedente)
        ligne[0] = i
        # substitution ou égalité, puis suppression
        ligne[1:] = np.minimum(precedente[:-1] + (hyp != r), precedente[1:] + 1)
        ligne[0] = min(ligne[0], precedente[0] + 1)
        # insertion : ligne[j] = min(ligne[j], ligne[j-1] + 1), d'un trait
        ligne = np.minimum.accumulate(ligne - colonnes) + colonnes
    fin = int(np.argmin(ligne))
    return int(ligne[fin]), fin


def erreurs(reference: str, ocr: str) -> dict[str, float]:
    """Par variante : CER et WER de l'OCR contre la référence."""
    sortie = {"caracteres": len(normalisee(reference))}
    for nom, norm in VARIANTES.items():
        ref, hyp = norm(reference), norm(ocr)
        hyp = hyp[: int(len(ref) * MARGE) + 50]
        d, _ = distance_semi_globale(list(ref), list(hyp))
        sortie[f"cer {nom}"] = d / len(ref) if ref else 0.0
        mots_ref, mots_hyp = ref.split(), hyp.split()
        d, _ = distance_semi_globale(
            mots_ref, mots_hyp[: int(len(mots_ref) * MARGE) + 10]
        )
        sortie[f"wer {nom}"] = d / len(mots_ref) if mots_ref else 0.0
    return sortie


def flux(chemins: list[Path]) -> list[tuple[str, int, int, str]]:
    """Les lignes de la couche texte des scans, dans l'ordre : (fichier,
    page, ligne dans la page, texte)."""
    sortie = []
    for chemin in chemins:
        with pymupdf.open(chemin) as doc:
            for n, page in enumerate(doc, 1):
                sortie += [
                    (chemin.name, n, i, texte)
                    for i, (texte, _) in enumerate(lignes(page))
                ]
    return sortie


def lire_alignement(chemin: Path) -> dict[str, list[dict]]:
    """Les contributions retrouvées dans l'OCR, par commune, dans l'ordre."""
    par_commune = defaultdict(list)
    with chemin.open(encoding="utf-8", newline="") as f:
        for a in csv.DictReader(f):
            if a["fichier"] and a["genre"] in ("dactylographié", "mail"):
                par_commune[a["insee"]].append(
                    a
                    | {
                        "rang": int(a["rang"]),
                        "page": int(a["page"]),
                        "ligne": int(a["ligne"]),
                    }
                )
    return par_commune


def mesurer(extraction: list, alignement: dict, versement: Path) -> list[dict]:
    chemins = {p.name: p for p in versement.rglob("*.pdf")}
    resultats = []
    for e in extraction:
        if not e or e["city"]["insee"] not in alignement:
            continue
        trouvees = alignement[e["city"]["insee"]]
        scans = [chemins[Path(f).name] for f in e["pdf_files"]]
        lignes_ocr = flux(scans)
        position = {(f, n, i): k for k, (f, n, i, _) in enumerate(lignes_ocr)}
        debuts = sorted(position[a["fichier"], a["page"], a["ligne"]] for a in trouvees)
        for a in trouvees:
            debut = position[a["fichier"], a["page"], a["ligne"]]
            suivant = next((d for d in debuts if d > debut), len(lignes_ocr))
            ocr = " ".join(t for *_, t in lignes_ocr[debut:suivant])
            reference = CROCHETS.sub(" ", e["contributions"][a["rang"] - 1]["text"])
            resultats.append(
                {
                    "insee": a["insee"],
                    "rang": a["rang"],
                    "genre": a["genre"],
                    "fichier": a["fichier"],
                    "page": a["page"],
                }
                | {
                    k: round(v, 4) if isinstance(v, float) else v
                    for k, v in erreurs(reference, ocr).items()
                }
            )
        print(f"{e['city']['insee']} : {len(trouvees)} contributions", flush=True)
    return resultats


def rapport(resultats: list[dict]) -> str:
    lignes_ = [
        "# Qualité de l'OCR sur l'édition Chabin",
        "",
        (
            f"{len(resultats)} contributions imprimées de Charente-Maritime, "
            f"{len({r['insee'] for r in resultats})} communes, retrouvées dans "
            "l'OCR du versement (ABBYY FineReader Engine 11) et comparées à la "
            "transcription de Marie-Anne Chabin. Taux pondérés par la longueur "
            "des contributions ; médiane par contribution entre parenthèses."
        ),
        "",
        "| forme | contributions | caractères | CER brut | CER normalisé "
        "| CER sans accents | WER normalisé | "
        + " | ".join(f"CER > {s:.0%}" for s in SEUILS)
        + " |",
        "|---|---|---|---|---|---|---|" + "---|" * len(SEUILS),
    ]
    for forme in ("dactylographié", "mail", None):
        groupe = [r for r in resultats if forme is None or r["genre"] == forme]
        if not groupe:
            continue
        poids = np.array([r["caracteres"] for r in groupe], dtype=float)

        def taux(cle, groupe=groupe, poids=poids):
            v = np.array([r[cle] for r in groupe])
            return f"{np.average(v, weights=poids):.1%} ({np.median(v):.1%})"

        cer = np.array([r["cer sans accents"] for r in groupe])
        lignes_.append(
            f"| {forme or 'toutes'} | {len(groupe)} | {int(poids.sum())} "
            f"| {taux('cer brute')} | {taux('cer normalisée')} "
            f"| {taux('cer sans accents')} | {taux('wer normalisée')} | "
            + " | ".join(f"{(cer > s).sum()}" for s in SEUILS)
            + " |"
        )
    return "\n".join(lignes_)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--extraction",
        type=Path,
        default=Path("../data/cahiers_chabin-extraction.json"),
    )
    parser.add_argument(
        "--alignement", type=Path, default=Path("data/chabin/alignement.csv")
    )
    parser.add_argument("--versement", type=Path, default=Path("data/versement"))
    parser.add_argument("--sortie", type=Path, default=Path("data/ocr"))
    args = parser.parse_args()
    extraction = json.loads(args.extraction.read_text(encoding="utf-8"))
    resultats = mesurer(extraction, lire_alignement(args.alignement), args.versement)
    args.sortie.mkdir(parents=True, exist_ok=True)
    with (args.sortie / "chabin.csv").open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, list(resultats[0]))
        ecrivain.writeheader()
        ecrivain.writerows(resultats)
    texte = rapport(resultats)
    (args.sortie / "chabin.md").write_text(texte + "\n", encoding="utf-8")
    print(texte)


if __name__ == "__main__":
    main()
