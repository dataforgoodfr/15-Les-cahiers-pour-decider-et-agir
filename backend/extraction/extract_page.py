"""PDF text extraction."""

import logging

import pymupdf
from database.models import Document
from database.repositories.page_repo import create_page
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def extract_pdf_pages(session: AsyncSession, document: Document) -> list[int]:
    """Extract text page-by-page and persist each page as a separate contribution.

    Rules:
    - The first ``skip_first_n_pages`` pages are parsed only to extract the
      city name (no PageExtraction row created).
    - From the next page onward, each page is extracted, cleaned, scored and
      persisted as a separate contribution (unless too short = noise).
    - Parsing stops at the first page containing the end marker (excluded).
    - For pages with ``needs_ocr=False``, an ``Extraction`` row is also created
      with the cleaned text.

    Args:
        filepath: Path of the PDF to process.
        engine: Optional SQLAlchemy engine (defaults to the global engine).

    Returns:
        List of IDs of the created ``Contribution`` rows (one per page).
    """
    logger.debug("Opening PDF: %s", document.nom)

    doc = pymupdf.open(document.chemin)
    page_count = doc.page_count
    logger.debug("Pages: %d", page_count)

    raw_pages: list[str] = []
    for i in range(page_count):
        create_page(session, document, i + 1, doc[i].get_text())
        # raw_pages.append(doc[i].get_text())
    doc.close()
