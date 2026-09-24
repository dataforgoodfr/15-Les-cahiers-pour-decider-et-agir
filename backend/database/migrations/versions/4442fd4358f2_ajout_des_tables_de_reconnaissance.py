"""Ajout des tables de reconnaissance

Revision ID: 4442fd4358f2
Revises: 694999f9aafc
Create Date: 2026-09-23 22:22:30.148725

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from database.models import MethodeReconnaissance
from sqlalchemy.sql import func

# revision identifiers, used by Alembic.
revision: str = "4442fd4358f2"
down_revision: str | Sequence[str] | None = "694999f9aafc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "reconnaissance",
        sa.Column("id", sa.Uuid, primary_key=True, nullable=False),
        sa.Column("page_id", sa.Uuid, sa.ForeignKey("page.id"), nullable=False),
        sa.Column("methode", sa.Enum(MethodeReconnaissance), nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("resultat", sa.String, nullable=True),
        sa.Column("commentaire_traitement", sa.String, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("reconnaissance")
