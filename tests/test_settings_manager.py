"""Tests for SettingsManager service."""

import os
import pytest
from datetime import datetime
from app import create_app, db
from app.models.app_setting import AppSetting
from app.services.settings_manager import SettingsManager, AppSettings


@pytest.fixture
def app():
    """Create application for testing."""
    _app = create_app("testing")
    _app.config["TESTING"] = True

    with _app.app_context():
        db.create_all()
        yield _app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def sample_settings(app):
    """Create sample settings for testing."""
    with app.app_context():
        settings = [
            AppSetting(
                key="app_timezone",
                value="America/Mexico_City",
                data_type="timezone",
                default_value="America/Mexico_City",
                description="Application timezone",
                is_editable=True,
            ),
            AppSetting(
                key="public_pause_available_from_seconds",
                value="0",
                data_type="integer",
                default_value="0",
                description="Seconds after activity start",
                is_editable=True,
            ),
            AppSetting(
                key="public_pause_available_until_after_end_minutes",
                value="5",
                data_type="integer",
                default_value="5",
                description="Minutes after activity end",
                is_editable=True,
            ),
            AppSetting(
                key="public_confirm_window_days",
                value="30",
                data_type="integer",
                default_value="30",
                description="Days window for confirming",
                is_editable=True,
            ),
        ]
        for setting in settings:
            db.session.add(setting)
        db.session.commit()


class TestSettingsManager:
    """Test SettingsManager hierarchical lookup and operations."""

    def test_get_from_default_when_not_in_bd(self, app, sample_settings):
        """Test that get() returns default when key not in BD."""
        with app.app_context():
            value = SettingsManager.get("nonexistent_key", "default_value")
            assert value == "default_value"

    def test_get_from_bd_cache(self, app, sample_settings):
        """Test that get() retrieves value from BD cache."""
        with app.app_context():
            value = SettingsManager.get("app_timezone")
            assert value == "America/Mexico_City"

    def test_get_from_env_priority(self, app, sample_settings):
        """Test that ENV values have highest priority."""
        with app.app_context():
            # Set ENV variable
            os.environ["APP_APP_TIMEZONE"] = "America/New_York"
            try:
                value = SettingsManager.get("app_timezone")
                assert value == "America/New_York"
            finally:
                del os.environ["APP_APP_TIMEZONE"]
                SettingsManager._invalidate_cache("app_timezone")

    def test_parse_integer(self, app, sample_settings):
        """Test parsing integer values."""
        with app.app_context():
            value = SettingsManager.get("public_pause_available_from_seconds")
            assert isinstance(value, int)
            assert value == 0

    def test_parse_timezone(self, app, sample_settings):
        """Test parsing timezone values."""
        with app.app_context():
            value = SettingsManager.get("app_timezone")
            assert isinstance(value, str)
            assert value == "America/Mexico_City"

    def test_cache_ttl(self, app, sample_settings):
        """Test that cache invalidates after TTL."""
        with app.app_context():
            # Get value (caches it)
            value1 = SettingsManager.get("app_timezone")

            # Manually set cache time to past
            SettingsManager._cache["app_timezone"] = (
                value1,
                datetime.utcnow() - __import__("datetime").timedelta(seconds=20),
            )

            # Update in DB
            setting = AppSetting.find_by_key("app_timezone")
            setting.value = "America/Los_Angeles"
            db.session.commit()

            # Get should read from DB (cache expired)
            value2 = SettingsManager.get("app_timezone")
            assert value2 == "America/Los_Angeles"

    def test_set_in_db_updates_value(self, app, sample_settings):
        """Test that set_in_db() updates BD correctly."""
        with app.app_context():
            SettingsManager.set_in_db("app_timezone", "America/Denver", user_id=1)

            setting = AppSetting.find_by_key("app_timezone")
            assert setting.value == "America/Denver"
            assert setting.updated_by_user_id == 1
            assert setting.updated_at is not None

    def test_set_in_db_invalidates_cache(self, app, sample_settings):
        """Test that set_in_db() invalidates cache."""
        with app.app_context():
            # Prime cache
            SettingsManager.get("app_timezone")
            assert "app_timezone" in SettingsManager._cache

            # Update value
            SettingsManager.set_in_db("app_timezone", "America/Denver", user_id=1)

            # Cache should be invalidated
            assert "app_timezone" not in SettingsManager._cache

    def test_set_in_db_blocked_by_env(self, app, sample_settings):
        """Test that ENV-locked settings cannot be modified via set_in_db()."""
        with app.app_context():
            os.environ["APP_APP_TIMEZONE"] = "America/New_York"
            try:
                with pytest.raises(ValueError, match="locked by environment variable"):
                    SettingsManager.set_in_db(
                        "app_timezone", "America/Denver", user_id=1
                    )
            finally:
                del os.environ["APP_APP_TIMEZONE"]

    def test_validate_integer(self, app, sample_settings):
        """Test integer validation."""
        with app.app_context():
            # Valid
            SettingsManager.set_in_db(
                "public_pause_available_from_seconds", 600, user_id=1
            )

            # Invalid
            with pytest.raises(ValueError):
                SettingsManager.set_in_db(
                    "public_pause_available_from_seconds", "not_a_number", user_id=1
                )

    def test_validate_timezone(self, app, sample_settings):
        """Test timezone validation."""
        with app.app_context():
            # Valid
            SettingsManager.set_in_db("app_timezone", "Europe/London", user_id=1)

            # Invalid
            with pytest.raises(ValueError):
                SettingsManager.set_in_db("app_timezone", "Invalid/Timezone", user_id=1)

    def test_app_settings_convenience_methods(self, app, sample_settings):
        """Test AppSettings convenience namespace."""
        with app.app_context():
            assert AppSettings.app_timezone() == "America/Mexico_City"
            assert AppSettings.public_pause_available_from_seconds() == 0
            assert AppSettings.public_pause_available_until_after_end_minutes() == 5
            assert AppSettings.public_confirm_window_days() == 30
