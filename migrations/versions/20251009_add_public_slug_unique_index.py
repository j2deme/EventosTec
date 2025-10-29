"""create unique index on public_slug with pre-checks

This migration will attempt to create unique indexes on events.public_slug and
activities.public_slug. Before creating the indexes it will verify that there are
no duplicate non-null slugs and that no NULL values exist if you desire that.
If duplicates are found the migration will raise and abort so you can run the
backfill script and resolve duplicates first.

Revision ID: 20251009_add_public_slug_unique_index
Revises: 20251009_add_public_slug_columns
Create Date: 2025-10-09 00:05:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '20251009_add_public_slug_unique_index'
down_revision = '20251009_add_public_slug_columns'
branch_labels = None
depends_on = None


def _ensure_no_duplicates(conn, table_name, column_name):
    # Count duplicates where column is not null
    q = text(
        f"SELECT {column_name}, COUNT(*) AS c FROM {table_name} WHERE {column_name} IS NOT NULL GROUP BY {column_name} HAVING COUNT(*) > 1")
    res = conn.execute(q).fetchall()
    if res:
        dupes = ', '.join([r[0] for r in res[:10]])
        raise RuntimeError(
            f"Cannot create unique index on {table_name}.{column_name}: duplicates found: {dupes}")


def upgrade():
    conn = op.get_bind()
    # Ensure there are no duplicates
    _ensure_no_duplicates(conn, 'events', 'public_slug')
    _ensure_no_duplicates(conn, 'activities', 'public_slug')

    # Create unique indexes
    op.create_index('ux_events_public_slug', 'events',
                    ['public_slug'], unique=True)
    op.create_index('ux_activities_public_slug', 'activities',
                    ['public_slug'], unique=True)


def downgrade():
    op.drop_index('ux_activities_public_slug', table_name='activities')
    op.drop_index('ux_events_public_slug', table_name='events')
