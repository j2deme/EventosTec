# app/api/admin_bp.py
"""Endpoints administrativos de operación interna (impersonación, etc.)."""
from datetime import timedelta

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import create_access_token, jwt_required

from app import db
from app.models.student import Student
from app.utils.auth_helpers import get_current_user, require_admin

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")

# Duración del token de impersonación: sesión corta y auditada.
IMPERSONATION_TTL_MINUTES = 30


@admin_bp.route("/impersonate", methods=["POST"])
@jwt_required()
@require_admin
def impersonate_student():
    """Emite un token de estudiante de corta duración para impersonación.

    Caso de uso: el estudiante no puede ingresar a su cuenta y acude a
    oficina; el admin abre su sesión para operar en su nombre.

    El token emitido:
    - trae el claim ``type=student`` (se resuelve como Student incluso si la
      PK numérica colisiona con un User);
    - trae ``imp=true`` y ``admin_id`` para trazabilidad;
    - caduca en 30 minutos y se revoca con el logout normal (blocklist).

    El evento queda registrado en logs como rastro de auditoría.
    """
    try:
        payload = request.get_json() or {}
        try:
            student_id = int(payload.get("student_id"))
        except (TypeError, ValueError):
            return (
                jsonify({"message": "student_id es requerido y debe ser numérico"}),
                400,
            )

        student = db.session.get(Student, student_id)
        if not student:
            return jsonify({"message": "Estudiante no encontrado"}), 404

        # require_admin ya validó el rol; obtener el admin para la auditoría
        admin, _admin_type = get_current_user()
        admin_id = admin.id if admin is not None else None

        token = create_access_token(
            identity=str(student.id),
            additional_claims={
                "type": "student",
                "imp": True,
                "admin_id": admin_id,
            },
            expires_delta=timedelta(minutes=IMPERSONATION_TTL_MINUTES),
        )

        current_app.logger.info(
            "IMPERSONATION: admin_id=%s username=%s -> student_id=%s control=%s",
            admin_id,
            getattr(admin, "username", None),
            student.id,
            student.control_number,
        )

        return (
            jsonify(
                {
                    "access_token": token,
                    "expires_in": IMPERSONATION_TTL_MINUTES * 60,
                    "student": {**student.to_dict(), "type": "student"},
                    "admin": {
                        "id": admin_id,
                        "username": getattr(admin, "username", None),
                    },
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error en /api/admin/impersonate")
        return (
            jsonify(
                {
                    "message": "Error al generar el token de impersonación",
                    "error": str(e),
                }
            ),
            500,
        )
