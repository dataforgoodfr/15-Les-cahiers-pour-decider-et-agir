from uuid import UUID

from database.models import Departement, Region
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def create_departement(session: AsyncSession, region: Region, code: str, nom: str):
    """Create a new departement in the database."""

    departement = Departement(code=code, nom=nom, region=region)
    session.add(departement)
    return departement


async def liste_departements(
    session: AsyncSession, region_id: UUID | None, region: Region | None = None
) -> list[Departement]:
    """List all departements in the database."""
    query = select(Departement)
    if region:
        query = query.where(Departement.region == region)
    elif region_id:
        query = query.where(Departement.region_id == region_id)
    result = await session.execute(query)
    return result.scalars().all()
