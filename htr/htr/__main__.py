"""Lecture des pages manuscrites par un modèle HTR léger, sur CPU.

    uv run python -m htr
        (--extraction ../data/cahiers_chabin-extraction.json | --fichiers liste.txt)
        [--versement ../analyse/data/versement]
        [--typage ../analyse/data/typage/departements]
        [--types manuscrite] [--modele manicule-2026]
        [--sortie ../data/htr] [--modeles ../data/htr/modeles] [--processus 2]

Lit les pages des scans demandés que `analyse/corpus/typage` a classées dans l'un
des types donnés. Écrit, pour chaque scan, `<sortie>/<modèle>/<scan>.jsonl` :
une ligne par page lue, avec ses lignes de texte et leur cadre en points de
la page affichée. Un scan déjà lu n'est pas relu : la commande reprend où
elle s'est arrêtée.

Le texte reconnu n'est pas anonymisé : il reste dans data/ (hors git). La
commande n'affiche que des comptes.
"""

import argparse
import csv
import json
import os
import time
from multiprocessing import Pool
from pathlib import Path

import pymupdf

from htr.modeles import MODELES, modele

_lecteur = None


def scans_extraction(chemin: Path) -> list[str]:
    """Les scans des cahiers de l'édition Chabin (`extraction/chabin`)."""
    extraction = json.loads(chemin.read_text(encoding="utf-8"))
    return sorted({Path(f).name for e in extraction if e for f in e["pdf_files"]})


def chemins(versement: Path) -> dict[str, Path]:
    """Nom de fichier → chemin, sous le versement (liens symboliques suivis)."""
    sortie = {}
    for racine, _, fichiers in os.walk(versement, followlinks=True):
        for f in fichiers:
            if f.endswith(".pdf"):
                sortie[f] = Path(racine) / f
    return sortie


def pages_typees(
    typage: Path, fichiers: set[str], types: set[str]
) -> dict[str, list[int]]:
    """Numéros (à partir de 1) des pages de chaque scan dont le type est
    retenu, d'après les CSV de `analyse/corpus/typage`."""
    sortie: dict[str, list[int]] = {}
    for csv_ in sorted(typage.glob("*.csv")):
        with csv_.open(encoding="utf-8") as f:
            for ligne in csv.DictReader(f):
                if ligne["fichier"] in fichiers and ligne["type_page"] in types:
                    sortie.setdefault(ligne["fichier"], []).append(int(ligne["page"]))
    return {f: sorted(n) for f, n in sortie.items()}


def _initialiser(chemin_modele: Path, fils: int) -> None:
    global _lecteur
    import torch

    from htr.lecture import Lecteur

    torch.set_num_threads(fils)
    _lecteur = Lecteur(chemin_modele)


def lire_scan(tache: tuple[Path, list[int], Path]) -> tuple[str, int, int, float]:
    """Lit les pages d'un scan ; écrit le JSONL d'un coup à la fin, pour
    qu'un scan interrompu soit relu en entier."""
    chemin, numeros, cible = tache
    debut = time.time()
    lignes = 0
    with (
        pymupdf.open(chemin) as doc,
        cible.with_name(cible.name + ".part").open("w", encoding="utf-8") as f,
    ):
        for n in numeros:
            lues = _lecteur.lire(doc[n - 1])
            lignes += len(lues)
            f.write(json.dumps({"page": n, "lignes": lues}, ensure_ascii=False) + "\n")
    cible.with_name(cible.name + ".part").rename(cible)
    return chemin.name, len(numeros), lignes, time.time() - debut


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--extraction", type=Path)
    source.add_argument("--fichiers", type=Path, help="un nom de scan par ligne")
    parser.add_argument(
        "--versement", type=Path, default=Path("../analyse/data/versement")
    )
    parser.add_argument(
        "--typage", type=Path, default=Path("../analyse/data/typage/departements")
    )
    parser.add_argument("--types", nargs="+", default=["manuscrite"])
    parser.add_argument("--modele", choices=sorted(MODELES), default="manicule-2026")
    parser.add_argument("--sortie", type=Path, default=Path("../data/htr"))
    parser.add_argument("--modeles", type=Path, default=Path("../data/htr/modeles"))
    parser.add_argument("--processus", type=int, default=2)
    args = parser.parse_args()

    if args.extraction:
        demandes = scans_extraction(args.extraction)
    else:
        demandes = args.fichiers.read_text(encoding="utf-8").split()
    connus = chemins(args.versement)
    absents = [f for f in demandes if f not in connus]
    pages = pages_typees(args.typage, set(demandes) - set(absents), set(args.types))
    dossier = args.sortie / args.modele
    dossier.mkdir(parents=True, exist_ok=True)
    taches = [
        (connus[f], numeros, dossier / f"{Path(f).stem}.jsonl")
        for f, numeros in sorted(pages.items())
        if not (dossier / f"{Path(f).stem}.jsonl").exists()
    ]
    print(
        f"{len(demandes)} scans demandés ({len(absents)} absents du versement), "
        f"{len(pages)} avec des pages {'/'.join(args.types)}, "
        f"{sum(len(t[1]) for t in taches)} pages à lire dans {len(taches)} scans",
        flush=True,
    )
    if not taches:
        return

    chemin_modele = modele(args.modele, args.modeles)
    fils = max(1, (os.cpu_count() or 2) // args.processus)
    debut = time.time()
    total = 0
    with Pool(args.processus, _initialiser, (chemin_modele, fils)) as pool:
        for k, (nom, n, lignes, duree) in enumerate(
            pool.imap_unordered(lire_scan, taches), 1
        ):
            total += n
            print(
                f"{k}/{len(taches)} {nom} : {n} pages, {lignes} lignes, "
                f"{duree:.0f} s ({total} pages en {(time.time() - debut) / 60:.0f} min)",
                flush=True,
            )


if __name__ == "__main__":
    main()
