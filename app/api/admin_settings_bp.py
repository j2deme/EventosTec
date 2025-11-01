"""Admin API endpoint for application settings management."""

import os
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.models.app_setting import AppSetting
from app.services.settings_manager import SettingsManager
from app.utils.auth_helpers import require_admin

admin_settings_bp = Blueprint(
    "admin_settings", __name__, url_prefix="/admin/api/settings"
)


@admin_settings_bp.route("", methods=["GET"])
@jwt_required()
@require_admin
def list_all_settings():
    """Get all application settings (admin only)."""
    try:
        settings = AppSetting.query.all()
        result = []

        for setting in settings:
            # Check if locked by ENV
            env_key = f"APP_{setting.key.upper()}"
            env_value = os.environ.get(env_key)

            created_at_iso = (
                setting.created_at.isoformat()
                if getattr(setting, "created_at", None)
                else None
            )
            updated_at_iso = (
                setting.updated_at.isoformat()
                if getattr(setting, "updated_at", None)
                else None
            )

            result.append(
                {
                    "key": setting.key,
                    "value": setting.value,
                    "description": setting.description,
                    "data_type": setting.data_type,
                    "default_value": setting.default_value,
                    "is_editable": setting.is_editable and env_value is None,
                    "is_locked_by_env": env_value is not None,
                    "created_at": created_at_iso,
                    "updated_at": updated_at_iso,
                }
            )

        return jsonify({"settings": result}), 200

    except Exception as e:
        current_app.logger.error(f"[admin_settings] Error fetching settings: {e}")
        return jsonify({"error": "Failed to fetch settings"}), 500


@admin_settings_bp.route("/<key>", methods=["GET"])
@jwt_required()
@require_admin
def get_setting(key: str):
    """Get a single setting by key."""
    try:
        setting = AppSetting.find_by_key(key)
        if not setting:
            return jsonify({"error": f'Setting "{key}" not found'}), 404

        env_key = f"APP_{key.upper()}"
        env_value = os.environ.get(env_key)

        return (
            jsonify(
                {
                    "key": setting.key,
                    "value": setting.value,
                    "effective_value": env_value
                    or setting.value,  # Show which value is actually used
                    "description": setting.description,
                    "data_type": setting.data_type,
                    "is_locked_by_env": env_value is not None,
                    "is_editable": setting.is_editable and env_value is None,
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(
            f"[admin_settings] Error fetching setting '{key}': {e}"
        )
        return jsonify({"error": "Failed to fetch setting"}), 500


@admin_settings_bp.route("/<key>", methods=["PUT"])
@jwt_required()
@require_admin
def update_setting(key: str):
    """Update a setting value (admin only)."""
    try:
        user_id = get_jwt_identity()
        body = request.get_json() or {}
        new_value = body.get("value")

        if new_value is None:
            return jsonify({"error": 'Missing "value" in request body'}), 400

        # Attempt to update via SettingsManager (handles validation, locking, etc.)
        SettingsManager.set_in_db(key, new_value, user_id=user_id)

        # Return updated setting
        setting = AppSetting.find_by_key(key)
        if not setting:
            # Shouldn't normally happen (SettingsManager would raise), but
            # guard here to satisfy static analysis and avoid AttributeError.
            return jsonify({"error": f'Setting "{key}" not found after update'}), 404
        return (
            jsonify(
                {
                    "key": setting.key,
                    "value": setting.value,
                    "message": f'Setting "{key}" updated successfully',
                }
            ),
            200,
        )

    except ValueError as e:
        # Validation error (e.g., locked by ENV, invalid timezone)
        current_app.logger.warning(
            f"[admin_settings] Validation error updating '{key}': {e}"
        )
        return jsonify({"error": str(e)}), 400

    except RuntimeError as e:
        # DB error
        current_app.logger.error(
            f"[admin_settings] Error updating setting '{key}': {e}"
        )
        return jsonify({"error": "Failed to update setting"}), 500

    except Exception as e:
        current_app.logger.error(
            f"[admin_settings] Unexpected error updating '{key}': {e}"
        )
        return jsonify({"error": "Internal server error"}), 500


@admin_settings_bp.route("/<key>/reset", methods=["POST"])
@jwt_required()
@require_admin
def reset_setting_to_default(key: str):
    """Reset a setting to its default value."""
    try:
        user_id = get_jwt_identity()
        setting = AppSetting.find_by_key(key)

        if not setting:
            return jsonify({"error": f'Setting "{key}" not found'}), 404

        if setting.default_value is None:
            return jsonify({"error": f'No default value for "{key}"'}), 400

        SettingsManager.set_in_db(key, setting.default_value, user_id=user_id)

        return (
            jsonify(
                {
                    "key": setting.key,
                    "value": setting.default_value,
                    "message": f'Setting "{key}" reset to default',
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"[admin_settings] Error resetting '{key}': {e}")
        return jsonify({"error": "Failed to reset setting"}), 500
