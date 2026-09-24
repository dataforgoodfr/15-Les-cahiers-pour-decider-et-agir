from database.models import Document
from sqlalchemy.ext.asyncio import AsyncSession


def create_document(session: AsyncSession, chemin: str, nom: str):
    """Create a new document in the database."""

    document = Document(chemin=chemin, nom=nom)
    session.add(document)
    return document
