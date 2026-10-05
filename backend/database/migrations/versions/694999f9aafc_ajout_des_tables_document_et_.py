"""Ajout des tables document et contribution

Revision ID: 694999f9aafc
Revises: ee34a044e200
Create Date: 2026-09-20 17:51:08.710534

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from database.models import ModeDocument, TypeDocument
from sqlalchemy.sql import func

# revision identifiers, used by Alembic.
revision: str = "694999f9aafc"
down_revision: str | Sequence[str] | None = "ee34a044e200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "document",
        sa.Column("id", sa.Uuid, primary_key=True, nullable=False),
        sa.Column("chemin", sa.String, nullable=False, unique=True),
        sa.Column("nom", sa.String, nullable=False),
        sa.Column("type_document", sa.Enum(TypeDocument), nullable=False),
        sa.Column("mode_document", sa.Enum(ModeDocument), nullable=False),
        sa.Column("code_postal", sa.String, nullable=False),
        sa.Column("taille_fichier", sa.Integer, nullable=False),
        sa.Column("nb_pages", sa.Integer, nullable=True),
        sa.Column("commune_id", sa.Uuid, sa.ForeignKey("commune.id"), nullable=True),
        sa.Column(
            "horodatage_creation",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )

    op.create_table(
        "page",
        sa.Column("id", sa.Uuid, primary_key=True, nullable=False),
        sa.Column("num_page", sa.Integer, nullable=False),
        sa.Column("texte_brut", sa.String, nullable=True),
        sa.Column("texte_reconnu", sa.String, nullable=True),
        sa.Column("document_id", sa.Uuid, sa.ForeignKey("document.id"), nullable=True),
        sa.Column(
            "horodatage_creation",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
        sa.Column(
            "horodatage_modification", sa.DateTime(timezone=True), onupdate=func.now()
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("page")
    op.drop_table("document")
    op.execute("DROP TYPE typedocument")
    op.execute("DROP TYPE modedocument")
