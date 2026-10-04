import os
from pathlib import Path

from database.repositories.communes_repo import (
    get_commune_by_code,
    recherche_commune_proche_cp,
)
from database.repositories.document_repo import create_document
from infra.errors import AppException
from sqlalchemy.ext.asyncio import AsyncSession


def parse_filename(filename) -> dict:
    """Extrait type de contribution, code postal, code INSEE (si présent),
    mode de contributionà partir du nom de fichier."""
    parsed = {
        "type_contrib": None,
        "code_postal": None,
        "code_insee": None,
        "mode_contrib": None,
    }
    elems = filename.stem.split("_")
    match len(elems):
        case 6:
            parsed["type_contrib"] = elems[0]
            parsed["code_postal"] = elems[1]
            parsed["code_insee"] = elems[3]
            parsed["mode_contrib"] = elems[4]
        case 5:
            parsed["type_contrib"] = elems[0]
            parsed["code_postal"] = elems[1]
            parsed["mode_contrib"] = elems[3]
        case _:
            raise AppException(f"Nommage du fichier invalide: {filename}")
    return parsed


async def extract_document(session: AsyncSession, filepath: Path):
    pdf_name = filepath.name
    parsed = parse_filename(filepath)
    filesize = os.path.getsize(filepath)
    document = create_document(
        session,
        chemin=str(filepath),
        nom=pdf_name,
    )
    document.taille_fichier = filesize
    document.code_postal = parsed["code_postal"]
    document.type_document = parsed["type_contrib"]
    document.mode_document = parsed["mode_contrib"]
    document.commune_id = None
    if parsed["code_insee"]:
        commune = await get_commune_by_code(session, parsed["code_insee"])
        if commune:
            document.commune_id = commune.id
    if not document.commune_id:
        # Commune non identifiée par le code INSEE, recherche par le CP
        commune = await recherche_commune_proche_cp(session, document.code_postal)
        if not commune:
            # Pas trouvé -> la commune n'existe pas où le document vient de l'étranger
            commune = await get_commune_by_code(session, "99999")
        document.commune_id = commune.id
    return document
