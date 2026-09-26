from database.models import Commune, Departement
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def create_commune(
    session: AsyncSession,
    departement: Departement,
    code_insee: str,
    nom: str,
    codes_postaux=None,
    population=None,
    centre_longitude=None,
    centre_latitude=None,
):
    """Create a new commune in the database."""

    commune = Commune(
        code_insee=code_insee,
        nom=nom,
        departement=departement,
        codes_postaux=codes_postaux,
        population=population,
        centre_longitude=centre_longitude,
        centre_latitude=centre_latitude,
    )
    session.add(commune)
    return commune


async def get_commune_by_code(session: AsyncSession, code_insee: str) -> Commune | None:
    """Get a commune by its code."""
    result = await session.execute(
        select(Commune).where(Commune.code_insee == code_insee)
    )
    return result.scalars().first()


async def liste_communes(
    session: AsyncSession, departement_id: str | None
) -> list[Commune]:
    """List all communes in the database."""
    query = select(Commune)
    if departement_id:
        query = query.where(Commune.departement_id == departement_id)
    result = await session.execute(query)
    return result.scalars().all()
