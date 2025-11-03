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

        # Determine whether we should include debug details (only in dev-like envs)
        debug_mode = (
            current_app.config.get("DEBUG")
            or os.environ.get("FLASK_CONFIG") == "development"
            or current_app.config.get("ENV") == "development"
        )

        for setting in settings:
            # Check if locked by ENV
            # Compute possible env keys and which one is present
            env_key = SettingsManager._env_key_for(setting.key)
            plain_key = setting.key.upper()
            app_key = f"APP_{plain_key}"
            env_value = os.environ.get(env_key)
            attempted = [app_key, plain_key]

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
                    # Debug info (only meaningful when debug_mode=True)
                    "_debug": {
                        "attempted_env_keys": attempted,
                        "env_key_used": env_key if env_value is not None else None,
                        "env_value": env_value,
                        "db_value": setting.value,
                        "effective_source": (
                            "env"
                            if env_value is not None
                            else ("db" if setting.value is not None else "default")
                        ),
                    },
                }
            )

        return jsonify({"settings": result, "debug_mode": bool(debug_mode)}), 200

    except Exception as e:
        current_app.logger.error(
            f"[admin_settings] Error al obtener configuraciones: {e}"
        )
        return jsonify({"error": "Error al obtener configuraciones"}), 500


@admin_settings_bp.route("/<key>", methods=["GET"])
@jwt_required()
@require_admin
def get_setting(key: str):
    """Get a single setting by key."""
    try:
        setting = AppSetting.find_by_key(key)
        if not setting:
            return jsonify({"error": f'Configuración "{key}" no encontrada'}), 404

        env_key = SettingsManager._env_key_for(key)
        env_value = os.environ.get(env_key)

        return (
            jsonify(
                {
                    "key": setting.key,
                    "value": setting.value,
                    "effective_value": env_value
                    or setting.value,  # Muestra el valor efectivo usado
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
            f"[admin_settings] Error al obtener la configuración '{key}': {e}"
        )
        return jsonify({"error": "Error al obtener la configuración"}), 500


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
            return (
                jsonify(
                    {"error": "Falta valor o descripción en el cuerpo de la solicitud"}
                ),
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
                    jsonify({"error": f'Configuración "{key}" no encontrada'}),
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
                    f"[admin_settings] Error al guardar la descripción de '{key}': {e}"
                )
                return jsonify(
                    {"error": "Error al actualizar la descripción de la configuración"}
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
        # Error de validación (p. ej. bloqueada por ENV, zona horaria inválida)
        msg = str(e)
        # Map some common validation messages to Spanish-friendly text
        if (
            "locked by environment variable" in msg
            or "bloqueada por environment" in msg
        ):
            user_msg = "La configuración está bloqueada por una variable de entorno y no puede modificarse desde la interfaz."
        elif "does not exist" in msg or "does not exist" in msg:
            user_msg = "La configuración solicitada no existe."
        elif "not editable" in msg or "not editable" in msg:
            user_msg = "La configuración no es editable."
        elif "Invalid timezone" in msg or "Invalid timezone" in msg:
            # Preserve specific timezone value if present
            user_msg = f"Zona horaria inválida: {msg.split(':')[-1].strip()}"
        else:
            user_msg = f"Error de validación: {msg}"

        current_app.logger.warning(
            f"[admin_settings] Error de validación al actualizar '{key}': {msg}"
        )
        return jsonify({"error": user_msg}), 400

    except RuntimeError as e:
        # DB error
        current_app.logger.error(
            f"[admin_settings] Error al actualizar la configuración '{key}': {e}"
        )
        return jsonify({"error": "Fallo al actualizar la configuración"}), 500

    except Exception as e:
        current_app.logger.error(
            f"[admin_settings] Error inesperado al actualizar la configuración '{key}': {e}"
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
            return jsonify({"error": f'Configuración "{key}" no encontrada'}), 404

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
        current_app.logger.error(f"[admin_settings] Error al reiniciar '{key}': {e}")
        return jsonify({"error": "Error al reiniciar la configuración"}), 500
