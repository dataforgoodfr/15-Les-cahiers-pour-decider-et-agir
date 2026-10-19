"""Transcrire à la main les pages d'un étalon HTR dans l'outil d'annotation.

    uv run python -m annotation.transcriptions liste <étalon> [--nom NOM]
        [--dossier data/annotation]
    uv run python -m annotation.transcriptions exporter <étalon>
        --transcripteur NOM [--dossier data/annotation] [--remplacer]

Un étalon HTR (`docs/htr.md`) range dans `<étalon>/pages/` l'image de chaque
page, `<scan>_p<n>.jpg`, à côté de ses transcriptions
`<scan>_p<n>.<transcripteur>.txt`. `liste` en fait une liste à transcrire
(mode « transcrire » de `annotation.listes`) : les pages `n` des PDF
`<scan>.pdf` du versement, dans l'ordre. `exporter` écrit les transcriptions
du carnet à côté des images, sous le nom du transcripteur ; une page sans
transcription est sautée, et un fichier existant n'est remplacé qu'avec
`--remplacer`. Aucun texte n'est affiché : seulement des comptes.
"""

import argparse
import re
from pathlib import Path

from annotation import listes
from annotation.carnet import Carnet

IMAGE = re.compile(r"^(?P<scan>.+)_p(?P<page>\d+)$")
TACHE = "transcription"
CONSIGNE = (
    "Lire la page entière et l'écrire telle quelle, sans regarder d'autre "
    "transcription : orthographe, ponctuation et retours à la ligne "
    "d'origine, sans rien corriger. Un mot illisible : [?] ; un passage "
    "barré : [~~…~~] ; un nom de personne entre crochets, [Prénom NOM]. "
    "Le texte s'enregistre en tapant ; marquer la page vue (v) une fois "
    "finie."
)


def pages_de_l_etalon(etalon: Path) -> list[tuple[str, int, str]]:
    """(fichier PDF, page, nom de l'image) de chaque image de l'étalon,
    dans l'ordre du PDF puis des pages."""
    sortie = []
    for image in (etalon / "pages").glob("*.jpg"):
        m = IMAGE.match(image.stem)
        if m:
            sortie.append((f"{m['scan']}.pdf", int(m["page"]), image.stem))
    return sorted(sortie)


def ecrire_liste(etalon: Path, dossier: Path, nom: str) -> int:
    pages = pages_de_l_etalon(etalon)
    listes.ecrire(
        dossier / "listes",
        nom,
        f"Transcrire l'étalon {etalon.resolve().name}",
        CONSIGNE,
        [{"fichier": f, "page": n} for f, n, _ in pages],
        tache=TACHE,
        mode="transcrire",
    )
    return len(pages)


def exporter(
    etalon: Path, carnet: Carnet, transcripteur: str, remplacer: bool = False
) -> tuple[int, int]:
    """Écrit les transcriptions du carnet dans l'étalon : (écrites, gardées
    parce qu'un fichier existait déjà)."""
    if not re.fullmatch(r"[\w-]+", transcripteur):
        raise ValueError(f"nom de transcripteur invalide : {transcripteur}")
    transcriptions = carnet.transcriptions()
    ecrites = gardees = 0
    for fichier, page, image in pages_de_l_etalon(etalon):
        texte = transcriptions.get((fichier, page), "").strip()
        if not texte:
            continue
        cible = etalon / "pages" / f"{image}.{transcripteur}.txt"
        if cible.exists() and not remplacer:
            gardees += 1
            continue
        cible.write_text(texte + "\n", encoding="utf-8")
        ecrites += 1
    return ecrites, gardees


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sous = parser.add_subparsers(dest="commande", required=True)
    for nom in ("liste", "exporter"):
        p = sous.add_parser(nom)
        p.add_argument("etalon", type=Path)
        p.add_argument("--dossier", type=Path, default=Path("data/annotation"))
    sous.choices["liste"].add_argument("--nom")
    sous.choices["exporter"].add_argument("--transcripteur", required=True)
    sous.choices["exporter"].add_argument("--remplacer", action="store_true")
    args = parser.parse_args()
    if args.commande == "liste":
        nom = args.nom or f"transcription-{args.etalon.resolve().name}"
        n = ecrire_liste(args.etalon, args.dossier, nom)
        print(f"{n} pages dans la liste {nom}")
    else:
        carnet = Carnet(args.dossier / "notes.jsonl")
        ecrites, gardees = exporter(
            args.etalon, carnet, args.transcripteur, args.remplacer
        )
        print(f"{ecrites} transcriptions écrites, {gardees} gardées (--remplacer)")


if __name__ == "__main__":
    main()
