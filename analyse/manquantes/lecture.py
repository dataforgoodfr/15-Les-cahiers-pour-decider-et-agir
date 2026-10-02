"""Lecture des PDF par les processus de travail (importable, donc picklable)."""

from pathlib import Path

import pymupdf

from manquantes.manquantes import decrire, lignes

_partage = {}


def initialiser(valeurs: dict) -> None:
    """Données communes à tous les fichiers : lignes fréquentes, modèles."""
    _partage.update(valeurs)


def textes(chemin: Path) -> list[str]:
    with pymupdf.open(chemin) as doc:
        return [page.get_text() for page in doc]


def lignes_du_fichier(chemin: Path) -> set[str]:
    return set().union(*map(lignes, textes(chemin)))


def pages_frequentes(chemin: Path) -> tuple[str, list[set[str]]]:
    frequentes = _partage["frequentes"]
    return chemin.name, [lignes(t) & frequentes for t in textes(chemin)]


def exemplaires_du_fichier(chemin: Path):
    ts = textes(chemin)
    return [e for m in _partage["modeles"] for e in decrire(chemin.name, ts, m)]
