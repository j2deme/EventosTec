"""Settings manager service for hierarchical configuration (ENV > BD > Cache > Defaults)."""

import os
from typing import Any, Optional
from datetime import datetime
from flask import current_app


class SettingsManager:
    """
    Hierarchical configuration manager with caching and locking.

    Priority order (ENV > BD Cache > Defaults):
    1. Environment variable (APP_{KEY_UPPER})
    2. Database value (cached in-memory for TTL seconds)
    3. Default value

    Features:
    - Automatic locking if ENV variable is set (UI cannot override)
    - In-memory caché with configurable TTL (default 10 seconds)
    - Automatic fallback to defaults if BD unavailable
    - Type conversion (string, integer, boolean, timezone)
    - Input validation before storing in BD
    """

    # In-memory cache: {key: (value, timestamp)}
    _cache = {}
    _cache_ttl_seconds = 10

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """
        Retrieve a configuration value with hierarchical lookup.

        Args:
            key: Configuration key (e.g., 'app_timezone')
            default: Fallback value if not found anywhere

        Returns:
            Configuration value (from ENV, BD cache, or default)
        """
        # Step 1: Check ENV (highest priority)
        env_key = f"APP_{key.upper()}"
        env_value = os.environ.get(env_key)
        if env_value is not None:
            return cls._parse_value(env_value, cls._infer_type(key))

        # Step 2: Check BD cache (medium priority)
        try:
            cached_value = cls._get_from_cache(key)
            if cached_value is not None:
                return cached_value
        except Exception as e:
            current_app.logger.warning(
                f"[SettingsManager] Error reading settings cache for {key}: {e}"
            )

        # Step 3: Use default (lowest priority)
        return default

    @classmethod
    def set_in_db(cls, key: str, value: Any, user_id: Optional[int] = None) -> bool:
        """
        Set a configuration value in the database.

        Preconditions:
        - The key must not be locked by an ENV variable
        - Value must pass validation for its data_type

        Args:
            key: Configuration key
            value: New value (will be stringified)
            user_id: ID of admin making the change (for audit)

        Returns:
            True if successful

        Raises:
            ValueError: If key is locked by ENV or validation fails
            RuntimeError: If DB write fails
        """
        from app.models.app_setting import AppSetting
        from app import db

        # Check if this key is locked by ENV
        env_key = f"APP_{key.upper()}"
        if os.environ.get(env_key) is not None:
            raise ValueError(
                f"Setting '{key}' is locked by environment variable '{env_key}'. "
                "Cannot be modified via UI."
            )

        # Fetch or create the setting record
        setting = AppSetting.find_by_key(key)
        if setting is None:
            raise ValueError(f"Setting key '{key}' does not exist.")

        if not setting.is_editable:
            raise ValueError(f"Setting '{key}' is not editable.")

        # Validate the value according to its type
        cls._validate_value(value, setting.data_type)

        # Update BD
        try:
            setting.value = str(value)
            setting.updated_at = datetime.utcnow()
            setting.updated_by_user_id = user_id
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise RuntimeError(f"Failed to update setting '{key}': {e}")

        # Invalidate cache for this key
        cls._invalidate_cache(key)

        current_app.logger.info(
            f"[SettingsManager] Setting '{key}' updated to '{value}' by user {user_id}"
        )

        return True

    @classmethod
    def _get_from_cache(cls, key: str) -> Optional[Any]:
        """Get value from cache if fresh, else read from BD and cache."""
        now = datetime.utcnow()

        # Return cached value if still fresh
        if key in cls._cache:
            cached_value, cached_time = cls._cache[key]
            if (now - cached_time).total_seconds() < cls._cache_ttl_seconds:
                return cached_value

        # Cache stale or missing: read from BD
        from app.models.app_setting import AppSetting

        try:
            setting = AppSetting.find_by_key(key)

            if setting and setting.value is not None:
                parsed_value = cls._parse_value(setting.value, setting.data_type)
                cls._cache[key] = (parsed_value, now)
                return parsed_value
        except Exception as e:
            current_app.logger.warning(
                f"[SettingsManager] Error reading setting '{key}' from BD: {e}"
            )

        return None

    @classmethod
    def _invalidate_cache(cls, key: str) -> None:
        """Remove key from cache, forcing reload from BD on next get()."""
        if key in cls._cache:
            del cls._cache[key]
            current_app.logger.debug(f"[SettingsManager] Cache invalidated for '{key}'")

    @classmethod
    def _parse_value(cls, value: str, data_type: str) -> Any:
        """Parse string value to appropriate Python type."""
        if data_type == "integer":
            return int(value)
        elif data_type == "float":
            return float(value)
        elif data_type == "boolean":
            return value.lower() in ("true", "1", "yes", "on")
        elif data_type == "timezone":
            # Validate IANA timezone name
            try:
                import pytz

                pytz.timezone(value)
            except Exception:
                raise ValueError(f"Invalid timezone: {value}")
            return value
        else:  # string
            return str(value)

    @classmethod
    def _validate_value(cls, value: Any, data_type: str) -> None:
        """Validate value before storing in BD."""
        if data_type == "integer":
            if not isinstance(value, int):
                try:
                    int(value)
                except (ValueError, TypeError):
                    raise ValueError(f"Expected integer, got {value}")

        elif data_type == "float":
            if not isinstance(value, (int, float)):
                try:
                    float(value)
                except (ValueError, TypeError):
                    raise ValueError(f"Expected float, got {value}")

        elif data_type == "boolean":
            if not isinstance(value, bool):
                if str(value).lower() not in ("true", "false", "1", "0", "yes", "no"):
                    raise ValueError(f"Expected boolean, got {value}")

        elif data_type == "timezone":
            try:
                import pytz

                pytz.timezone(str(value))
            except Exception as e:
                raise ValueError(f"Invalid timezone '{value}': {e}")

    @classmethod
    def _infer_type(cls, key: str) -> str:
        """Infer data type from key name."""
        if "timezone" in key.lower():
            return "timezone"
        elif any(word in key.lower() for word in ["seconds", "minutes", "days"]):
            return "integer"
        elif key.endswith("_flag") or "enabled" in key.lower():
            return "boolean"
        else:
            return "string"


class AppSettings:
    """
    Convenience namespace for common settings lookups.
    Reduces need to use string keys directly.
    """

    @staticmethod
    def app_timezone() -> str:
        """Get application timezone (default: America/Mexico_City)."""
        return SettingsManager.get("app_timezone", "America/Mexico_City")

    @staticmethod
    def public_pause_available_from_seconds() -> int:
        """Get seconds after activity start when pause becomes available (default: 0)."""
        return SettingsManager.get("public_pause_available_from_seconds", 0)

    @staticmethod
    def public_pause_available_until_after_end_minutes() -> int:
        """Get minutes after activity end to keep pause available (default: 5)."""
        return SettingsManager.get("public_pause_available_until_after_end_minutes", 5)

    @staticmethod
    def public_confirm_window_days() -> int:
        """Get days window for confirming attendance (default: 30)."""
        return SettingsManager.get("public_confirm_window_days", 30)
