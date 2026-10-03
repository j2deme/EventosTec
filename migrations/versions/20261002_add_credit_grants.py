"""Create credit_grants table (history of granted complementary credits).

Migración 100% aditiva: solo crea la tabla; no altera ni toca tablas
existentes (requisito de despliegue quirúrgico en producción), mismo criterio
que 20261001_add_credit_overrides.

Registra, por estudiante y evento, los eventos "gastados" al acreditar el
crédito complementario, para que no se puedan volver a usar en una
acreditación futura (evita el doble acreditado al re-exportar la lista).
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20261002_add_credit_grants"
down_revision = "20261001_add_credit_overrides"
branch_labels = None
depends_on = None


def upgrade():
    """Create credit_grants (una fila por estudiante+evento gastado)."""
    op.create_table(
        "credit_grants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.String(length=36), nullable=False),
        sa.Column("granted_by", sa.Integer(), nullable=True),
        sa.Column(
            "granted_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"]),
        sa.UniqueConstraint(
            "student_id", "event_id", name="uq_credit_grants_student_event"
        ),
    )
    op.create_index("ix_credit_grants_student_id", "credit_grants", ["student_id"])
    op.create_index("ix_credit_grants_event_id", "credit_grants", ["event_id"])
    op.create_index("ix_credit_grants_batch_id", "credit_grants", ["batch_id"])


def downgrade():
    """Drop credit_grants table."""
    op.drop_index("ix_credit_grants_batch_id", table_name="credit_grants")
    op.drop_index("ix_credit_grants_event_id", table_name="credit_grants")
    op.drop_index("ix_credit_grants_student_id", table_name="credit_grants")
    op.drop_table("credit_grants")
