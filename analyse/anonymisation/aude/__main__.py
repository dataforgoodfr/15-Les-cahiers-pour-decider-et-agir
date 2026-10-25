"""Rapproche les pages des cahiers de l'Aude publiés par le CESE des pages BnF.

    uv sync --group images
    uv run python -m anonymisation.aude [--aude ../../aude/pdf]
        [--bnf data/versement/BnF_GDN_11_PDF/CC] [--sortie data/aude]
        [--processus 8]

Écrit dans la sortie :
- `rapprochement.csv` : une ligne par page publiée (canton, page, nature :
  scan ou texte du CESE), avec sa page BnF quand elle est retrouvée, la
  commune (code INSEE du fichier BnF), le score, le meilleur score d'une
  autre commune, la page douteuse s'il en est proche, et les autres pages BnF
  de la même commune (doublons du versement) ;
- `corpus.communes.csv` : une ligne par cahier BnF retrouvé (fichier et commune : un
  fichier peut contenir le cahier d'une autre commune, voir `corpus.concatenes`),
  avec son canton, les pages publiées qui en viennent et la part de ses pages
  écrites publiée.

Des numéros de page et des scores, jamais de texte.
"""

import argparse
import csv
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

from anonymisation.aude.rapprochement import Index, pages_bnf, pages_publiees


def _vierges(typage: Path) -> dict[str, set[int]]:
    vierges = defaultdict(set)
    with typage.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["type_page"] == "vierge":
                vierges[r["fichier"]].add(int(r["page"]))
    return vierges


def _concatenes(chemin: Path) -> dict[str, list[tuple[int, str]]]:
    """Fichiers BnF qui contiennent le cahier d'autres communes (#42) :
    première page et code INSEE de chacun, « p17:11390 » dans concatenes.csv."""
    if not chemin.exists():
        return {}
    debuts = {}
    with chemin.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["categorie"] == "concatene":
                debuts[r["fichier"]] = [
                    (int(p[1:]), code)
                    for p, code in (x.split(":") for x in r["autres_communes"].split())
                ]
    return debuts


def commune(fichier: str, page: int = 1, concatenes=None) -> str:
    """Code INSEE d'une page BnF : celui du nom de fichier
    (CC_<postal>_<date>_<INSEE>_…), sauf dans le cahier d'une autre commune
    concaténé au fichier."""
    code = fichier.split("_")[3]
    for debut, autre in (concatenes or {}).get(fichier, []):
        if page >= debut:
            code = autre
    return code


def _plages(pages: list[int]) -> str:
    """« 3-21 25 » pour [3, …, 21, 25]."""
    morceaux, debut = [], None
    for i, p in enumerate(pages):
        if debut is None:
            debut = p
        if i + 1 == len(pages) or pages[i + 1] != p + 1:
            morceaux.append(str(p) if p == debut else f"{debut}-{p}")
            debut = None
    return " ".join(morceaux)


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
    parser.add_argument(
        "--concatenes", type=Path, default=Path("data/concatenes/concatenes.csv")
    )
    parser.add_argument("--sortie", type=Path, default=Path("data/aude"))
    parser.add_argument("--processus", type=int, default=8)
    args = parser.parse_args()

    vierges = _vierges(args.typage)
    concatenes = _concatenes(args.concatenes)
    with Pool(args.processus) as pool:
        bnf = [
            p
            for f in pool.imap(
                pages_bnf,
                [(c, vierges[c.name]) for c in sorted(args.bnf.glob("*.pdf"))],
            )
            for p in f
        ]
        publiees = [
            p
            for f in pool.imap(pages_publiees, sorted(args.aude.glob("*.pdf")))
            for p in f
        ]
    print(f"{len(bnf)} pages BnF non vierges, {len(publiees)} pages publiées")
    communes = [commune(f, p, concatenes) for f, p, _ in bnf]
    index = Index([d for _, _, d in bnf], communes)

    args.sortie.mkdir(parents=True, exist_ok=True)
    trouvees = defaultdict(list)  # (fichier, commune) -> [(page BnF, canton, page)]
    scans = douteuses = doublons = 0
    with (args.sortie / "rapprochement.csv").open(
        "w", encoding="utf-8", newline=""
    ) as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(
            [
                "canton",
                "page",
                "nature",
                "fichier",
                "page_bnf",
                "commune",
                "score",
                "autre_commune",
                "douteuse",
                "doublons",
            ]
        )
        for canton, page, n, d in publiees:
            if n != "scan":
                ecrivain.writerow([canton, page, n, "", "", "", "", "", "", ""])
                continue
            scans += 1
            r = index.rapprocher(d)
            if r.page is None:
                ecrivain.writerow(
                    [canton, page, n, "", "", "", r.score, r.autre_commune, "", ""]
                )
                continue
            fichier, page_bnf, _ = bnf[r.page]
            if r.douteuse:
                douteuses += 1
            else:
                trouvees[fichier, communes[r.page]].append((page_bnf, canton, page))
            doublons += bool(r.doublons)
            ecrivain.writerow(
                [
                    canton,
                    page,
                    n,
                    fichier,
                    page_bnf,
                    communes[r.page],
                    r.score,
                    r.autre_commune,
                    int(r.douteuse),
                    " ".join(f"{bnf[j][0]}:{bnf[j][1]}" for j in r.doublons),
                ]
            )

    ecrites = Counter(zip((f for f, _, _ in bnf), communes))
    with (args.sortie / "communes.csv").open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(
            [
                "fichier",
                "commune",
                "canton",
                "pages_publiees",
                "pages_bnf",
                "ecrites_bnf",
            ]
        )
        for (fichier, code), liste in sorted(trouvees.items()):
            cantons = Counter(c for _, c, _ in liste)
            ecrivain.writerow(
                [
                    fichier,
                    code,
                    " ".join(cantons),
                    _plages(sorted(p for _, _, p in liste)),
                    len({p for p, _, _ in liste}),
                    ecrites[fichier, code],
                ]
            )

    rapprochees = sum(len(v) for v in trouvees.values())
    print(f"{rapprochees} pages publiées rapprochées sur {scans} scans")
    print(f"{douteuses} douteuses (une autre commune presque aussi proche)")
    print(f"{doublons} présentes plusieurs fois dans le versement")
    fichiers = {f for f, _ in trouvees}
    print(f"{len(fichiers)} fichiers BnF retrouvés sur {len({f for f, _ in ecrites})}")
    print(f"{len({c for _, c in trouvees})} communes")
    print(f"Écrit dans {args.sortie}")


if __name__ == "__main__":
    main()
