"""Jugements des paires de propositions (issue #94), sortie de `python -m classement.paires`.

Chaque annotateur juge seul chaque paire : il ne voit ni la tranche, ni la
similarité, ni les jugements des autres. Une paire est en litige quand ses
deux premiers annotateurs ne sont pas d'accord ; un troisième, qui ne l'a pas
jugée, l'adjuge en voyant les deux jugements.

Les jugements vont dans un journal JSONL en ajout seul, comme le carnet des
notes (`annotation.carnet`) : le dernier jugement d'un annotateur sur une
paire l'emporte, un jugement vide le retire. Un annotateur peut travailler sur
sa machine : `accord` lit plusieurs journaux.
"""

import csv
import json
import threading
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

JUGEMENTS = (
    "même proposition",
    "même sujet, mesure différente",
    "sans rapport",
    # témoignage, constat, ou proposition mal coupée : pas jugeable
    "pas une proposition",
)
JUGER, ADJUGER = "jugement", "adjudication"
CHAMPS = ("contexte", "texte")


def lire_paires(chemin: Path) -> list[dict]:
    """Les paires, sans lot, tranche ni similarité : ce que voit
    l'annotateur."""
    if not chemin.exists():
        return []
    with chemin.open(encoding="utf-8", newline="") as f:
        return [
            {
                "paire": x["paire"],
                "a": {c: x[f"a_{c}"] for c in CHAMPS},
                "b": {c: x[f"b_{c}"] for c in CHAMPS},
            }
            for x in csv.DictReader(f)
        ]


class Journal:
    def __init__(self, chemin: Path):
        self.chemin = chemin
        self.verrou = threading.Lock()

    def evenements(self) -> list[dict]:
        if not self.chemin.exists():
            return []
        with self.chemin.open(encoding="utf-8") as f:
            return [json.loads(ligne) for ligne in f if ligne.strip()]

    def juger(
        self, paire: str, annotateur: str, jugement: str | None, role: str = JUGER
    ) -> dict:
        annotateur = annotateur.strip()
        if not annotateur:
            raise ValueError("annotateur sans nom")
        if jugement not in (*JUGEMENTS, None) or role not in (JUGER, ADJUGER):
            raise ValueError(f"jugement inconnu : {role} {jugement}")
        evenement = {
            "type": role,
            "paire": str(paire),
            "annotateur": annotateur,
            "jugement": jugement,
            "cree": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        with self.verrou:
            self.chemin.parent.mkdir(parents=True, exist_ok=True)
            with self.chemin.open("a", encoding="utf-8") as f:
                f.write(json.dumps(evenement, ensure_ascii=False) + "\n")
        return evenement


def etat(evenements: list[dict]) -> tuple[dict, dict]:
    """Jugements {paire: {annotateur: jugement}}, dans l'ordre du premier
    jugement de chacun, et adjudications {paire: (annotateur, jugement)}."""
    jugements: dict[str, dict[str, str]] = {}
    adjudications: dict[str, tuple[str, str]] = {}
    for e in sorted(evenements, key=lambda e: e["cree"]):
        if e["type"] == JUGER:
            par = jugements.setdefault(e["paire"], {})
            if e["jugement"]:
                par[e["annotateur"]] = e["jugement"]
            else:
                par.pop(e["annotateur"], None)
        elif e["type"] == ADJUGER:
            if e["jugement"]:
                adjudications[e["paire"]] = (e["annotateur"], e["jugement"])
            else:
                adjudications.pop(e["paire"], None)
    return jugements, adjudications


def litiges(jugements: dict) -> dict[str, list[tuple[str, str]]]:
    """Les paires dont les deux premiers annotateurs ne sont pas d'accord."""
    sortie = {}
    for paire, par in jugements.items():
        deux = list(par.items())[:2]
        if len(deux) == 2 and deux[0][1] != deux[1][1]:
            sortie[paire] = deux
    return sortie


def kappa(couples: list[tuple[str, str]]) -> float | None:
    """Kappa de Cohen de deux annotateurs sur les mêmes paires."""
    n = len(couples)
    if not n:
        return None
    observe = sum(a == b for a, b in couples) / n
    gauche = Counter(a for a, _ in couples)
    droite = Counter(b for _, b in couples)
    attendu = sum(gauche[c] * droite[c] for c in gauche) / n**2
    return 1.0 if attendu == 1 else (observe - attendu) / (1 - attendu)


def retenus(jugements: dict, adjudications: dict) -> dict[str, str]:
    """Le jugement retenu de chaque paire : celui de ses deux premiers
    annotateurs s'ils s'accordent, sinon l'adjudication. Une paire jugée une
    seule fois n'en a pas encore."""
    sortie = {}
    for paire, par in jugements.items():
        deux = list(par.values())[:2]
        if paire in adjudications:
            sortie[paire] = adjudications[paire][1]
        elif len(deux) == 2 and deux[0] == deux[1]:
            sortie[paire] = deux[0]
    return sortie
