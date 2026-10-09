"""Recueil des contributions exportées, pour l'association (issue #21).

    uv run python -m recueil [--selection data/selection]
        [--tirage data/tirage/contributions.csv]
        [--typage data/typage/departements] [--cache data/sources]
        [--qualite 80] [--sortie data/recueil]

Mise en page dans `recueil.recueil`. Lit l'export de `python -m selection`
(contributions délimitées et caviardées) et écrit dans la sortie :

- `recueil.pdf` : une page de présentation, la représentativité (tailles de
  communes et régions contre la population), un sommaire, puis chaque
  contribution précédée d'une page de titre. Les pages des contributions
  sont celles de l'export, déjà caviardées, recompressées en JPEG
  (`--qualite`) : le caviardage les réécrit sans perte, cinq fois plus
  lourdes ;
- `index.csv` : une ligne par contribution, dans l'ordre du recueil.

Des noms de communes, des codes et des comptes, jamais de texte des cahiers.
"""

import argparse
import csv
import io
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pymupdf

from communes.rattachement import Referentiel
from communes.representativite import TRANCHES, univers
from panel.panel import lire_typage
from recueil.recueil import (
    STYLE,
    comparaison,
    index,
    page_de_garde,
    page_de_titre,
    page_representativite,
    sommaire,
)

A4 = pymupdf.paper_rect("a4")
MARGE = 50  # points


def ajouter(doc: pymupdf.Document, html: str) -> None:
    """Ajoute le HTML sur autant de pages A4 qu'il en faut."""
    histoire = pymupdf.Story(html=html, user_css=STYLE)
    cadre = A4 + (MARGE, MARGE, -MARGE, -MARGE)
    tampon = io.BytesIO()
    ecrivain = pymupdf.DocumentWriter(tampon)
    while True:
        appareil = ecrivain.begin_page(A4)
        reste, _ = histoire.place(cadre)
        histoire.draw(appareil)
        ecrivain.end_page()
        if not reste:
            break
    ecrivain.close()
    with pymupdf.open("pdf", tampon.getvalue()) as pages:
        doc.insert_pdf(pages)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--selection", type=Path, default=Path("data/selection"))
    parser.add_argument(
        "--tirage", type=Path, default=Path("data/tirage/contributions.csv")
    )
    parser.add_argument("--typage", type=Path, default=Path("data/typage/departements"))
    parser.add_argument("--cache", type=Path, default=Path("data/sources"))
    parser.add_argument(
        "--qualite", type=int, default=80, help="qualité JPEG des pages (1 à 100)"
    )
    parser.add_argument("--sortie", type=Path, default=Path("data/recueil"))
    args = parser.parse_args()

    with (args.selection / "selection.csv").open(encoding="utf-8", newline="") as f:
        selection = list(csv.DictReader(f))
    with args.tirage.open(encoding="utf-8", newline="") as f:
        tirage = {t["fichier"]: t for t in csv.DictReader(f)}
    exportes = {s["fichier"] for s in selection if s["statut"] == "exporté"}
    types = {
        (t["fichier"], int(t["page"])): t["type_page"]
        for t in lire_typage([args.typage])
        if t["fichier"] in exportes
    }
    lignes = index(selection, tirage, types)
    if not lignes:
        print("Aucune contribution exportée : lancer d'abord python -m selection.")
        return

    france = univers(Referentiel.telecharger(args.cache))
    par_taille, par_region = defaultdict(int), defaultdict(int)
    for c in france.values():
        par_taille[c["taille"]] += c["population"]
        par_region[c["region"]] += c["population"]
    par_taille.pop("population inconnue", None)

    doc = pymupdf.open()
    ajouter(
        doc,
        page_de_garde(
            lignes, len(tirage), datetime.now().astimezone().strftime("%d/%m/%Y")
        ),
    )
    ajouter(
        doc,
        page_representativite(
            comparaison(lignes, "taille", par_taille, [t for _, t in TRANCHES]),
            comparaison(lignes, "region", par_region, sorted(par_region)),
        ),
    )
    ajouter(doc, sommaire(lignes))
    for x in lignes:
        ajouter(doc, page_de_titre(x))
        with pymupdf.open(args.selection / "pdf" / x["fichier"]) as contribution:
            doc.insert_pdf(contribution)

    args.sortie.mkdir(parents=True, exist_ok=True)
    doc.set_metadata({"title": "Cahiers citoyens : échantillon de contributions"})
    doc.rewrite_images(quality=args.qualite)
    doc.save(args.sortie / "recueil.pdf", garbage=4, deflate=True)
    with (args.sortie / "index.csv").open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, list(lignes[0]))
        ecrivain.writeheader()
        ecrivain.writerows(lignes)
    taille = (args.sortie / "recueil.pdf").stat().st_size / 1e6
    print(
        f"{len(lignes)} contributions, {doc.page_count} pages, "
        f"{taille:.0f} Mo : {args.sortie / 'recueil.pdf'}"
    )
    sans = [x["commune"] for x in lignes if not x["caviardages"]]
    if sans:
        print(
            f"Sans aucun caviardage, à vérifier avant d'envoyer ({len(sans)}) : "
            + ", ".join(sans)
        )


if __name__ == "__main__":
    main()
