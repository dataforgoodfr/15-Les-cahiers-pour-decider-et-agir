"""Pages d'ouverture imprimées des cahiers (issue #5).

Dans certains départements, les communes ont reçu un cahier dont la première
page est imprimée : en Charente-Maritime, celle de l'association des maires
(« Cahier de doléances et de propositions… »), en Gironde, dans le Nord… Ce
n'est pas une contribution : l'édition Chabin ne la transcrit pas, et sa
première contribution commence à la page suivante. Le typage la voit
dactylographiée et ne la marque pas comme page de service.

Elle se reconnaît à deux traits :

- ses lignes reviennent sur la première page écrite de nombreux cahiers du
  même département ;
- ce modèle ne revient pas ailleurs dans le cahier. Un formulaire rempli à la
  main (celui de la Ville de Paris) reprend aussi des lignes communes à tout
  le département, mais une fois par contribution : il revient sur d'autres
  pages du cahier, et ce n'est pas une ouverture.

Un cahier qui ne contient qu'un formulaire rempli échappe au second trait :
on garde alors la page si l'essentiel de son encre est hors du texte
imprimé (`typage.part_hors_texte`), donc écrit à la main. Une couverture n'a
hors du texte que des logos et des cadres.
"""

import re
from collections import Counter, defaultdict
from pathlib import Path

import pymupdf

from panel.panel import lire_typage
from typage.typage import part_hors_texte

LONGUEUR_LIGNE = 10  # caractères au moins d'une ligne de modèle
PART_CAHIERS = 0.05  # part des cahiers du département où revient une ligne de modèle
CAHIERS_MIN = 10  # et au moins ce nombre de cahiers
LIGNES_MIN = 2  # lignes du modèle sur une page qui le porte
PAGE_MAX = 5  # la première page écrite est cherchée parmi les premières
# part de l'encre hors du texte au-delà de laquelle la page est remplie à la
# main : 0,27 à 0,58 sur les couvertures, 0,64 et 0,81 sur le formulaire de Paris
ENCRE_MAX = 0.6
DACTYLOGRAPHIEE = "dactylographiée"


def normaliser(ligne: str) -> str:
    """Minuscules et mots seuls : la ponctuation varie d'un OCR à l'autre."""
    return " ".join(re.sub(r"\W+", " ", ligne.lower()).split())


def lignes_de_page(texte: str) -> set[str]:
    return {
        x
        for x in (normaliser(ligne) for ligne in texte.splitlines())
        if len(x) > LONGUEUR_LIGNE
    }


def modele(premieres: dict[str, set[str]]) -> set[str]:
    """Lignes qui reviennent sur la première page écrite de nombreux cahiers
    d'un département (`premieres` : lignes de cette page, par cahier)."""
    presences = Counter(x for lignes in premieres.values() for x in lignes)
    seuil = max(CAHIERS_MIN, PART_CAHIERS * len(premieres))
    return {x for x, n in presences.items() if n >= seuil}


def porte(lignes: set[str], lignes_modele: set[str]) -> bool:
    return len(lignes & lignes_modele) >= LIGNES_MIN


def premieres_pages(table: Path) -> dict[str, int]:
    """Première page dactylographiée hors service de chaque cahier citoyen,
    si elle est parmi les premières."""
    pages = defaultdict(list)
    for ligne in lire_typage([table]):
        if (
            ligne["fichier"].startswith("CC")
            and ligne["type_page"] == DACTYLOGRAPHIEE
            and ligne["page_de_service"] != "1"
        ):
            pages[ligne["fichier"]].append(int(ligne["page"]))
    return {f: min(p) for f, p in pages.items() if min(p) <= PAGE_MAX}


def departement(travail: tuple[Path, dict[str, Path]]) -> tuple[str, int, list]:
    """(département, cahiers lus, pages d'ouverture (fichier, page))."""
    table, chemins = travail
    premieres = {f: p for f, p in premieres_pages(table).items() if f in chemins}
    lignes = {}
    for f, p in premieres.items():
        with pymupdf.open(chemins[f]) as doc:
            lignes[f] = lignes_de_page(doc[p - 1].get_text())
    lignes_modele = modele(lignes)
    ouvertures = []
    for f, p in sorted(premieres.items()):
        if not porte(lignes[f], lignes_modele):
            continue
        with pymupdf.open(chemins[f]) as doc:
            ailleurs = any(
                porte(lignes_de_page(doc[n - 1].get_text()), lignes_modele)
                for n in range(1, doc.page_count + 1)
                if n != p
            )
            remplie = part_hors_texte(doc[p - 1]) >= ENCRE_MAX
        if not ailleurs and not remplie:
            ouvertures.append((f, p))
    return table.stem, len(premieres), ouvertures
