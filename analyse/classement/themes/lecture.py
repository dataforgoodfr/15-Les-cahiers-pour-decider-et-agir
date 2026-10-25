"""Lecture de la couche texte des cahiers, pour le repérage des sous-thèmes.

À part du point d'entrée : les processus parallèles de `classement.themes` doivent
pouvoir importer `cahier`.
"""

from collections import Counter

import pymupdf

from classement.themes.sous_themes import normaliser, sous_themes

REPETEE = 3  # occurrences d'une ligne dans un cahier pour la tenir imprimée
TEXTE_MIN = 200  # caractères au moins pour qu'un texte compte


def lignes_imprimees(pages: list[list[str]]) -> set[str]:
    """Les lignes normalisées qui reviennent `REPETEE` fois dans le cahier."""
    compte = Counter(
        x for page in pages for x in {normaliser(t) for t in page} if len(x) > 15
    )
    return {x for x, n in compte.items() if n >= REPETEE}


def lignes_de_page(page: pymupdf.Page, haut=None, bas=None) -> list[str]:
    """Les lignes de la couche texte, entre deux hauteurs du PDF non tourné
    (sur une page non tournée seulement ; sinon toute la page)."""
    sortie = []
    for bloc in page.get_text("dict")["blocks"]:
        for ligne in bloc.get("lines", []):
            y = ligne["bbox"][1]
            if page.rotation == 0 and (
                (haut is not None and y < haut - 6) or (bas is not None and y > bas)
            ):
                continue
            sortie.append("".join(s["text"] for s in ligne["spans"]))
    return sortie


def texte(lignes: list[str], imprimees: set[str]) -> str:
    return "\n".join(x for x in lignes if normaliser(x) not in imprimees)


def cahier(args) -> tuple[str, set[str]] | None:
    fichier, chemin, numeros = args
    try:
        with pymupdf.open(chemin) as doc:
            pages = [lignes_de_page(doc[n - 1]) for n in numeros]
    except pymupdf.FileDataError, RuntimeError:  # PDF illisible
        return None
    imprimees = lignes_imprimees(pages)
    t = texte([x for p in pages for x in p], imprimees)
    if len(t) < TEXTE_MIN:
        return None
    return fichier, sous_themes(t)
