"""Lecture d'une page : rendu à la résolution du scan, segmentation en lignes
par kraken (modèle blla par défaut), reconnaissance de chaque ligne."""

import unicodedata

import pymupdf
from PIL import Image


def zoom(page: pymupdf.Page) -> float:
    """Facteur de rendu qui retrouve la résolution du scan : la plus grande
    image de la page, rapportée à la page affichée. 2 (144 ppp) à défaut."""
    tailles = [max(i[2], i[3]) for i in page.get_images()]
    if not tailles:
        return 2.0
    return max(tailles) / max(page.rect.width, page.rect.height)


def image(page: pymupdf.Page, facteur: float) -> Image.Image:
    """La page telle qu'affichée (rotation comprise), en niveaux de gris."""
    pix = page.get_pixmap(
        matrix=pymupdf.Matrix(facteur, facteur), colorspace=pymupdf.csGRAY
    )
    return Image.frombytes("L", (pix.width, pix.height), pix.samples)


def cadre(polygone, facteur: float) -> list[float]:
    """Rectangle d'un polygone en pixels, en points de la page affichée : le
    repère des lignes de la couche texte (`contributions.lignes`)."""
    xs = [p[0] for p in polygone]
    ys = [p[1] for p in polygone]
    return [
        round(min(xs) / facteur, 1),
        round(min(ys) / facteur, 1),
        round(max(xs) / facteur, 1),
        round(max(ys) / facteur, 1),
    ]


class Lecteur:
    """Les modèles chargés une fois, pour lire beaucoup de pages."""

    def __init__(self, chemin_modele):
        from importlib import resources

        from kraken.lib import models, vgsl

        self.segmentation = vgsl.TorchVGSLModel.load_model(
            str(resources.files("kraken") / "blla.mlmodel")
        )
        self.reconnaissance = models.load_any(str(chemin_modele))

    def lire(self, page: pymupdf.Page) -> list[dict]:
        """Les lignes de la page, dans l'ordre de lecture de kraken : texte
        (NFC) et cadre en points. Les lignes que kraken ne sait pas extraire
        (trop courtes) sont omises."""
        from kraken import blla, rpred

        facteur = zoom(page)
        im = image(page, facteur)
        seg = blla.segment(im, model=self.segmentation)
        sortie = []
        for r in rpred.rpred(self.reconnaissance, im, seg):
            texte = unicodedata.normalize("NFC", r.prediction).strip()
            if texte:
                sortie.append({"texte": texte, "cadre": cadre(r.boundary, facteur)})
        return sortie
