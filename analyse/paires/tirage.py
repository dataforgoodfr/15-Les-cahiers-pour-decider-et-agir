"""Tirage des paires de propositions, par tranches de ressemblance."""

import random
import re
from collections import Counter

import numpy as np

VOISINS = 10  # voisins les plus proches de chaque proposition
BLOC = 1024  # lignes de la matrice de similarité calculées à la fois
HASARD = "hasard"
REGLAGE, TEST = "réglage", "test"

NON_MOT = re.compile(r"\W+")


def normaliser(texte: str) -> str:
    """Le texte sans casse ni ponctuation, pour repérer les copies."""
    return NON_MOT.sub(" ", texte.casefold()).strip()


def voisins(
    vecteurs: np.ndarray, groupes: list, k: int = VOISINS, bloc: int = BLOC
) -> dict[tuple[int, int], float]:
    """Paires (i, j), i < j, où j est l'un des `k` plus proches voisins de i
    (ou l'inverse), hors même groupe, avec leur similarité cosinus."""
    groupes_ = np.array([hash(g) for g in groupes])
    paires = {}
    for debut in range(0, len(vecteurs), bloc):
        sim = vecteurs[debut : debut + bloc] @ vecteurs.T
        lignes = np.arange(debut, min(debut + bloc, len(vecteurs)))
        sim[groupes_[lignes, None] == groupes_[None, :]] = -np.inf
        k_ = min(k, sim.shape[1])
        proches = np.argpartition(-sim, k_ - 1, axis=1)[:, :k_]
        for r, i in enumerate(lignes):
            for j in proches[r]:
                if np.isfinite(sim[r, j]):
                    paires[min(i, j), max(i, j)] = float(sim[r, j])
    return paires


def tranches(similarites: list[float], n: int) -> list[float]:
    """Les `n - 1` bornes qui coupent les similarités en `n` tranches de
    même effectif."""
    return [float(b) for b in np.quantile(similarites, np.arange(1, n) / n)]


def tirer(
    vecteurs: np.ndarray,
    groupes: list,
    textes: list[str],
    n_tranches: int = 5,
    par_tranche: int = 100,
    hasard: int = 100,
    graine: int = 0,
    k: int = VOISINS,
) -> list[dict]:
    """Les paires tirées : `par_tranche` dans chacune des `n_tranches`
    tranches de ressemblance des voisins, et `hasard` au hasard. Une
    proposition n'entre que dans une paire ; deux textes identiques n'en font
    pas une."""
    alea = random.Random(graine)
    normes = [normaliser(t) for t in textes]
    candidats = {
        p: s
        for p, s in voisins(vecteurs, groupes, k).items()
        if normes[p[0]] != normes[p[1]]
    }
    pris: set[int] = set()
    tirees = []
    if candidats:
        bornes = tranches(list(candidats.values()), n_tranches)
        par = [[] for _ in range(n_tranches)]
        for p, s in sorted(candidats.items()):
            par[sum(s > b for b in bornes)].append(p)
        for t, liste in enumerate(par, 1):
            alea.shuffle(liste)
            n = 0
            for i, j in liste:
                if n == par_tranche:
                    break
                if i in pris or j in pris:
                    continue
                pris |= {i, j}
                tirees.append(
                    {"i": i, "j": j, "tranche": str(t), "similarite": candidats[i, j]}
                )
                n += 1
    libres = [i for i in range(len(textes)) if i not in pris]
    alea.shuffle(libres)
    n = 0
    while n < hasard and len(libres) >= 2:
        i = libres.pop()
        j = next(
            (
                j
                for j in reversed(libres)
                if groupes[j] != groupes[i] and normes[j] != normes[i]
            ),
            None,
        )
        if j is None:
            continue
        libres.remove(j)
        i, j = min(i, j), max(i, j)
        tirees.append(
            {
                "i": i,
                "j": j,
                "tranche": HASARD,
                "similarite": float(vecteurs[i] @ vecteurs[j]),
            }
        )
        n += 1
    return tirees


def lots(tirees: list[dict], reglage: float, graine: int = 0) -> list[dict]:
    """Chaque paire dans le lot de réglage ou de test, en même part dans
    chaque tranche."""
    alea = random.Random(graine)
    par_tranche: dict[str, list[dict]] = {}
    for p in tirees:
        par_tranche.setdefault(p["tranche"], []).append(p)
    for liste in par_tranche.values():
        alea.shuffle(liste)
        n = round(len(liste) * reglage)
        for rang, p in enumerate(liste):
            p["lot"] = REGLAGE if rang < n else TEST
    return tirees


def comptes(tirees: list[dict]) -> Counter:
    return Counter((p["tranche"], p["lot"]) for p in tirees)
