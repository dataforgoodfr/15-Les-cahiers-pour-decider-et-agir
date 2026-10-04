import argparse
import asyncio
import logging
from pathlib import Path

from extraction.discovery import list_pdfs
from extraction.extract_document import extract_document
from extraction.extract_page import extract_pdf_pages
from infra.container import Container
from tqdm import tqdm

container = Container()
container.logging()

logger = logging.getLogger(__name__)


async def main(recursive: bool) -> int:
    racine = container.settings().pdf_data_dir
    async with container.database().get_session() as db_session:
        pdf_paths = list_pdfs(racine, recursive)
        for f in tqdm(pdf_paths, "Extraction des données depuis les fichiers PDF"):
            await db_session.begin()
            document = await extract_document(db_session, f)
            document.nb_pages = await extract_pdf_pages(db_session, document)
            document.chemin = str(Path(document.chemin).relative_to(racine))
            await db_session.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extraction des données depuis les documents PDF"
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Parcourir les sous-répertoires",
        default=False,
    )
    args = parser.parse_args()
    asyncio.run(main(args.recursive))
