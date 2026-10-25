"""Tirage des tronçons à délimiter pour tester le découpage (issue #5).

    uv run python -m decoupage.troncons [--typage data/typage/departements]
        [--cahiers data/tirage/contributions.csv]
        [--ouvertures data/ouvertures/ouvertures.csv] [--longueur 10]
        [--graine 2026] [--annotation data/annotation] [--sortie data/troncons]

Méthode dans `decoupage.troncons.troncons`. Seuls les cahiers citoyens comptent ; le
département est celui du fichier de typage, donc du versement. Les versements
sans département (00 : cahiers sans commune ; 99 : étranger) sont écartés,
comme ceux des cahiers de `--cahiers`, déjà délimités. Écrit :

- `decoupage.troncons.csv` dans la sortie : une ligne par tronçon, son cahier, ses
  pages et son poids (pages dactylographiées de son département) ;
- la liste « decoupage » dans `listes/` du dossier d'annotation, de tâche
  « decoupage », à ouvrir avec `python -m annotation`.

Des noms de fichiers, des numéros de pages et des comptes, jamais de texte.
"""

import argparse
import csv
import random
import re
from pathlib import Path

from annotation import listes
from corpus.cascade.cascade import categorie
from corpus.ouvertures.__main__ import lire as lire_ouvertures
from decoupage.troncons.troncons import tirer

VIERGE = "vierge"
SANS_DEPARTEMENT = {"00", "99"}
_DEPARTEMENT = re.compile(r"GDN_(\w+?)_PDF")
CONSIGNE = (
    "Pour chaque tronçon (pages dans le commentaire) : cliquer chaque début "
    "de contribution, dans l'ordre de lecture, manuscrits compris. Regarder "
    "la page qui précède le tronçon pour savoir si sa première page continue "
    "une contribution. Pas de caviardage. Les pages dépassées en défilant se "
    "marquent vues ; à la fin, marquer la dernière page du tronçon vue (v)."
)


def lire_cahiers(typage: Path, ouvertures: set[tuple[str, int]]) -> dict[str, dict]:
    """Par cahier citoyen, son département de versement et ses pages écrites."""
    cahiers: dict[str, dict] = {}
    for chemin in sorted(typage.glob("*.csv")):
        departement = _DEPARTEMENT.search(chemin.name).group(1)
        with chemin.open(encoding="utf-8", newline="") as f:
            for ligne in csv.DictReader(f):
                fichier, page = ligne["fichier"], int(ligne["page"])
                if (
                    categorie(fichier) != "CC"
                    or ligne["type_page"] == VIERGE
                    or ligne["page_de_service"] == "1"
                    or (fichier, page) in ouvertures
                ):
                    continue
                cahier = cahiers.setdefault(
                    fichier, {"departement": departement, "pages": []}
                )
                cahier["pages"].append((page, ligne["type_page"]))
    for cahier in cahiers.values():
        cahier["pages"].sort()
    return cahiers


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--typage", type=Path, default=Path("data/typage/departements"))
    parser.add_argument(
        "--cahiers", type=Path, default=Path("data/tirage/contributions.csv")
    )
    parser.add_argument(
        "--ouvertures", type=Path, default=Path("data/ouvertures/ouvertures.csv")
    )
    parser.add_argument("--longueur", type=int, default=10)
    parser.add_argument("--graine", type=int, default=2026)
    parser.add_argument("--annotation", type=Path, default=Path("data/annotation"))
    parser.add_argument("--sortie", type=Path, default=Path("data/troncons"))
    args = parser.parse_args()

    cahiers = lire_cahiers(args.typage, lire_ouvertures(args.ouvertures))
    with args.cahiers.open(encoding="utf-8", newline="") as f:
        delimites = {ligne["fichier"] for ligne in csv.DictReader(f)}
    couverts = {cahiers[f]["departement"] for f in delimites if f in cahiers}
    troncons = tirer(
        cahiers, couverts | SANS_DEPARTEMENT, random.Random(args.graine), args.longueur
    )

    args.sortie.mkdir(parents=True, exist_ok=True)
    with (args.sortie / "troncons.csv").open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, list(troncons[0]))
        ecrivain.writeheader()
        ecrivain.writerows(troncons)
    listes.ecrire(
        args.annotation / "listes",
        "decoupage",
        f"Découpage : {len(troncons)} tronçons de test",
        CONSIGNE,
        [
            {
                "fichier": t["fichier"],
                "page": t["premiere"],
                "marques": [],
                "commentaire": (
                    f"Département {t['departement']} : pages {t['premiere']} à "
                    f"{t['derniere']} ({t['pages']} pages écrites, "
                    f"{t['dactylographiees']} dactylographiées)."
                ),
            }
            for t in troncons
        ],
        tache="decoupage",
    )
    print(
        f"{len(couverts)} départements déjà délimités, {len(troncons)} tronçons "
        f"tirés : {sum(t['pages'] for t in troncons)} pages écrites, dont "
        f"{sum(t['dactylographiees'] for t in troncons)} dactylographiées"
    )


if __name__ == "__main__":
    main()
