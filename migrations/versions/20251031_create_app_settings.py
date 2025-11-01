"""Create app_settings table for runtime configuration."""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251031_create_app_settings"
down_revision = "20251009_add_public_slug_unique_index"
branch_labels = None
depends_on = None


def upgrade():
    """Create app_settings table with all columns."""
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("data_type", sa.String(50), nullable=False, server_default="string"),
        sa.Column("default_value", sa.Text(), nullable=True),
        # Use SQL-native defaults compatible with MySQL/MariaDB/SQLite
        sa.Column(
            "is_editable", sa.Boolean(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    # Create index on key for faster lookups
    op.create_index("ix_app_settings_key", "app_settings", ["key"])


def downgrade():
    """Drop app_settings table and index."""
    op.drop_index("ix_app_settings_key", table_name="app_settings")
    op.drop_table("app_settings")
