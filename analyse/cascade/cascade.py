"""Cascade du corpus : du versement BnF aux pages écrites des cahiers citoyens.

Trois niveaux, chacun ne garde qu'une partie du précédent :

1. le **versement** : toutes les pages numérisées, par catégorie (CC, CO, CR,
   IL), comptées dans les PDF ;
2. les **cahiers citoyens** (CC) : leurs pages, moins celles ajoutées à la
   numérisation et les pages vierges, d'après le typage (issue #17) ;
3. les **pages écrites** : dactylographiées, mixtes (formulaires remplis à la
   main) ou manuscrites.

Des comptes, jamais de texte.
"""

import csv
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pymupdf

CATEGORIES = {
    "CC": "cahiers citoyens (CC)",
    "CO": "courriers (CO)",
    "CR": "réunions (CR)",
    "IL": "réunions par courriel (IL)",
}
_CATEGORIE = re.compile(r"^(CC|CO|CR|IL)_")

SERVICE = "ajoutées à la numérisation"
VIERGES = "vierges"
ECRITES = "écrites"
DACTYLOGRAPHIEES = "dactylographiées"
MANUSCRITES = "manuscrites"
MIXTES = "mixtes"


@dataclass
class Segment:
    libelle: str
    pages: int
    suite: bool  # la partie qui passe au niveau suivant


@dataclass
class Niveau:
    titre: str
    segments: list[Segment]

    @property
    def pages(self) -> int:
        return sum(s.pages for s in self.segments)


def categorie(nom: str) -> str | None:
    m = _CATEGORIE.match(nom)
    return m.group(1) if m else None


def compter_versement(racine: Path) -> tuple[Counter, Counter]:
    """Documents et pages par catégorie, dans l'arborescence du versement."""
    documents, pages = Counter(), Counter()
    for pdf in racine.rglob("*.pdf"):
        cat = categorie(pdf.name)
        if cat is None:
            continue  # inventaires et documents d'accompagnement
        with pymupdf.open(pdf) as doc:
            pages[cat] += doc.page_count
        documents[cat] += 1
    return documents, pages


def lire_typage(chemins: list[Path]) -> Counter:
    """Pages des cahiers citoyens par destin : ajoutée, vierge ou type d'écriture."""
    compte = Counter()
    fichiers = []
    for chemin in chemins:
        fichiers += sorted(chemin.glob("*.csv")) if chemin.is_dir() else [chemin]
    for fichier in fichiers:
        with fichier.open(encoding="utf-8", newline="") as f:
            for ligne in csv.DictReader(f):
                if categorie(ligne["fichier"]) != "CC":
                    continue
                if ligne["page_de_service"] == "1":
                    compte[SERVICE] += 1
                elif ligne["type_page"] == "vierge":
                    compte[VIERGES] += 1
                elif ligne["type_page"] == "manuscrite":
                    compte[MANUSCRITES] += 1
                elif ligne["type_page"] == "mixte":
                    compte[MIXTES] += 1
                else:
                    compte[DACTYLOGRAPHIEES] += 1
    return compte


def niveaux(pages: Counter, typage: Counter) -> list[Niveau]:
    ecrites = typage[DACTYLOGRAPHIEES] + typage[MIXTES] + typage[MANUSCRITES]
    return [
        Niveau(
            "Versement BnF",
            [Segment(CATEGORIES["CC"], pages["CC"], True)]
            + [Segment(CATEGORIES[c], pages[c], False) for c in ("CO", "CR", "IL")],
        ),
        Niveau(
            "Cahiers citoyens",
            [
                Segment(ECRITES, ecrites, True),
                Segment(VIERGES, typage[VIERGES], False),
                Segment(SERVICE, typage[SERVICE], False),
            ],
        ),
        Niveau(
            "Pages écrites",
            [
                Segment(DACTYLOGRAPHIEES, typage[DACTYLOGRAPHIEES], True),
                Segment(MIXTES, typage[MIXTES], True),
                Segment(MANUSCRITES, typage[MANUSCRITES], True),
            ],
        ),
    ]


def milliers(n: int) -> str:
    return f"{n:,}".replace(",", "\u202f")


def pourcent(part: float) -> str:
    return f"{part * 100:.0f}\u202f%"


def ecrire_csv(chemin: Path, cascade: list[Niveau], documents: Counter) -> None:
    documents_par_libelle = {CATEGORIES[c]: n for c, n in documents.items()}
    with chemin.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(["niveau", "segment", "pages", "part", "documents"])
        for niveau in cascade:
            for s in niveau.segments:
                ecrivain.writerow(
                    [
                        niveau.titre,
                        s.libelle,
                        s.pages,
                        f"{s.pages / niveau.pages:.3f}" if niveau.pages else "",
                        documents_par_libelle.get(s.libelle, "")
                        if niveau is cascade[0]
                        else "",
                    ]
                )


# Figure : SVG écrit à la main, sans dépendance. Couleurs en classes CSS pour
# suivre le thème clair ou sombre de la page qui l'affiche.
LARGEUR = 900
MARGE_GAUCHE = 170
LARGEUR_BARRES = LARGEUR - MARGE_GAUCHE - 20
HAUTEUR_BARRE = 34
PAS = 96
HAUT = 56

_STYLE = """
  .fond { fill: #ffffff; }
  text { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; fill: #1f1f1f; }
  .titre { font-size: 17px; font-weight: 600; }
  .niveau { font-size: 14px; font-weight: 600; }
  .total { font-size: 12px; fill: #5a5a5a; }
  .libelle { font-size: 12px; }
  .note { font-size: 11px; fill: #5a5a5a; }
  .suite0 { fill: #2a6fbf; }
  .suite1 { fill: #8db8e8; }
  .ecarte { fill: #d9d9d6; }
  .lien { fill: #2a6fbf; opacity: 0.12; }
  @media (prefers-color-scheme: dark) {
    .fond { fill: #161b22; }
    text { fill: #e6e6e6; }
    .total, .note { fill: #a8a8a8; }
    .suite0 { fill: #4a8fdf; }
    .suite1 { fill: #2b5c94; }
    .ecarte { fill: #3a3a38; }
    .lien { fill: #4a8fdf; opacity: 0.18; }
  }
"""


def _tient(texte: str, largeur: float) -> bool:
    """Le libellé tient-il au-dessus du segment ? (~6 px par caractère en 12 px)"""
    return len(texte) * 6 + 8 <= largeur


def svg(cascade: list[Niveau], date: str) -> str:
    echelle = LARGEUR_BARRES / cascade[0].pages
    hauteur = HAUT + PAS * len(cascade) + 40
    morceaux = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{LARGEUR}" '
            f'height="{hauteur}" viewBox="0 0 {LARGEUR} {hauteur}" role="img" '
            'aria-labelledby="titre">'
        ),
        f"<style>{_STYLE}</style>",
        f'<rect class="fond" width="{LARGEUR}" height="{hauteur}"/>',
        (
            '<text id="titre" class="titre" x="16" y="30">'
            "Du versement BnF aux pages écrites des cahiers citoyens</text>"
        ),
    ]
    debut_suivant = None
    for i, niveau in enumerate(cascade):
        y = HAUT + PAS * i
        if debut_suivant is not None:
            # bande qui relie la partie gardée au niveau suivant
            x0, x1 = debut_suivant
            morceaux.append(
                f'<polygon class="lien" points="{x0:.1f},{y - PAS + HAUTEUR_BARRE + 22} '
                f"{x1:.1f},{y - PAS + HAUTEUR_BARRE + 22} "
                f"{MARGE_GAUCHE + niveau.pages * echelle:.1f},{y + 20} "
                f'{MARGE_GAUCHE:.1f},{y + 20}"/>'
            )
        morceaux.append(
            f'<text class="niveau" x="16" y="{y + 38}">{niveau.titre}</text>'
        )
        morceaux.append(
            f'<text class="total" x="16" y="{y + 55}">{milliers(niveau.pages)} pages</text>'
        )
        x = MARGE_GAUCHE
        suites = 0
        petits = 0
        for s in niveau.segments:
            largeur = s.pages * echelle
            classe = f"suite{min(suites, 1)}" if s.suite else "ecarte"
            suites += s.suite
            morceaux.append(
                f'<rect class="{classe}" x="{x:.1f}" y="{y + 22}" '
                f'width="{max(largeur - 2, 0.5):.1f}" height="{HAUTEUR_BARRE}" rx="3">'
                f"<title>{s.libelle} : {milliers(s.pages)} pages</title></rect>"
            )
            etiquette = f"{s.libelle} {pourcent(s.pages / niveau.pages)}"
            if _tient(etiquette, largeur):
                morceaux.append(
                    f'<text class="libelle" x="{x + 4:.1f}" y="{y + 16}">'
                    f"{etiquette}</text>"
                )
            elif s.pages:
                # trop étroit : sous la barre, aligné sur la fin du segment,
                # une ligne par libellé pour que deux voisins ne se chevauchent pas
                petits += 1
                morceaux.append(
                    f'<text class="libelle" text-anchor="end" x="{x + largeur - 2:.1f}" '
                    f'y="{y + 22 + HAUTEUR_BARRE + 2 + 14 * petits}">{etiquette}</text>'
                )
            x += largeur
        gardees = [s for s in niveau.segments if s.suite]
        debut_suivant = (
            MARGE_GAUCHE,
            MARGE_GAUCHE + sum(s.pages for s in gardees) * echelle,
        )
    y = HAUT + PAS * len(cascade) + 10
    morceaux.append(
        f'<text class="note" x="16" y="{y}">Pages comptées dans les PDF du versement ; '
        "types de page par l'outil de typage (issue #17) ; mixtes : formulaires "
        f"remplis à la main. État au {date}.</text>"
    )
    morceaux.append("</svg>")
    return "\n".join(morceaux) + "\n"
