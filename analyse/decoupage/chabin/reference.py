"""Les cahiers transcrits par Marie-Anne Chabin, comme référence de découpage.

Son édition sépare déjà les contributions des cahiers de Charente-Maritime
(`extraction/chabin`). Le lecteur délimite les mêmes cahiers dans l'outil
d'annotation, sans connaître ses comptes ; on compare ensuite, cahier par
cahier, les contributions qu'il trouve à celles de l'édition.

Seuls les comptes et les noms de fichiers de l'extraction sont lus, jamais
le texte des contributions.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Cahier:
    insee: str
    commune: str
    contributions: int  # selon l'édition Chabin
    fichiers: tuple[str, ...]  # scans BnF de la commune


def cahiers(extraction: list[dict | None]) -> list[Cahier]:
    """Les cahiers extraits (les `null` sont ceux sans PDF téléchargé)."""
    return [
        Cahier(
            e["city"]["insee"],
            e["city"]["commune"],
            e["found_nb_contrib"],
            tuple(Path(f).name for f in e["pdf_files"]),
        )
        for e in extraction
        if e
    ]


def elements(liste: list[Cahier], pages: dict[str, int]) -> list[dict]:
    """Un élément de liste par scan présent, à sa première page. Le compte de
    l'édition n'y figure pas : le lecteur ne doit pas le connaître."""
    sortie = []
    for c in liste:
        presents = [f for f in c.fichiers if f in pages]
        for i, f in enumerate(presents, 1):
            autres = f", fichier {i} sur {len(presents)}" if len(presents) > 1 else ""
            sortie.append(
                {
                    "fichier": f,
                    "page": 1,
                    "commentaire": f"{c.commune} ({c.insee}), {pages[f]} pages{autres}.",
                }
            )
    return sortie


def comparer(
    liste: list[Cahier], debuts: dict[str, int], delimites: set[str]
) -> list[dict]:
    """Par cahier dont tous les scans sont délimités : contributions de
    l'édition et débuts notés par le lecteur."""
    lignes = []
    for c in liste:
        if not c.fichiers or not all(f in delimites for f in c.fichiers):
            continue
        notes = sum(debuts.get(f, 0) for f in c.fichiers)
        lignes.append(
            {
                "insee": c.insee,
                "commune": c.commune,
                "chabin": c.contributions,
                "lecteur": notes,
                "ecart": notes - c.contributions,
            }
        )
    return lignes
