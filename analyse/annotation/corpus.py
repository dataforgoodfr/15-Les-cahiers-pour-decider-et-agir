"""Accès aux PDF du versement pour l'outil d'annotation.

Un cahier se désigne par le nom de son fichier PDF ; on ne sert que les
fichiers indexés au démarrage, jamais un chemin venu du navigateur. Le type
de chaque page vient du typage (#17), dont les tables portent le nom du
dossier du versement (`BnF_GDN_75_PDF.csv` pour `BnF_GDN_75_PDF/`).
"""

import csv
from functools import lru_cache
from pathlib import Path

import pymupdf

PAS_LARGEUR = 100  # pixels : les images sont rendues par paliers, pour le cache
LARGEUR_MAX = 3000


class Corpus:
    def __init__(self, versement: Path, typage: Path):
        self.typage_dossier = typage
        self.chemins = {
            p.name: p for p in versement.rglob("*.pdf", recurse_symlinks=True)
        }
        self.noms = sorted(self.chemins)
        self.typages: dict[str, dict] = {}  # typage par dossier, lu à la demande

    def chemin(self, fichier: str) -> Path:
        return self.chemins[fichier]  # KeyError : fichier inconnu

    def chercher(self, motif: str, limite: int = 50) -> list[str]:
        motif = motif.strip()
        return [nom for nom in self.noms if motif in nom][:limite] if motif else []

    def _typage(self, dossier: str) -> dict[str, dict[int, dict]]:
        if dossier in self.typages:
            return self.typages[dossier]
        table = self.typage_dossier / f"{dossier}.csv"
        types: dict[str, dict[int, dict]] = {}
        if table.exists():
            with table.open(encoding="utf-8", newline="") as f:
                for ligne in csv.DictReader(f):
                    types.setdefault(ligne["fichier"], {})[int(ligne["page"])] = {
                        "type": ligne["type_page"],
                        "service": ligne["page_de_service"] == "1",
                        "encre": float(ligne["encre"] or 0),
                        "qualite": float(ligne["qualite"] or 0),
                        "mots": int(ligne["mots"] or 0),
                    }
        self.typages[dossier] = types
        return types

    def pages(self, fichier: str) -> list[dict]:
        """Dimensions affichées (points PDF) et type de chaque page."""
        chemin = self.chemin(fichier)
        types = self._typage(chemin.parent.name).get(fichier, {})
        with pymupdf.open(chemin) as doc:
            return [
                {
                    "page": n,
                    "largeur": round(doc[n - 1].rect.width, 1),
                    "hauteur": round(doc[n - 1].rect.height, 1),
                    **types.get(n, {"type": "", "service": False}),
                    "rotation_pdf": doc[n - 1].rotation,
                }
                for n in range(1, doc.page_count + 1)
            ]

    def lignes(self, fichier: str, page: int) -> list[dict]:
        """Lignes de la couche texte (OCR du versement), avec leur cadre en
        points dans le repère de la page affichée. Pour l'affichage local
        seulement : ce texte est celui du cahier."""
        with pymupdf.open(self.chemin(fichier)) as doc:
            p = doc[page - 1]
            sortie = []
            for bloc in p.get_text("dict")["blocks"]:
                for ligne in bloc.get("lines", []):
                    cadre = pymupdf.Rect(ligne["bbox"]) * p.rotation_matrix
                    sortie.append(
                        {
                            "x0": round(cadre.x0, 1),
                            "y0": round(cadre.y0, 1),
                            "x1": round(cadre.x1, 1),
                            "y1": round(cadre.y1, 1),
                            "texte": "".join(s["text"] for s in ligne["spans"]),
                        }
                    )
            return sortie

    def image(self, fichier: str, page: int, largeur: int) -> bytes:
        largeur = max(
            PAS_LARGEUR, min(LARGEUR_MAX, round(largeur / PAS_LARGEUR) * PAS_LARGEUR)
        )
        return _rendre(self.chemin(fichier), page, largeur)


@lru_cache(maxsize=256)
def _rendre(chemin: Path, page: int, largeur: int) -> bytes:
    with pymupdf.open(chemin) as doc:
        p = doc[page - 1]  # IndexError : page hors du cahier
        zoom = largeur / p.rect.width
        pixmap = p.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
        return pixmap.tobytes("jpeg", jpg_quality=85)
