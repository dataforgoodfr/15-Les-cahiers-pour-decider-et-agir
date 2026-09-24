from database.models import Document, Page
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def create_page(
    session: AsyncSession, document: Document, num_page: int, texte_brut: str
):
    page = Page(num_page=num_page, texte_brut=texte_brut, document=document)
    session.add(page)
    return page


async def list_pages(session: AsyncSession):
    stmt = select(Page).execution_options(yield_per=1000)
    return await session.stream_scalars(stmt)
