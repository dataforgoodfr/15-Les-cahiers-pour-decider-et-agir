from uuid import UUID

from database.models import MethodeReconnaissance, Page, TraitementReconnaissance
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def create_reconnaissance(
    session: AsyncSession, methode: MethodeReconnaissance, page: Page
) -> TraitementReconnaissance:
    r = TraitementReconnaissance(page=page, methode=methode, score=0.0)
    session.add(r)
    return r


async def liste_reconnaissances(
    session: AsyncSession, page_id: UUID
) -> list[TraitementReconnaissance]:
    result = await session.execute(
        select(TraitementReconnaissance).where(
            TraitementReconnaissance.page_id == page_id
        )
    )
    return result.scalars().all()
