"""Admin API endpoint for application settings management."""

import os
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.models.app_setting import AppSetting
from app.services.settings_manager import SettingsManager
from app.utils.auth_helpers import require_admin
from app import db

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
        return jsonify({"error": "Falló al obtener la configuración"}), 500


@admin_settings_bp.route("/<key>", methods=["GET"])
@jwt_required()
@require_admin
def get_setting(key: str):
    """Get a single setting by key."""
    try:
        setting = AppSetting.find_by_key(key)
        if not setting:
            return jsonify({"error": f'Configuración "{key}" no encontrada'}), 404

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
        return jsonify({"error": "Falló al obtener la configuración"}), 500


@admin_settings_bp.route("/<key>", methods=["PUT"])
@jwt_required()
@require_admin
def update_setting(key: str):
    """Update a setting value (admin only)."""
    try:
        user_id = get_jwt_identity()
        body = request.get_json() or {}

        # Support updating either `value`, `description`, or both.
        new_value = body.get("value")
        new_description = body.get("description")

        if new_value is None and new_description is None:
            return jsonify(
                {"error": "Falta valor o descripción en el cuerpo de la solicitud"},
                400,
            )

        # First, if value provided, update via SettingsManager (validation & locking)
        if new_value is not None:
            SettingsManager.set_in_db(key, new_value, user_id=user_id)

        # If description provided, update directly on the model (no locking)
        if new_description is not None:
            setting = AppSetting.find_by_key(key)
            if not setting:
                return (
                    jsonify({"error": f'Setting "{key}" not found'}),
                    404,
                )
            # Limit description length to model constraint
            if new_description and len(new_description) > 500:
                return (
                    jsonify(
                        {"error": "Descripción demasiado larga (máx. 500 caracteres)"}
                    ),
                    400,
                )
            setting.description = new_description
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(
                    f"[admin_settings] Failed saving description for '{key}': {e}"
                )
                return jsonify(
                    {"error": "Fallo al actualizar la descripción de la configuración"}
                ), 500

        # Return updated setting
        setting = AppSetting.find_by_key(key)
        if not setting:
            return (
                jsonify(
                    {
                        "error": f'Configuración "{key}" no encontrada después de la actualización'
                    }
                ),
                404,
            )
        return (
            jsonify(
                {
                    "key": setting.key,
                    "value": setting.value,
                    "description": setting.description,
                    "message": f'Configuración "{key}" actualizada correctamente',
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
        return jsonify({"error": "Fallo al actualizar la configuración"}), 500

    except Exception as e:
        current_app.logger.error(
            f"[admin_settings] Unexpected error updating '{key}': {e}"
        )
        return jsonify({"error": "Error interno del servidor"}), 500


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
            return jsonify({"error": f'No hay valor por defecto para "{key}"'}), 400

        SettingsManager.set_in_db(key, setting.default_value, user_id=user_id)

        return (
            jsonify(
                {
                    "key": setting.key,
                    "value": setting.default_value,
                    "message": f'Configuración "{key}" reiniciada al valor por defecto',
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"[admin_settings] Error resetting '{key}': {e}")
        return jsonify({"error": "Fallo al reiniciar la configuración"}), 500
