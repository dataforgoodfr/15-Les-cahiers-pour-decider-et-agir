import asyncio
import logging
import re

from database.models import MethodeReconnaissance
from database.repositories.page_repo import list_pages
from database.repositories.reconnaissance_repo import create_reconnaissance
from infra.container import Container
from tqdm.asyncio import tqdm
from wordfreq import zipf_frequency

container = Container()
container.logging()

logger = logging.getLogger(__name__)


def wordfreq_quality_score(text: str) -> float:
    """Estimate OCR quality from the frequency of French words.

    Splits the text into words longer than 2 characters, strips non-letter
    characters from each token (so that OCR garbage like ``"'aj-v"`` does not
    accidentally match a real French word), then returns the ratio of "known"
    words (zipf frequency >= 2 in French). Returns 0.0 when there is no token
    long enough to evaluate.

    Args:
        text: The cleaned text to evaluate.

    Returns:
        A float between 0.0 (all words unknown / OCR garbage) and 1.0
        (every word is a common French word).
    """
    tokens = [w.lower() for w in text.split() if len(w) > 2]
    words = [re.sub(r"[^a-zà-ÿ]", "", w) for w in tokens]
    words = [w for w in words if len(w) > 2]
    if not words:
        return 0.0
    known_words = sum(1 for w in words if zipf_frequency(w, "fr") >= 2)
    return known_words / len(words)


def clean_page_text(text: str) -> str:
    """Clean the raw text extracted from a page.

    - Strip leading/trailing whitespace.
    - Normalize carriage returns.
    - Collapse multiple spaces (preserving newlines).

    Args:
        text: Raw text from PyMuPDF.

    Returns:
        The cleaned text.
    """
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = []
    for line in text.split("\n"):
        collapsed = " ".join(line.split())
        lines.append(collapsed)
    return "\n".join(lines).strip()


async def main() -> int:
    async with container.database().get_session() as db_session:
        async for p in tqdm(await list_pages(db_session)):
            # tqdm(pages, "Reconnaissance par extraction du texte PDF"):
            # await db_session.begin()
            cleaned = clean_page_text(p.texte_brut)
            r = create_reconnaissance(db_session, MethodeReconnaissance.PDF_TEXT, p)
            if len(cleaned) < container.settings().min_chars_for_page:
                r.commentaire_traitement = (
                    f"Page trop courte ({len(cleaned)} caractères)"
                )
                continue
            r.score = wordfreq_quality_score(cleaned)
            if (
                cleaned.strip()
                and r.score >= container.settings().seuil_qualite_texte_pdf
            ):
                r.resultat = p.texte_brut
                p.texte_reconnu = r.resultat
            else:
                r.commentaire_traitement = f"Qualité inférieure au seuil de {container.settings().seuil_qualite_texte_pdf}"

        await db_session.commit()


if __name__ == "__main__":
    asyncio.run(main())
