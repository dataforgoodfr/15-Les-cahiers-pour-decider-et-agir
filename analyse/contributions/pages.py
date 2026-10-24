"""Pages qui ouvrent une contribution en leur haut, sans règle (issue #5).

Sur les cahiers délimités, sept débuts manqués par les règles sur dix sont
en haut d'une page où aucune règle ne trouve rien : la question est de
savoir si la page ouvre une contribution ou continue la précédente. Une
régression logistique y répond, sur des indices de forme comparés à la page
lue précédente :

- la mise en page : police, taille du corps et marge qui changent, haut de
  la page où commence le texte, bas de la précédente où il finit ;
- le texte, sans le comprendre : mots communs aux deux pages, première
  ligne courte (un titre) ou en minuscule, date en tête, numéro de page
  au-delà du premier (`regles.suite`), politesse en fin de précédente ;
- la suite des pages : la page lue précédente est-elle la page d'avant dans
  le fichier, ou une page que les règles ne lisent pas (manuscrite,
  vierge) s'intercale-t-elle ?

Chaque cahier a ses habitudes (certains changent de police à chaque page) :
les indices de mise en page comptent aussi par leur rang dans le cahier.

Le modèle n'est fait que de poids : il s'entraîne en quelques secondes, sur
CPU, sur les cahiers délimités à la main. Il ne voit que des nombres et
ne rend que des probabilités.
"""

import math
import re
import statistics
from collections import Counter
from dataclasses import dataclass

import numpy as np
import pymupdf

from contributions.regles import POLITESSE, TOLERANCE, suite

MOT = re.compile(r"[a-zà-ÿ]{4,}")
DATE = re.compile(
    r"\b(19|20)\d\d\b|janvier|f[ée]vrier|mars|avril|\d{1,2}/\d{1,2}/\d{2,4}",
    re.IGNORECASE,
)
LIGNES_TETE = 4  # premières lignes où chercher une date
LIGNES_FIN = 10  # dernières lignes de la précédente où chercher la politesse
TITRE = 40  # caractères au plus d'une première ligne qui fait titre
INDICES = (
    "contigue",
    "remplissage_precedente",
    "haut",
    "premiere_courte",
    "minuscule",
    "marge",
    "taille",
    "police",
    "mots_communs",
    "rapport_mots",
    "suite",
    "date",
    "politesse",
)
# indices de mise en page qui comptent aussi par leur rang dans le cahier
RANGS = (
    "remplissage_precedente",
    "marge",
    "taille",
    "police",
    "mots_communs",
    "rapport_mots",
)
SEUIL = 0.5  # probabilité à partir de laquelle une page ouvre une contribution
HAUT = 0.2  # part de la page : une note de début au-dessus ouvre la page


@dataclass
class Ligne:
    texte: str
    cadre: pymupdf.Rect
    police: str
    taille: float


def lignes(page: pymupdf.Page) -> list[Ligne]:
    """Lignes de la couche texte, dans l'ordre de `contributions.__main__.lignes`,
    avec la police et la taille de leur plus long fragment."""
    sortie = []
    for bloc in page.get_text("dict")["blocks"]:
        for ligne in bloc.get("lines", []):
            spans = ligne["spans"]
            principal = max(spans, key=lambda s: len(s["text"]), default=None)
            sortie.append(
                Ligne(
                    "".join(s["text"] for s in spans),
                    pymupdf.Rect(ligne["bbox"]) * page.rotation_matrix,
                    principal["font"] if principal else "",
                    principal["size"] if principal else 0.0,
                )
            )
    return sortie


def _ecrites(page: list[Ligne]) -> list[Ligne]:
    return sorted(
        (x for x in page if x.texte.strip()), key=lambda x: (x.cadre.y0, x.cadre.x0)
    )


def indices(
    precedente: list[Ligne],
    page: list[Ligne],
    hauteur: float,
    largeur: float,
    hauteur_precedente: float,
    contigue: bool,
) -> dict[str, float] | None:
    """Indices d'une page contre la page lue qui la précède (None si l'une des
    deux est sans texte). `contigue` : les deux pages se suivent dans le fichier."""
    cour, prec = _ecrites(page), _ecrites(precedente)
    if not cour or not prec:
        return None
    mots_cour = set(MOT.findall(" ".join(x.texte for x in cour).lower()))
    mots_prec = set(MOT.findall(" ".join(x.texte for x in prec).lower()))
    union = mots_cour | mots_prec
    premiere = cour[0].texte.strip()
    return {
        "contigue": float(contigue),
        "remplissage_precedente": max(x.cadre.y1 for x in prec) / hauteur_precedente,
        "haut": cour[0].cadre.y0 / hauteur,
        "premiere_courte": float(len(premiere) < TITRE),
        "minuscule": float(premiere[:1].islower()),
        "marge": abs(
            statistics.median(x.cadre.x0 for x in cour)
            - statistics.median(x.cadre.x0 for x in prec)
        )
        / largeur,
        "taille": abs(
            statistics.median(x.taille for x in cour)
            - statistics.median(x.taille for x in prec)
        ),
        "police": float(
            Counter(x.police for x in cour).most_common(1)[0][0]
            != Counter(x.police for x in prec).most_common(1)[0][0]
        ),
        "mots_communs": len(mots_cour & mots_prec) / len(union) if union else 0.0,
        "rapport_mots": math.log((len(mots_cour) + 1) / (len(mots_prec) + 1)),
        "suite": float(suite([x.texte for x in page])),
        "date": float(any(DATE.search(x.texte) for x in cour[:LIGNES_TETE])),
        "politesse": float(any(POLITESSE.search(x.texte) for x in prec[-LIGNES_FIN:])),
    }


def ouvre(page: list[Ligne], hauteur: float, notes: list[float]) -> bool:
    """La page ouvre une contribution en son haut : une note de début (son
    ordonnée) tombe dans le premier cinquième de la page, ou à moins de
    `TOLERANCE` points de sa première ligne."""
    cour = _ecrites(page)
    haut = max(HAUT * hauteur, (cour[0].cadre.y0 if cour else 0) + TOLERANCE)
    return any(y <= haut for y in notes)


def matrice(lignes_indices: list[dict[str, float]], cahiers: list[str]) -> np.ndarray:
    """Les indices en colonnes, plus le rang des indices de `RANGS` parmi les
    pages candidates de leur cahier (entre 0 et 1)."""
    x = np.array([[d[k] for k in INDICES] for d in lignes_indices], dtype=float)
    rangs = np.full((len(x), len(RANGS)), 0.5)
    groupes = np.array(cahiers)
    for cahier in dict.fromkeys(cahiers):
        i = np.flatnonzero(groupes == cahier)
        if len(i) < 2:
            continue
        for j, nom in enumerate(RANGS):
            valeurs = x[i, INDICES.index(nom)]
            rangs[i, j] = np.argsort(np.argsort(valeurs)) / (len(i) - 1)
    return np.hstack([x, rangs])


class Logistique:
    """Régression logistique régularisée (L2), par descente de gradient sur
    des indices centrés réduits."""

    def __init__(self, l2: float = 1.0, tours: int = 3000, pas: float = 0.1):
        self.l2, self.tours, self.pas = l2, tours, pas

    def entrainer(self, x: np.ndarray, y: np.ndarray) -> Logistique:
        self.moyenne, self.ecart = x.mean(0), x.std(0) + 1e-9
        z = (x - self.moyenne) / self.ecart
        self.poids, self.biais = np.zeros(z.shape[1]), 0.0
        for _ in range(self.tours):
            p = 1 / (1 + np.exp(-(z @ self.poids + self.biais)))
            self.poids -= self.pas * (z.T @ (p - y) + self.l2 * self.poids) / len(y)
            self.biais -= self.pas * (p - y).mean()
        return self

    def probabilites(self, x: np.ndarray) -> np.ndarray:
        z = (x - self.moyenne) / self.ecart
        return 1 / (1 + np.exp(-(z @ self.poids + self.biais)))


def validation_croisee(
    x: np.ndarray, y: np.ndarray, cahiers: list[str], plis: int = 5, graine: int = 0
) -> np.ndarray:
    """Probabilités de chaque page par un modèle qui n'a pas vu son cahier."""
    distincts = list(dict.fromkeys(cahiers))
    np.random.default_rng(graine).shuffle(distincts)
    groupes = np.array(cahiers)
    sortie = np.zeros(len(y))
    for pli in np.array_split(np.array(distincts), plis):
        test = np.isin(groupes, pli)
        if test.all() or not test.any():
            continue
        modele = Logistique().entrainer(x[~test], y[~test])
        sortie[test] = modele.probabilites(x[test])
    return sortie
