from uuid import UUID

from database.models import Commune, Departement, Document, Region
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def create_document(session: AsyncSession, chemin: str, nom: str):
    """Create a new document in the database."""

    document = Document(chemin=chemin, nom=nom)
    session.add(document)
    return document


async def liste_documents(
    session: AsyncSession,
    region_id: UUID | None,
    departement_id: UUID | None,
    commune_id: UUID | None,
) -> list[Document]:
    query = (
        select(Document)
        .join(Document.commune)
        .join(Commune.departement)
        .join(Departement.region)
    )
    if region_id:
        query = query.where(Region.id == region_id)
    if departement_id:
        query = query.where(Departement.id == departement_id)
    if commune_id:
        query = query.where(Commune.id == commune_id)
    result = await session.execute(query)
    return result.scalars().all()
