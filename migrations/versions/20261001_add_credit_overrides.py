"""Create credit_overrides table (manual overrides for complementary credits).

Migración 100% aditiva: solo crea la tabla; no altera ni toca tablas
existentes (requisito de despliegue quirúrgico en producción).
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20261001_add_credit_overrides"
down_revision = "20260927_add_revoked_tokens"
branch_labels = None
depends_on = None


def upgrade():
    """Create credit_overrides (una fila por estudiante, decision include/exclude)."""
    op.create_table(
        "credit_overrides",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(length=10), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.UniqueConstraint("student_id", name="uq_credit_overrides_student_id"),
    )


def downgrade():
    """Drop credit_overrides table."""
    op.drop_table("credit_overrides")
