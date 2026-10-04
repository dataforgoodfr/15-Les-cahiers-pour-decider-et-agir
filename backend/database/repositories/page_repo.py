from uuid import UUID

from database.models import Document, Page
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def create_page(
    session: AsyncSession, document: Document, num_page: int, texte_brut: str
):
    page = Page(num_page=num_page, texte_brut=texte_brut, document=document)
    session.add(page)
    return page


async def liste_pages(session: AsyncSession) -> list[Page]:
    stmt = select(Page).execution_options(yield_per=1000)
    return await session.stream_scalars(stmt)


async def liste_pages_document(session: AsyncSession, document_id: UUID) -> list[Page]:
    result = await session.execute(
        select(Page)
        .where(Page.document_id == document_id)
        .order_by(Page.num_page.asc())
    )
    return result.scalars().all()


async def get_doc_page(
    session: AsyncSession, document_id: UUID, page_number: int
) -> Page | None:
    result = await session.execute(
        select(Page)
        .where(Page.document_id == document_id)
        .where(Page.num_page == page_number)
    )
    return result.scalars().first()
