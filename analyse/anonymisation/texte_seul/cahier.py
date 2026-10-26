"""Un cahier, dans un processus de `python -m anonymisation.texte_seul`.

Hors de `__main__` : les processus de travail doivent pouvoir importer ces
fonctions. `initialiser` leur donne une fois les références (lexique,
prénoms, noms publics, noms répandus).
"""

from collections import defaultdict
from pathlib import Path

import pymupdf

from anonymisation.__main__ import mots_de_la_page
from anonymisation.blanche import raison
from anonymisation.delimites import DEDANS, _cadre, contribution_de, texte_du_cadre
from anonymisation.detection import mots_personnels
from anonymisation.factices import garde
from anonymisation.masquage import dans
from anonymisation.texte_seul.texte import masquer

ETAPE = 3  # tous les filtres de `factices.garde`, noms répandus compris
_ref: dict = {}


def initialiser(references: dict) -> None:
    """`references` : prénoms (bruts et simplifiés), lexique, noms publics
    par cahier, avec les lieux (`surs`) ou sans (`noms`), commune par
    cahier, noms répandus."""
    _ref.update(references)


def noms(tache: tuple[Path, str, list[int]]) -> list[tuple[str, str]]:
    """Première passe : (étiquette, texte) des noms que les règles repèrent
    dans le cahier, pour compter les communes où chacun revient."""
    chemin, fichier, pages = tache
    sortie = []
    with pymupdf.open(chemin) as doc:
        for n in pages:
            mots = mots_de_la_page(doc[n - 1])
            for r in mots_personnels(
                mots, _ref["communes"].get(fichier, ""), _ref["prenoms"]
            ):
                if r["etiquette"] in ("nom", "prénom"):
                    sortie.append((r["etiquette"], texte_du_cadre(mots, r)))
    return sortie


def anonymiser(tache: tuple[Path, str, list[int], list[dict]]) -> list[dict]:
    """Seconde passe : le texte caché de chaque contribution du cahier.
    `pages` : ses pages imprimées ; `contributions` : les lignes de
    `decoupage.corpus`, en points PDF de la page non tournée."""
    chemin, fichier, pages, contributions = tache
    commune = _ref["communes"].get(fichier, "")
    surs = _ref["surs"][fichier]
    with pymupdf.open(chemin) as doc:
        debuts = []
        for c in contributions:
            pd, pf = int(c["page_debut"]), int(c["page_fin"])
            debut = pymupdf.Point(float(c["x_debut"]), float(c["y_debut"]))
            fin_y = (
                (
                    pymupdf.Point(float(c["x_fin"]), float(c["y_fin"]))
                    * doc[pf - 1].rotation_matrix
                ).y
                if c["y_fin"]
                else float("inf")
            )
            debuts.append(
                (pd, (debut * doc[pd - 1].rotation_matrix).y, pf, fin_y, int(c["rang"]))
            )
        debuts.sort()
        lignes = defaultdict(list)
        for n in pages:
            mots = mots_de_la_page(doc[n - 1])
            regles = [
                r
                for r in mots_personnels(mots, commune, _ref["prenoms"])
                if garde(
                    r | {"texte": texte_du_cadre(mots, r)},
                    ETAPE,
                    _ref["noms"][fichier],
                    _ref["repandus"],
                )
            ]
            par_ligne = defaultdict(list)
            for m in mots:
                par_ligne[m[5], m[6]].append(m)
            for ligne in par_ligne.values():
                ligne.sort(key=lambda m: m[7])
                y0 = min(m[1] for m in ligne)
                rang = contribution_de(debuts, n, y0)
                if rang is None:
                    continue
                lignes[rang].append(
                    (
                        (n, y0, min(m[0] for m in ligne)),
                        [
                            (
                                m[4],
                                any(dans(_cadre(m), r) >= DEDANS for r in regles)
                                or raison(m[4], _ref["lexique"], _ref["simples"], surs)
                                is not None,
                            )
                            for m in ligne
                        ],
                    )
                )
    sortie = []
    for c in contributions:
        rang = int(c["rang"])
        texte, mots, caches = masquer([ligne for _, ligne in sorted(lignes[rang])])
        sortie.append(
            {
                "fichier": fichier,
                "rang": rang,
                "page_debut": c["page_debut"],
                "page_fin": c["page_fin"],
                "mots": mots,
                "caches": caches,
                "texte": texte,
            }
        )
    return sortie
