from database.models import Region
from sqlalchemy.ext.asyncio import AsyncSession


def create_region(session: AsyncSession, code: str, nom: str) -> Region:
    """Create a new region in the database."""

    region = Region(code=code, nom=nom)
    session.add(region)
    return region
