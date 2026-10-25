"""Plongements de phrases, avec un petit modèle local sur CPU."""

import hashlib
from pathlib import Path

import numpy as np

MODELE = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
LOT = 64  # phrases par passe du modèle
LONGUEUR = 128  # jetons au plus par phrase


def empreinte(textes: list[str], modele: str) -> str:
    h = hashlib.sha256(modele.encode())
    for t in textes:
        h.update(b"\0" + t.encode())
    return h.hexdigest()


def plonger(textes: list[str], modele: str = MODELE) -> np.ndarray:
    """Un vecteur normé par texte : moyenne des jetons, comme le modèle a
    été entraîné."""
    import torch
    from transformers import AutoModel, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(modele)
    reseau = AutoModel.from_pretrained(modele).eval()
    vecteurs = []
    with torch.inference_mode():
        for debut in range(0, len(textes), LOT):
            entree = tokenizer(
                textes[debut : debut + LOT],
                padding=True,
                truncation=True,
                max_length=LONGUEUR,
                return_tensors="pt",
            )
            jetons = reseau(**entree).last_hidden_state
            masque = entree["attention_mask"].unsqueeze(-1).to(jetons.dtype)
            moyenne = (jetons * masque).sum(1) / masque.sum(1).clamp(min=1)
            vecteurs.append(torch.nn.functional.normalize(moyenne, dim=1).numpy())
    return np.concatenate(vecteurs) if vecteurs else np.zeros((0, 0), np.float32)


def plongements(textes: list[str], modele: str, cache: Path) -> np.ndarray:
    """Les plongements de `textes`, relus du cache s'il correspond."""
    cle = empreinte(textes, modele)
    if cache.exists():
        lu = np.load(cache)
        if str(lu["empreinte"]) == cle:
            return lu["vecteurs"]
    vecteurs = plonger(textes, modele)
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez(cache, vecteurs=vecteurs, empreinte=cle)
    return vecteurs
