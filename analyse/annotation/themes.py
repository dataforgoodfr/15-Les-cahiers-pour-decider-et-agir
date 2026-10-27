"""Sous-thèmes des propositions à revoir (issue #24), sortie de `python -m classement.themes.revue`.

Pour chaque proposition, l'annotateur coche, dans toute la grille, les
sous-thèmes qu'elle traite. Il la lit dans sa contribution et voit la page
de l'édition Chabin où elle se trouve ; il ne sait pas ce qu'ont repéré les
mots-clés ou un LLM, ni ce qu'ont coché les autres. Une proposition mal
coupée se signale.

Les annotations vont dans un journal JSONL en ajout seul, comme les
jugements des paires (`annotation.paires`) : la dernière annotation d'un
annotateur sur une proposition l'emporte, une annotation vide (`None`) la
retire. Une liste vide dit qu'aucun sous-thème n'est traité.
"""

import csv
import json
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

import pymupdf

from annotation.paires import Journal
from classement.themes.sous_themes import THEMES, TOUS

NOMS = [nom for nom, _, _ in TOUS]


def lire_revue(chemin: Path) -> list[dict]:
    """Les contributions, dans l'ordre du tirage, et leurs propositions avec
    leur place dans le PDF de l'édition : ce que voit l'annotateur."""
    if not chemin.exists():
        return []
    contributions: dict[str, dict] = {}
    with chemin.open(encoding="utf-8", newline="") as f:
        for x in csv.DictReader(f):
            c = contributions.setdefault(
                x["contribution"],
                {
                    "contribution": x["contribution"],
                    "commune": x["commune"],
                    "pdf": x["pdf"],
                    "propositions": [],
                },
            )
            c["propositions"].append(
                {
                    "proposition": x["proposition"],
                    "contexte": x["contexte"],
                    "texte": x["texte"],
                    "page": int(x["page"]),
                    "largeur": float(x["largeur"]),
                    "hauteur": float(x["hauteur"]),
                    "cadres": json.loads(x["cadres"]),
                }
            )
    return list(contributions.values())


def grille() -> list[dict]:
    """Les sous-thèmes groupés par thème, dans l'ordre de la grille ; un
    sous-thème de plusieurs thèmes va sous le premier."""
    groupes: dict[str, list[str]] = {}
    for nom, codes, _ in TOUS:
        groupes.setdefault(codes[0], []).append(nom)
    return [{"theme": THEMES[c], "sous_themes": noms} for c, noms in groupes.items()]


@lru_cache(maxsize=64)
def image(chemin: Path, page: int, largeur: int) -> bytes:
    with pymupdf.open(chemin) as doc:
        p = doc[page - 1]  # IndexError : page hors du PDF
        zoom = largeur / p.rect.width
        return p.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom)).tobytes("jpeg")


class JournalThemes(Journal):
    def annoter(
        self,
        proposition: str,
        annotateur: str,
        sous_themes: list[str] | None,
        mal_coupee: bool = False,
    ) -> dict:
        annotateur = annotateur.strip()
        if not annotateur:
            raise ValueError("annotateur sans nom")
        if sous_themes is not None and not set(sous_themes) <= set(NOMS):
            raise ValueError("sous-thème hors de la grille")
        evenement = {
            "type": "sous-thèmes",
            "proposition": str(proposition),
            "annotateur": annotateur,
            "sous_themes": None if sous_themes is None else sorted(set(sous_themes)),
            "mal_coupee": bool(mal_coupee),
            "cree": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        with self.verrou:
            self.chemin.parent.mkdir(parents=True, exist_ok=True)
            with self.chemin.open("a", encoding="utf-8") as f:
                f.write(json.dumps(evenement, ensure_ascii=False) + "\n")
        return evenement


def etat(evenements: list[dict]) -> dict[str, dict[str, dict]]:
    """Annotations {proposition: {annotateur: {"sous_themes": set,
    "mal_coupee": bool}}}. Les annotations par contribution entière, d'une
    version précédente de la tâche, sont ignorées."""
    annotations: dict[str, dict[str, dict]] = {}
    for e in sorted(evenements, key=lambda e: e["cree"]):
        if "proposition" not in e:
            continue
        par = annotations.setdefault(e["proposition"], {})
        if e["sous_themes"] is None:
            par.pop(e["annotateur"], None)
        else:
            par[e["annotateur"]] = {
                "sous_themes": set(e["sous_themes"]),
                "mal_coupee": e.get("mal_coupee", False),
            }
    return annotations
