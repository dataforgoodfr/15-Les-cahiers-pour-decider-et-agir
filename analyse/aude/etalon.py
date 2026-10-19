"""Étalon d'anonymisation : les masques des Archives de l'Aude sur nos pages BnF.

    uv sync --group images
    uv run python -m aude.etalon [--aude ../../aude/pdf]
        [--bnf data/versement/BnF_GDN_11_PDF/CC] [--sortie data/aude]
        [--processus 8]

Lit `rapprochement.csv` (`python -m aude`), garde les pages rapprochées sans
doute, et écrit dans la sortie :
- `etalon.csv` : une ligne par masque, en points de la page BnF (x0, y0,
  x1, y1), avec le type de la page (typage, #17) et l'accord des deux images
  autour du masque après recalage (vide si l'entourage est blanc) ;
- `pages_etalon.csv` : une ligne par page, avec son nombre de masques et si
  elle est à vérifier. Une page sans masque compte aussi : les archivistes
  n'y ont rien caché (sauf par découpe, invisible ici).

Des coordonnées, jamais de texte.
"""

import argparse
import csv
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

from aude.masques import MASQUES_MAX, zones

ACCORD_SUR = 0.5  # accord au-delà duquel un masque reporté est sûr


def _types(typage: Path) -> dict[tuple[str, int], str]:
    with typage.open(encoding="utf-8") as f:
        return {
            (r["fichier"], int(r["page"])): r["type_page"] for r in csv.DictReader(f)
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--aude", type=Path, default=Path("../../aude/pdf"))
    parser.add_argument(
        "--bnf", type=Path, default=Path("data/versement/BnF_GDN_11_PDF/CC")
    )
    parser.add_argument(
        "--typage",
        type=Path,
        default=Path("data/typage/departements/BnF_GDN_11_PDF.csv"),
    )
    parser.add_argument("--sortie", type=Path, default=Path("data/aude"))
    parser.add_argument("--processus", type=int, default=8)
    args = parser.parse_args()

    with (args.sortie / "rapprochement.csv").open(encoding="utf-8") as f:
        lignes = [r for r in csv.DictReader(f) if r["fichier"] and r["douteuse"] == "0"]
    commune = {(r["canton"], int(r["page"])): r["commune"] for r in lignes}
    taches = [
        (
            args.aude / f"{r['canton']}.pdf",
            int(r["page"]),
            args.bnf / r["fichier"],
            int(r["page_bnf"]),
        )
        for r in lignes
    ]
    types = _types(args.typage)

    pages = sans_similitude = a_verifier = 0
    masques, avec_masque, accords = Counter(), Counter(), Counter()
    with (
        Pool(args.processus) as pool,
        (args.sortie / "etalon.csv").open("w", encoding="utf-8", newline="") as fe,
        (args.sortie / "pages_etalon.csv").open(
            "w", encoding="utf-8", newline=""
        ) as fp,
    ):
        etalon, par_page = csv.writer(fe), csv.writer(fp)
        entete = ["fichier", "page_bnf", "commune", "type_page", "canton", "page"]
        etalon.writerow([*entete, "x0", "y0", "x1", "y1", "accord"])
        par_page.writerow([*entete, "score", "masques", "a_verifier"])
        for (canton, page, fichier, page_bnf), score, rectangles in pool.imap(
            zones, taches, chunksize=4
        ):
            debut = [
                fichier.name,
                page_bnf,
                commune[canton.stem, page],
                types.get((fichier.name, page_bnf), ""),
                canton.stem,
                page,
            ]
            if rectangles is None:
                sans_similitude += 1
                continue
            trop = len(rectangles) > MASQUES_MAX
            par_page.writerow([*debut, score, len(rectangles), int(trop)])
            pages += 1
            a_verifier += trop
            if trop:
                continue
            masques[debut[3]] += len(rectangles)
            avec_masque[debut[3]] += bool(rectangles)
            for rectangle in rectangles:
                etalon.writerow([*debut, *rectangle])
                accord = rectangle[-1]
                accords[
                    "entourage blanc"
                    if accord is None
                    else "sûr"
                    if accord >= ACCORD_SUR
                    else "à vérifier"
                ] += 1

    print(f"{pages} pages dans l'étalon ({sans_similitude} sans similitude retrouvée)")
    print(f"{a_verifier} à vérifier (plus de {MASQUES_MAX} masques)")
    for type_page in sorted(masques):
        print(
            f"{type_page or '?'} : {masques[type_page]} masques"
            f" sur {avec_masque[type_page]} pages"
        )
    print("Report des masques :", ", ".join(f"{n} {k}" for k, n in accords.items()))
    print(f"Écrit dans {args.sortie}")


if __name__ == "__main__":
    main()
