from database.models import MethodeReconnaissance, Page, Reconnaissance
from sqlalchemy.ext.asyncio import AsyncSession


def create_reconnaissance(
    session: AsyncSession, methode: MethodeReconnaissance, page: Page
) -> Reconnaissance:
    r = Reconnaissance(page=page, methode=methode, score=0.0)
    session.add(r)
    return r
