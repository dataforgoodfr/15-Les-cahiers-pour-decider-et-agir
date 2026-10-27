"""Propositions de l'édition Chabin à revoir, sous-thème par sous-thème (issue #24).

    uv run python -m classement.themes.revue
        [--chabin ../data/cahiers_chabin-extraction.json]
        [--pdf ../data/cahiers_chabin-pdfs]
        [--propositions data/propositions/propositions.csv]
        [--contributions 20] [--graine 2710] [--sortie data/themes/revue.csv]

Les mots-clés (`classement.themes.sous_themes`) et un LLM ne s'accordent pas
sur les sous-thèmes larges. Pour savoir lequel a raison, des annotateurs
cochent, dans l'outil d'annotation (`/themes`, `annotation.themes`), les
sous-thèmes de la grille que chaque proposition traite. Jugée en entier, une
contribution touche presque tous les sous-thèmes : l'unité est la
proposition (`python -m classement.propositions`), et la contribution
réunit celles de ses propositions.

Les contributions sont tirées au hasard dans l'édition Chabin (au moins
`TEXTE_MIN` caractères), avec la graine de la comparaison au LLM : les
`--contributions` premières des `TIRAGE` tirées. Pour que l'annotateur voie
le texte source, chaque proposition est retrouvée dans le PDF de l'édition :
sa page et le cadre de ses premiers mots, en points PDF (`MOTS_REPERE`).

L'édition Chabin est publiée et déjà anonymisée. La commande n'affiche que
des comptes.
"""

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path

import pymupdf

from classement.themes.sous_themes import normaliser

TEXTE_MIN = 200
TIRAGE = 300  # contributions de la comparaison au LLM
MOTS_REPERE = 5  # premiers mots cherchés dans le PDF
PAGES_MAX = 3  # pages après la précédente où chercher une proposition
COLONNES = [
    "proposition",
    "contribution",
    "commune",
    "numero",
    "contexte",
    "texte",
    "pdf",
    "page",
    "largeur",
    "hauteur",
    "cadres",
]


def tirer(extraction: list[dict | None], nombre: int, graine: int) -> list[dict]:
    """Les contributions tirées, dans l'ordre du tirage."""
    toutes = [
        {
            "contribution": f"{e['city']['insee']}-{rang}",
            "commune": e["city"]["commune"],
            "texte": c["text"],
            "pdf": e["chabin_pdf_files"],
        }
        for e in extraction
        if e
        for rang, c in enumerate(e["contributions"], 1)
        if len(c["text"]) >= TEXTE_MIN
    ]
    return random.Random(graine).sample(toutes, TIRAGE)[:nombre]


def _jetons(texte: str) -> list[str]:
    return [j for j in normaliser(texte).split() if j]


def _chercher(
    doc, texte: str, depuis: tuple[int, float], pages: int = PAGES_MAX
) -> tuple[int, list] | None:
    """La première occurrence des premiers mots de `texte` après `depuis`
    (page, ordonnée), dans les `pages` pages suivantes : sa page (à partir de 1) et le cadre de ces mots sur
    chaque ligne. Les mots sont comparés normalisés, d'une ligne à l'autre :
    la découpe recolle les lignes et retire puces et notes."""
    cherches = _jetons(texte)[:MOTS_REPERE]
    if not cherches:
        return None
    page, y = depuis
    for n in range(page, min(page + pages + 1, doc.page_count + 1)):
        p = doc[n - 1]
        mots = [
            (pymupdf.Rect(m[:4]), j)
            for m in p.get_text("words", sort=True)
            for j in _jetons(m[4])
        ]
        jetons = [j for _, j in mots]
        for i in range(len(mots) - len(cherches) + 1):
            if jetons[i : i + len(cherches)] != cherches:
                continue
            if n == page and mots[i][0].y0 <= y:
                continue
            lignes: dict[float, pymupdf.Rect] = {}
            for cadre, _ in mots[i : i + len(cherches)]:
                cle = round(cadre.y0)
                lignes[cle] = lignes.get(cle, cadre) | cadre
            return n, [
                [round(v, 1) for v in cadre * p.rotation_matrix]
                for cadre in lignes.values()
            ]
    return None


def situer(doc, contribution: str, propositions: list[dict]) -> list[dict]:
    """La page et les cadres de chaque proposition, dans l'ordre ; à défaut,
    la page de la précédente, sans cadre."""
    # le début de la contribution, ou à défaut sa première proposition
    # retrouvée, n'importe où dans le PDF
    debut = _chercher(doc, contribution, (1, -1), doc.page_count) or next(
        filter(
            None,
            (_chercher(doc, p["texte"], (1, -1), doc.page_count) for p in propositions),
        ),
        None,
    )
    position = (debut[0], debut[1][0][1] - 1) if debut else (1, -1)
    sortie = []
    for p in propositions:
        trouve = _chercher(doc, p["texte"], position)
        if trouve:
            position = (trouve[0], trouve[1][0][1])
        page = doc[position[0] - 1]
        sortie.append(
            {
                "page": position[0],
                "largeur": round(page.rect.width, 1),
                "hauteur": round(page.rect.height, 1),
                "cadres": json.dumps(trouve[1] if trouve else []),
            }
        )
    return sortie


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--chabin", type=Path, default=Path("../data/cahiers_chabin-extraction.json")
    )
    parser.add_argument("--pdf", type=Path, default=Path("../data/cahiers_chabin-pdfs"))
    parser.add_argument(
        "--propositions", type=Path, default=Path("data/propositions/propositions.csv")
    )
    parser.add_argument("--contributions", type=int, default=20)
    parser.add_argument("--graine", type=int, default=2710)
    parser.add_argument("--sortie", type=Path, default=Path("data/themes/revue.csv"))
    args = parser.parse_args()

    extraction = json.loads(args.chabin.read_text(encoding="utf-8"))
    par_contribution = defaultdict(list)
    with args.propositions.open(encoding="utf-8", newline="") as f:
        for x in csv.DictReader(f):
            par_contribution[f"{x['insee']}-{x['rang']}"].append(x)
    tirees = tirer(extraction, args.contributions, args.graine)
    lignes, situees = [], 0
    for c in tirees:
        propositions = sorted(
            par_contribution[c["contribution"]], key=lambda x: int(x["numero"])
        )
        pdf = next((f for f in c["pdf"] if (args.pdf / f).exists()), None)
        if pdf is None:
            parser.error(f"{c['contribution']} : PDF de l'édition introuvable")
        with pymupdf.open(args.pdf / pdf) as doc:
            places = situer(doc, c["texte"], propositions)
        for p, place in zip(propositions, places, strict=True):
            situees += place["cadres"] != "[]"
            lignes.append(
                {
                    "proposition": f"{c['contribution']}-{p['numero']}",
                    "contribution": c["contribution"],
                    "commune": c["commune"],
                    "numero": p["numero"],
                    "contexte": p["contexte"],
                    "texte": p["texte"],
                    "pdf": pdf,
                }
                | place
            )
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    with args.sortie.open("w", encoding="utf-8", newline="") as f:
        ecrire = csv.DictWriter(f, COLONNES)
        ecrire.writeheader()
        ecrire.writerows(lignes)
    print(
        f"{len(tirees)} contributions, {len(lignes)} propositions, "
        f"{situees} retrouvées dans le PDF de l'édition"
    )


if __name__ == "__main__":
    main()
