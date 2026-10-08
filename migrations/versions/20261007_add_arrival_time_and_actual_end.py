"""Add attendances.arrival_time and activities.actual_end_datetime

Llegada real del estudiante (no el check-in plegado por pausas) y hora real
de cierre de la actividad (informativa, la registra batch-checkout).

Revision ID: 20261007_add_arrival_time_and_actual_end
Revises: 20261002_add_credit_grants
Create Date: 2026-10-07 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20261007_add_arrival_time_and_actual_end"
down_revision = "20261002_add_credit_grants"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("attendances", schema=None) as batch_op:
        batch_op.add_column(sa.Column("arrival_time", sa.DateTime(), nullable=True))

    with op.batch_alter_table("activities", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("actual_end_datetime", sa.DateTime(), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("activities", schema=None) as batch_op:
        batch_op.drop_column("actual_end_datetime")

    with op.batch_alter_table("attendances", schema=None) as batch_op:
        batch_op.drop_column("arrival_time")
