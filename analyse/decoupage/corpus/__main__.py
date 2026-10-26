"""Découpage automatique de tous les cahiers citoyens (issue #5).

    uv run python -m decoupage.corpus [--versement data/versement]
        [--typage data/typage/departements]
        [--ouvertures data/ouvertures/ouvertures.csv]
        [--modele data/contributions/modele.npz] [--processus 4]
        [--sortie data/decoupage/corpus]

Les règles (`decoupage.contributions.regles`) et le modèle entraîné sur les
cahiers délimités (`modele.npz`, écrit par `python -m decoupage.contributions`)
lisent les pages imprimées de chaque cahier citoyen, comme sur les cahiers
délimités. Les contributions s'arrêtent avant les pages manuscrites
(`decoupage.corpus.contributions`).

Écrit `contributions.csv` dans la sortie, au format de
`decoupage.delimitation` (début et fin en points PDF dans le repère de la page
non tournée, comme les notes de l'outil), plus la règle qui a trouvé le
début. Rien n'y est modéré ni caviardé : `publiable` vaut 1 faute de
relecture, ce qui ne dit pas qu'une contribution peut être montrée. Des
positions et des comptes, jamais de texte.
"""

import argparse
import csv
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

from corpus.ouvertures.__main__ import lire as lire_ouvertures
from decoupage.contributions.__main__ import IMPRIMEES, VIERGE
from decoupage.corpus.cahier import decouper, initialiser
from panels.panel.panel import lire_typage

COLONNES = [
    "fichier",
    "rang",
    "page_debut",
    "x_debut",
    "y_debut",
    "page_fin",
    "x_fin",
    "y_fin",
    "fin",
    "publiable",
    "regle",
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--versement", type=Path, default=Path("data/versement"))
    parser.add_argument(
        "--typage", type=Path, nargs="+", default=[Path("data/typage/departements")]
    )
    parser.add_argument(
        "--ouvertures", type=Path, default=Path("data/ouvertures/ouvertures.csv")
    )
    parser.add_argument(
        "--modele", type=Path, default=Path("data/contributions/modele.npz")
    )
    parser.add_argument("--processus", type=int, default=4)
    parser.add_argument("--sortie", type=Path, default=Path("data/decoupage/corpus"))
    args = parser.parse_args()

    if not args.modele.exists():
        parser.error(f"pas de {args.modele} : lancer python -m decoupage.contributions")
    ouvertures = lire_ouvertures(args.ouvertures)
    ecrites = defaultdict(list)
    for ligne in lire_typage(args.typage):
        f, n = ligne["fichier"], int(ligne["page"])
        if (
            f.startswith("CC_")
            and ligne["type_page"] != VIERGE
            and ligne["page_de_service"] != "1"
            and (f, n) not in ouvertures
        ):
            ecrites[f].append((n, ligne["type_page"]))
    chemins = {
        p.name: p
        for p in args.versement.rglob("CC_*.pdf", recurse_symlinks=True)
        if p.name in ecrites
    }
    taches = [
        (chemins[f], f, sorted(pages))
        for f, pages in sorted(ecrites.items())
        if f in chemins and any(t in IMPRIMEES for _, t in pages)
    ]

    lignes = []
    with Pool(args.processus, initialiser, (args.modele,)) as pool:
        for k, sortie in enumerate(pool.imap(decouper, taches, chunksize=8), 1):
            lignes += sortie
            if k % 2000 == 0:
                print(f"  {k}/{len(taches)} cahiers", flush=True)

    args.sortie.mkdir(parents=True, exist_ok=True)
    with (args.sortie / "contributions.csv").open(
        "w", encoding="utf-8", newline=""
    ) as f:
        ecrivain = csv.DictWriter(f, COLONNES)
        ecrivain.writeheader()
        ecrivain.writerows(
            {k: "" if v is None else v for k, v in ligne.items()} for ligne in lignes
        )
    sans = len(ecrites) - len(taches)
    print(
        f"{len(taches)} cahiers découpés ({sans} sans page imprimée), "
        f"{len(lignes)} contributions dans {args.sortie / 'contributions.csv'}"
    )
    for cle, titre in (("regle", "début"), ("fin", "fin")):
        compte = Counter(
            x[cle].split()[0] if cle == "regle" else x[cle] for x in lignes
        )
        print(f"  {titre} : " + ", ".join(f"{k} {n}" for k, n in compte.most_common()))


if __name__ == "__main__":
    main()
