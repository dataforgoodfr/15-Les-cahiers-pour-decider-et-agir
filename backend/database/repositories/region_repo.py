from database.models import Region
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def create_region(session: AsyncSession, code: str, nom: str) -> Region:
    """Create a new region in the database."""

    region = Region(code=code, nom=nom)
    session.add(region)
    return region


async def liste_regions(session: AsyncSession) -> list[Region]:
    """List all regions in the database."""
    result = await session.execute(select(Region))
    return result.scalars().all()
