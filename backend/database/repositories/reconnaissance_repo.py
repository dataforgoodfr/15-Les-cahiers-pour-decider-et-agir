from database.models import MethodeReconnaissance, Page, TraitementReconnaissance
from sqlalchemy.ext.asyncio import AsyncSession


def create_reconnaissance(
    session: AsyncSession, methode: MethodeReconnaissance, page: Page
) -> TraitementReconnaissance:
    r = TraitementReconnaissance(page=page, methode=methode, score=0.0)
    session.add(r)
    return r
