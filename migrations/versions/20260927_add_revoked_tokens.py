"""Create revoked_tokens table for server-side JWT logout (blocklist)."""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260927_add_revoked_tokens"
down_revision = "20251031_create_app_settings"
branch_labels = None
depends_on = None


def upgrade():
    """Create revoked_tokens table with unique jti index."""
    op.create_table(
        "revoked_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("jti", sa.String(36), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_revoked_tokens_jti"), "revoked_tokens", ["jti"], unique=True
    )
    op.create_index(
        op.f("ix_revoked_tokens_expires_at"),
        "revoked_tokens",
        ["expires_at"],
        unique=False,
    )


def downgrade():
    """Drop revoked_tokens table."""
    op.drop_index(op.f("ix_revoked_tokens_expires_at"), table_name="revoked_tokens")
    op.drop_index(op.f("ix_revoked_tokens_jti"), table_name="revoked_tokens")
    op.drop_table("revoked_tokens")
