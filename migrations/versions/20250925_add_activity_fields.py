"""add activity speakers, target_audience and knowledge_area

Revision ID: 20250925_add_activity_fields
Revises: f517609078c5
Create Date: 2025-09-25 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250925_add_activity_fields'
down_revision = 'f517609078c5'
branch_labels = None
depends_on = None


def upgrade():
    # Add columns to activities table
    op.add_column('activities', sa.Column(
        'speakers', sa.Text(), nullable=True))
    op.add_column('activities', sa.Column(
        'target_audience', sa.Text(), nullable=True))
    op.add_column('activities', sa.Column(
        'knowledge_area', sa.String(length=100), nullable=True))


def downgrade():
    op.drop_column('activities', 'knowledge_area')
    op.drop_column('activities', 'target_audience')
    op.drop_column('activities', 'speakers')
