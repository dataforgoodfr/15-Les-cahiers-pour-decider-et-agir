"""Découpage d'un cahier, dans un processus de `python -m decoupage.corpus`.

Hors de `__main__` : les processus de travail doivent pouvoir importer ces
fonctions.
"""

from pathlib import Path

import pymupdf

from decoupage.contributions import pages as modele
from decoupage.contributions.__main__ import IMPRIMEES, candidates
from decoupage.contributions.regles import debuts
from decoupage.corpus.contributions import Debut, contributions

_modele: modele.Logistique | None = None


def initialiser(chemin: Path) -> None:
    """Charge le modèle, une fois par processus."""
    global _modele
    _modele = modele.Logistique.charger(chemin)


def decouper(tache: tuple[Path, str, list[tuple[int, str]]]) -> list[dict]:
    """Les contributions d'un cahier : règles, puis le modèle sur les pages
    lues où elles ne trouvent rien."""
    chemin, fichier, ecrites = tache
    numeros = [n for n, t in ecrites if t in IMPRIMEES]
    if not numeros:
        return []
    with pymupdf.open(chemin) as doc:
        pages = [(modele.lignes(doc[n - 1]), doc[n - 1].rect) for n in numeros]
        derotation = [doc[n - 1].derotation_matrix for n in numeros]
    trouves = debuts(
        [[x.texte for x in page] for page, _ in pages],
        debut_du_cahier=numeros[0] == ecrites[0][0],
    )
    avec_debut = {p for p, _, _ in trouves}
    candidates_ = candidates(pages, numeros, avec_debut)
    if candidates_:
        x = modele.matrice([d for _, d in candidates_], [fichier] * len(candidates_))
        for (p, _), q in zip(candidates_, _modele.probabilites(x), strict=True):
            if q >= modele.SEUIL:
                page = pages[p][0]
                premiere = min(
                    (i for i, x in enumerate(page) if x.texte.strip()),
                    key=lambda i: (page[i].cadre.y0, page[i].cadre.x0),
                )
                trouves.append((p, premiere, "page"))
    # dans l'ordre de lecture (repère affiché), puis en points PDF
    places = sorted(
        (p, pages[p][0][i].cadre.y0, pages[p][0][i].cadre.x0, i, regle)
        for p, i, regle in trouves
    )
    debuts_ = []
    for p, _, _, i, regle in places:
        cadre = pages[p][0][i].cadre * derotation[p]
        debuts_.append(Debut(numeros[p], round(cadre.x0, 1), round(cadre.y0, 1), regle))
    return [
        {"fichier": fichier, **c, "publiable": 1}
        for c in contributions(debuts_, ecrites)
    ]
