from database.models import Departement, Region
from sqlalchemy.ext.asyncio import AsyncSession


def create_departement(session: AsyncSession, region: Region, code: str, nom: str):
    """Create a new departement in the database."""

    departement = Departement(code=code, nom=nom, region=region)
    session.add(departement)
    return departement
