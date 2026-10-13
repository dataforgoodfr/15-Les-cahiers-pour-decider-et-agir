"""Toutes les contributions délimitées à la main dans les cahiers tirés (#95).

    uv run python -m delimitation [--cahiers data/tirage/contributions.csv]
        [--versement data/versement] [--typage data/typage/departements]
        [--annotation data/annotation] [--sortie data/delimitation]

Pour chaque cahier délimité dans l'outil d'annotation (tâche « selection »,
voir `selection`), toutes ses contributions et pas seulement la tirée.
Écrit `contributions.csv` dans la sortie, que la plateforme charge
(`manage.py charger_contributions`) : une ligne par contribution, son rang,
son début et sa fin en points PDF dans le repère de la page non tournée,
comme les notes de l'outil. La fin est la fin notée, sinon le début
suivant, sinon le bas de la dernière page (sans position). `publiable` est
faux si une de ses pages est « à écarter ». Un cahier dont un début est posé
deux fois est laissé de côté, comme dans `selection`.

Ne touche pas aux PDF exportés par `selection`. Des pages et des positions,
jamais de texte.
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from annotation.carnet import Carnet
from annotation.corpus import Corpus
from selection.__main__ import TACHE, lire_cahier
from selection.contribution import delimites, doublons, ecartee, toutes, vers_pdf

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
]


def lignes_du_cahier(fichier, sens, debuts, fins, qualifications) -> list[dict]:
    """Les contributions du cahier, positions ramenées au repère du PDF."""
    contributions = toutes(debuts, fins, len(sens))
    lignes = []
    for k, c in enumerate(contributions):
        x_debut, y_debut = vers_pdf(sens[c.page_debut], c.y_debut, c.x_debut)
        if c.fin_notee:
            fin = "notée"
            x_fin, y_fin = vers_pdf(sens[c.page_fin], c.y_fin, c.x_fin)
        elif k + 1 < len(contributions):
            fin = "début suivant"
            suivante = contributions[k + 1]
            x_fin, y_fin = vers_pdf(sens[c.page_fin], c.y_fin, suivante.x_debut)
        else:
            fin, x_fin, y_fin = "fin du cahier", None, None
        lignes.append(
            {
                "fichier": fichier,
                "rang": c.rang,
                "page_debut": c.page_debut,
                "x_debut": round(x_debut, 1),
                "y_debut": round(y_debut, 1),
                "page_fin": c.page_fin,
                "x_fin": "" if x_fin is None else round(x_fin, 1),
                "y_fin": "" if y_fin is None else round(y_fin, 1),
                "fin": fin,
                "publiable": int(not ecartee(fichier, c.pages, qualifications)),
            }
        )
    return lignes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--cahiers", type=Path, default=Path("data/tirage/contributions.csv")
    )
    parser.add_argument("--versement", type=Path, default=Path("data/versement"))
    parser.add_argument("--typage", type=Path, default=Path("data/typage/departements"))
    parser.add_argument("--annotation", type=Path, default=Path("data/annotation"))
    parser.add_argument("--sortie", type=Path, default=Path("data/delimitation"))
    args = parser.parse_args()

    with args.cahiers.open(encoding="utf-8", newline="") as f:
        fichiers = {t["fichier"] for t in csv.DictReader(f)}
    chemins = {p.name: p for p in args.versement.rglob("*.pdf") if p.name in fichiers}
    carnet = Carnet(args.annotation / "notes.jsonl")
    qualifications = carnet.qualifications(remarques=False)
    vues = {cle for cle, s in carnet.statuts(TACHE, exacte=True).items() if s == "vue"}
    corpus = Corpus(args.versement, args.typage)
    vus = delimites(
        fichiers,
        {f: corpus.pages(f) for f in fichiers if f in chemins},
        vues,
        qualifications,
    )
    notes, _ = carnet.etat()
    par_cahier = defaultdict(list)
    for n in notes.values():
        if n.get("fichier") in vus:
            par_cahier[n["fichier"]].append(n)

    lignes, en_double = [], []
    for fichier in sorted(vus):
        sens, debuts, fins, _, _ = lire_cahier(
            chemins[fichier], fichier, par_cahier[fichier], qualifications
        )
        if doublons(debuts)[1]:
            en_double.append(fichier)
            continue
        lignes += lignes_du_cahier(fichier, sens, debuts, fins, qualifications)

    args.sortie.mkdir(parents=True, exist_ok=True)
    with (args.sortie / "contributions.csv").open(
        "w", encoding="utf-8", newline=""
    ) as f:
        ecrivain = csv.DictWriter(f, COLONNES)
        ecrivain.writeheader()
        ecrivain.writerows(lignes)
    cahiers = {x["fichier"] for x in lignes}
    print(f"{len(lignes)} contributions dans {len(cahiers)} cahiers délimités")
    print(
        f"  non publiables (à écarter) : {sum(1 for x in lignes if not x['publiable'])}"
    )
    for fin in ("notée", "début suivant", "fin du cahier"):
        print(f"  fin {fin} : {sum(1 for x in lignes if x['fin'] == fin)}")
    if en_double:
        print(f"  laissés de côté, débuts en double : {', '.join(en_double)}")
    print(f"Écrit dans {args.sortie / 'contributions.csv'}")


if __name__ == "__main__":
    main()
