"""Modèles de reconnaissance : téléchargés depuis leur dépôt public, vérifiés
par leur somme de contrôle, rangés dans data/htr/modeles (hors git)."""

import hashlib
import urllib.error
import urllib.request
from pathlib import Path

ZENODO = "https://zenodo.org/api/records/{}/files/{}/content"

# nom court : (fichier, adresse, md5)
MODELES = {
    # Manicule 2026 Français moderne (LaMOP, juillet 2026), CC0. Le meilleur
    # modèle générique sur l'étalon de Charente-Maritime (docs/htr.md).
    "manicule-2026": (
        "Manicule-2026-Francais-Moderne.mlmodel",
        ZENODO.format(21195087, "Manicule-2026-Francais-Moderne.mlmodel"),
        "4f5eef781288ca4a0f0efeed1863dcdf",
    ),
    # McCATMuS (Clérice et al. 2024), XVIᵉ-XXIᵉ siècle, CC BY 4.0
    "mccatmus": (
        "McCATMuS_nfd_nofix_V1.mlmodel",
        ZENODO.format(13788177, "McCATMuS_nfd_nofix_V1.mlmodel"),
        "e531463f631303c700750784b4f9ed63",
    ),
}
ESSAIS = 3  # Zenodo coupe parfois les gros fichiers en cours de route


def md5(chemin: Path) -> str:
    return hashlib.md5(chemin.read_bytes()).hexdigest()


def modele(nom: str, dossier: Path) -> Path:
    """Chemin du modèle, téléchargé s'il manque. Erreur si sa somme de
    contrôle n'est pas celle publiée."""
    fichier, adresse, attendu = MODELES[nom]
    cible = dossier / fichier
    if not cible.exists():
        dossier.mkdir(parents=True, exist_ok=True)
        partiel = cible.with_name(cible.name + ".part")
        print(f"Téléchargement de {fichier}…", flush=True)
        for essai in range(ESSAIS):
            try:
                urllib.request.urlretrieve(adresse, partiel)
                break
            except urllib.error.ContentTooShortError:
                if essai == ESSAIS - 1:
                    raise
        partiel.rename(cible)
    if md5(cible) != attendu:
        raise ValueError(f"{cible} : somme de contrôle inattendue")
    return cible
