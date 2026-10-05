"""Ajout des tables de codification régions/départements/communes

Revision ID: ee34a044e200
Revises:
Create Date: 2026-09-19 21:38:42.334523

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "ee34a044e200"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "region",
        sa.Column("id", sa.Uuid, primary_key=True, nullable=False),
        sa.Column("code", sa.String, nullable=False, unique=True),
        sa.Column("nom", sa.String, nullable=False),
    )
    op.create_table(
        "departement",
        sa.Column("id", sa.Uuid, primary_key=True, nullable=False),
        sa.Column("code", sa.String, nullable=False, unique=True),
        sa.Column("nom", sa.String, nullable=False),
        sa.Column("region_id", sa.Uuid, sa.ForeignKey("region.id"), nullable=False),
    )
    op.create_table(
        "commune",
        sa.Column("id", sa.Uuid, primary_key=True, nullable=False),
        sa.Column("code_insee", sa.String, nullable=False, unique=True),
        sa.Column(
            "codes_postaux", postgresql.ARRAY(sa.String()), nullable=True, unique=False
        ),
        sa.Column("nom", sa.String, nullable=False),
        sa.Column("population", sa.Integer, nullable=True),
        sa.Column("centre_latitude", sa.Float, nullable=True),
        sa.Column("centre_longitude", sa.Float, nullable=True),
        sa.Column(
            "departement_id", sa.Uuid, sa.ForeignKey("departement.id"), nullable=False
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("commune")
    op.drop_table("departement")
    op.drop_table("region")
