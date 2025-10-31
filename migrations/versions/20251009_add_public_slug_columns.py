"""add public_slug columns to events and activities

Revision ID: 20251009_add_public_slug_columns
Revises:
Create Date: 2025-10-09 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251009_add_public_slug_columns"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add nullable public_slug columns to events and activities
    op.add_column(
        "events", sa.Column("public_slug", sa.String(length=200), nullable=True)
    )
    op.add_column(
        "activities", sa.Column("public_slug", sa.String(length=200), nullable=True)
    )


def downgrade():
    op.drop_column("activities", "public_slug")
    op.drop_column("events", "public_slug")
