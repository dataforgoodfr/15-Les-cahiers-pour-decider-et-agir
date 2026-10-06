"""Export des contributions tirées, caviardées (issues #21 et #7).

    uv run python -m selection [--cahiers data/tirage/contributions.csv]
        [--versement data/versement] [--annotation data/annotation]
        [--reperes data/anonymisation/reperes.csv] [--sortie data/selection]

Lit la liste « selection » de l'outil d'annotation : un cahier marqué vu a
tous ses débuts de contributions notés. La contribution tirée s'en déduit
(`selection.contribution`). Écrit dans la sortie :

- `pdf/` : un PDF par contribution tirée, réduit à ses pages. Ce qui n'est pas
  la contribution (au-dessus de son début, en dessous de sa fin) est couvert
  de gris ; les données personnelles de noir. Le caviardage est une vraie
  rédaction : le texte et les pixels dessous disparaissent, et les
  métadonnées du PDF sont effacées ;
- `selection.csv` : une ligne par cahier tiré, sa commune, la contribution
  retenue (rang, pages) et le nombre de cadres caviardés, ou ce qui manque.

À caviarder : les notes de données personnelles et de signature de ces pages,
et sur les pages dactylographiées les repérages de `anonymisation` que la
relecture n'a pas rétablis (dans le doute, on cache). Des pages, des cadres et
des comptes, jamais de texte.
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import pymupdf

from annotation.carnet import Carnet
from anonymisation.__main__ import PERSONNELLES
from anonymisation.masquage import CHAMPS, a_masquer, fusionner
from selection.contribution import doublons, hors_contribution, tiree

TACHE = "selection"
DEBUT = "début de contribution"
FIN = "fin de contribution"
A_CACHER = PERSONNELLES | {"signature"}
NOIR = (0, 0, 0)
GRIS = (0.82, 0.82, 0.82)


def ordonnee(n: dict) -> float:
    return min(n["y0"], n["y1"])


def cadre(n: dict) -> pymupdf.Rect:
    return pymupdf.Rect(
        min(n["x0"], n["x1"]),
        min(n["y0"], n["y1"]),
        max(n["x0"], n["x1"]),
        max(n["y0"], n["y1"]),
    )


def caviarder(
    chemin: Path, sortie: Path, t, noirs: dict[int, list], fichier: str
) -> int:
    """Écrit le PDF de la contribution `t` ; rend le nombre de cadres noirs."""
    total = 0
    with pymupdf.open(chemin) as doc:
        for n in t.pages:
            page = doc[n - 1]
            # les cadres sont dans le repère de la page affichée (rotation comprise)
            vers_pdf = page.derotation_matrix
            gris = hors_contribution(t, n, page.rect.width, page.rect.height)
            for r in gris:
                page.add_redact_annot(pymupdf.Rect(r) * vers_pdf, fill=GRIS)
            for r in noirs.get(n, []):
                # une donnée sur un pixel de bord reste cachée : marge d'un point
                page.add_redact_annot((r + (-1, -1, 1, 1)) * vers_pdf, fill=NOIR)
                total += 1
            page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_PIXELS)
        doc.select([n - 1 for n in t.pages])
        doc.scrub()
        doc.set_metadata({"title": f"Contribution tirée de {fichier}"})
        doc.save(sortie, garbage=4, deflate=True)
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--cahiers", type=Path, default=Path("data/tirage/contributions.csv")
    )
    parser.add_argument("--versement", type=Path, default=Path("data/versement"))
    parser.add_argument("--annotation", type=Path, default=Path("data/annotation"))
    parser.add_argument(
        "--reperes", type=Path, default=Path("data/anonymisation/reperes.csv")
    )
    parser.add_argument("--sortie", type=Path, default=Path("data/selection"))
    args = parser.parse_args()

    with args.cahiers.open(encoding="utf-8", newline="") as f:
        tirage = list(csv.DictReader(f))
    fichiers = {t["fichier"] for t in tirage}
    chemins = {p.name: p for p in args.versement.rglob("*.pdf") if p.name in fichiers}
    carnet = Carnet(args.annotation / "notes.jsonl")
    vus = {
        f
        for (f, _), s in carnet.statuts(TACHE, exacte=True).items()
        if s == "vue" and f in fichiers
    }
    notes, _ = carnet.etat()
    par_cahier = defaultdict(list)
    for n in notes.values():
        if n.get("fichier") in fichiers:
            par_cahier[n["fichier"]].append(n)
    with args.reperes.open(encoding="utf-8", newline="") as f:
        reperes = [
            {**r, "page": int(r["page"]), **{k: float(r[k]) for k in CHAMPS}}
            for r in csv.DictReader(f)
            if r["fichier"] in vus
        ]
    retablis = list(carnet.retablis().values())

    dossier = args.sortie / "pdf"
    dossier.mkdir(parents=True, exist_ok=True)
    lignes = []
    for t in tirage:
        fichier = t["fichier"]
        ligne = {
            "fichier": fichier,
            "commune": t["commune"],
            "departement": t["departement"],
            "position": t["position"],
            "statut": "à délimiter",
            "rang": "",
            "contributions": "",
            "page_debut": "",
            "page_fin": "",
            "fin": "",
            "caviardages": "",
            "pdf": "",
        }
        lignes.append(ligne)
        if fichier not in vus:
            continue
        ns = par_cahier[fichier]
        with pymupdf.open(chemins[fichier]) as doc:
            derniere = doc.page_count
        debuts = [(n["page"], ordonnee(n)) for n in ns if n["etiquette"] == DEBUT]
        fins = [(n["page"], ordonnee(n)) for n in ns if n["etiquette"] == FIN]
        repetes = doublons(debuts)[1]
        if repetes:
            # un début posé deux fois : un double clic manqué (une fin) ou non
            pages = ", ".join(str(p) for p, _ in repetes)
            ligne["statut"] = f"à vérifier : débuts en double p. {pages}"
            continue
        contribution = tiree(float(t["position"]), debuts, fins, derniere)
        if contribution is None:
            ligne["statut"] = "vu sans début noté"
            continue
        pages = set(contribution.pages)
        notes_a_cacher = [
            {**n, **{k: v for k, v in zip(CHAMPS, cadre(n))}}
            for n in ns
            if n["etiquette"] in A_CACHER and n["page"] in pages
        ]
        masques = a_masquer(
            fusionner(
                [r for r in reperes if r["fichier"] == fichier and r["page"] in pages]
            ),
            [r for r in retablis if r["fichier"] == fichier],
            notes_a_cacher,
        )
        noirs = defaultdict(list)
        for m in masques:
            noirs[m["page"]].append(cadre(m))
        nom = f"{Path(fichier).stem}.pdf"
        total = caviarder(chemins[fichier], dossier / nom, contribution, noirs, fichier)
        ligne |= {
            "statut": "exporté",
            "rang": contribution.rang,
            "contributions": contribution.n,
            "page_debut": contribution.page_debut,
            "page_fin": contribution.page_fin,
            "fin": "notée" if contribution.fin_notee else "déduite",
            "caviardages": total,
            "pdf": f"pdf/{nom}",
        }

    with (args.sortie / "selection.csv").open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, list(lignes[0]))
        ecrivain.writeheader()
        ecrivain.writerows(lignes)
    exportes = [x for x in lignes if x["statut"] == "exporté"]
    print(f"{len(exportes)} contributions exportées sur {len(lignes)} cahiers tirés")
    print(f"  pages : {sum(x['page_fin'] - x['page_debut'] + 1 for x in exportes)}")
    print(f"  cadres caviardés : {sum(x['caviardages'] for x in exportes)}")
    print(f"  sans caviardage : {sum(1 for x in exportes if not x['caviardages'])}")
    a_verifier = [x for x in lignes if x["statut"].startswith("à vérifier")]
    print(f"  à vérifier (débuts en double) : {len(a_verifier)}")
    for statut in ("vu sans début noté", "à délimiter"):
        print(f"  {statut} : {sum(1 for x in lignes if x['statut'] == statut)}")
    print(f"PDF dans {dossier}")


if __name__ == "__main__":
    main()
