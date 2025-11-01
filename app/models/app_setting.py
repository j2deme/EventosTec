"""Application settings model for runtime configuration management."""

from app import db
from datetime import datetime


class AppSetting(db.Model):
    """
    Application-level settings stored in database.

    These settings can be adjusted at runtime without restarting the app.
    Values are managed through a hierarchical system: ENV > BD > Defaults.

    Attributes:
        key: Unique identifier (lowercase_snake_case)
        value: Current value (stored as string)
        data_type: Type hint for parsing (string, integer, boolean, timezone)
        is_editable: Whether this setting can be modified via UI
        default_value: Fallback value if not set
        created_at: Timestamp of creation
        updated_at: Timestamp of last update
        updated_by_user_id: ID of user who last modified it (for audit)
    """

    __tablename__ = "app_settings"

    id = db.Column(db.Integer, primary_key=True)

    # Key: lowercase_snake_case, e.g., 'app_timezone'
    key = db.Column(db.String(128), unique=True, nullable=False, index=True)

    # Value: stored as string; caller is responsible for parsing type
    value = db.Column(db.Text, nullable=True)

    # Human-readable description for admin UI
    description = db.Column(db.String(500), nullable=True)

    # Data type hint for validation and UI rendering
    # Options: 'string', 'integer', 'boolean', 'float', 'timezone'
    data_type = db.Column(db.String(50), default="string")

    # Default value if not set in BD or ENV
    default_value = db.Column(db.Text, nullable=True)

    # Whether this key is allowed to be overridden in UI
    # (False = locked by ENV, cannot be edited)
    is_editable = db.Column(db.Boolean, default=True)

    # Audit trail
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    updated_by_user_id = db.Column(db.Integer, nullable=True)

    def __repr__(self):
        return f"<AppSetting {self.key}={self.value}>"

    @classmethod
    def find_by_key(cls, key: str):
        """Get a single setting by key."""
        return db.session.query(cls).filter_by(key=key).first()

    @classmethod
    def get_all_settings(cls) -> dict:
        """Return all settings as dict {key: setting_object}."""
        return {s.key: s for s in db.session.query(cls).all()}
