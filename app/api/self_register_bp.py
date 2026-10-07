from flask import Blueprint, request, jsonify, render_template, current_app
from datetime import datetime, timezone

from app import db
from app.models.activity import Activity
from app.models.registration import Registration
from app.models.attendance import Attendance
from app.schemas import attendance_schema
from app.services.self_register_service import (
    OPEN,
    self_register_state,
    window_message,
)
from app.services.student_auth_service import (
    RATE_LIMIT_MESSAGE,
    CredentialServiceUnavailable,
    CredentialsRateLimited,
    InvalidCredentials,
    upsert_student,
    validate_student_credentials,
)
from app.utils.datetime_utils import localize_naive_datetime, safe_iso
from app.utils.datetime_utils import db_wall_local

# token utilities deprecated for public flows; do not import generative helpers

self_register_bp = Blueprint("self_register", __name__, url_prefix="")


def _find_activity(ref):
    """Resuelve una actividad: slug primero (preferido), ID numérico al final."""
    if ref is None or ref == "":
        return None

    activity = None
    try:
        activity = Activity.query.filter_by(public_slug=ref).first()
    except Exception:
        activity = None

    if not activity and str(ref).isdigit():
        try:
            activity = db.session.get(Activity, int(ref))
        except Exception:
            activity = None

    return activity


def _resolve_activity(activity_ref=None):
    """Resuelve la actividad de la vista pública.

    Returns:
        ``(activity, invalid)`` — ``invalid`` marca un reference inexistente
        (para distinguir "QR inválido" de "sin actividad").
    """
    invalid = False
    activity = _find_activity(activity_ref)

    if activity_ref and not activity:
        invalid = True

    # Legacy: aceptar el id crudo por query param (?activity=<id>)
    if not activity:
        aid = request.args.get("activity")
        if aid:
            try:
                activity = db.session.get(Activity, int(aid))
            except Exception:
                activity = None

    return activity, invalid


@self_register_bp.route("/self-register", methods=["GET"])
@self_register_bp.route("/public/self-register/<path:activity_ref>", methods=["GET"])
def self_register_form(activity_ref=None):
    """Self-registration form view. Resolve activity by:
    1. Slug first (preferred, from DB public_slug)
    2. Numeric ID (fallback, from path param or query param)
    """
    activity, activity_ref_invalid = _resolve_activity(activity_ref)

    activity_name = getattr(activity, "name", None)
    activity_exists = activity is not None

    activity_start_iso = None
    activity_duration_hours = None
    activity_deadline_iso = None
    activity_type = None

    state = OPEN
    opens_at = None
    closes_at = None

    if activity:
        # start datetime (localizado a UTC para el countdown del cliente)
        start_dt = getattr(activity, "start_datetime", None)
        if start_dt is not None:
            try:
                app_tz = current_app.config.get("APP_TIMEZONE", "America/Mexico_City")
                s_local = localize_naive_datetime(start_dt, app_tz)
                activity_start_iso = (
                    safe_iso(s_local) if s_local is not None else safe_iso(start_dt)
                )
            except Exception:
                activity_start_iso = None

        try:
            hours_val = getattr(activity, "duration_hours", None)
            activity_duration_hours = (
                float(hours_val) if hours_val is not None else None
            )
        except Exception:
            activity_duration_hours = None

        # Ventana de auto-registro (fuente única: self_register_service)
        state, opens_at, closes_at = self_register_state(activity)
        if closes_at is not None:
            activity_deadline_iso = safe_iso(closes_at)

        try:
            activity_type = getattr(activity, "activity_type", None) or None
        except Exception:
            activity_type = None

    # Determina si la actividad admite self-register (ventana configurable)
    activity_allowed = state == OPEN
    error_message = window_message(state, opens_at, closes_at)

    # Preferir public_slug como identificador de la actividad (el POST lo
    # resuelve con la misma estrategia slug-first).
    activity_id_out = None
    if activity:
        activity_id_out = getattr(activity, "public_slug", None) or str(activity.id)

    return render_template(
        "public/self_register.html",
        activity_id=activity_id_out,
        activity_name=activity_name,
        activity_exists=activity_exists,
        activity_allowed=activity_allowed,
        activity_invalid=activity_ref_invalid,
        error_message=error_message,
        activity_message=error_message,
        activity_start_iso=activity_start_iso,
        activity_duration_hours=activity_duration_hours,
        activity_deadline_iso=activity_deadline_iso,
        activity_type=activity_type,
    )


@self_register_bp.route("/api/registrations/self", methods=["POST"])
def self_register_api():
    """Self check-in: abre una sesión de asistencia (status 'Parcial').

    No acredita por sí mismo: la Registration del estudiante queda intacta y
    se cierra recién en el checkout del admin (>= 80% -> 'Asistió',
    < 80% -> 'Ausente'). Ver ``attendance_service.sync_registration_status``.
    """
    try:
        payload = request.get_json() or {}
        control_number = (payload.get("control_number") or "").strip()
        password = payload.get("password")
        activity_ref = payload.get("activity_id")

        if not control_number or not password or not activity_ref:
            return (
                jsonify(
                    {"message": "control_number, password y activity_id son requeridos"}
                ),
                400,
            )

        activity = _find_activity(activity_ref)
        if not activity:
            return jsonify({"message": "Actividad no encontrada"}), 404

        # Ventana configurable (mismo criterio que la vista del formulario)
        state, _opens_at, _closes_at = self_register_state(activity)
        if state != OPEN:
            return (
                jsonify({"message": window_message(state, _opens_at, _closes_at)}),
                400,
            )

        # Credenciales contra la plataforma MAB: validación en proceso con
        # rate-limit compartido con /api/auth/student-login.
        try:
            student_info = validate_student_credentials(control_number, password)
        except CredentialsRateLimited:
            current_app.logger.info("self-register limitado (%s)", control_number)
            return jsonify({"message": RATE_LIMIT_MESSAGE}), 429
        except InvalidCredentials:
            return jsonify({"message": "Credenciales inválidas"}), 401
        except CredentialServiceUnavailable:
            current_app.logger.warning(
                "self-register: sistema externo no disponible (%s)", control_number
            )
            return (
                jsonify(
                    {
                        "message": (
                            "Servicio de validación no disponible. "
                            "Intenta de nuevo en unos minutos."
                        )
                    }
                ),
                503,
            )

        # Asegurar que el estudiante exista/esté actualizado en la BD local
        student = upsert_student(control_number, student_info)
        db.session.commit()

        # Rechazar duplicados: una sola sesión de asistencia por actividad
        existing_att = Attendance.query.filter_by(
            student_id=student.id, activity_id=activity.id
        ).first()
        if existing_att:
            return (
                jsonify(
                    {
                        "message": "Ya existe un registro de asistencia para esta actividad"
                    }
                ),
                409,
            )

        # Self check-in: abre la sesión. 'Parcial' = presente pero sin cerrar.
        now = datetime.now(timezone.utc)
        attendance = Attendance()
        attendance.student_id = student.id
        attendance.activity_id = activity.id
        attendance.check_in_time = db_wall_local(now)
        attendance.status = "Parcial"
        db.session.add(attendance)

        # Si había preregistro NO se cambia su estado aquí: el resultado
        # final se decide en el checkout del admin. Solo se marca `attended`
        # para que la lista pública muestre "Confirmado" (y no "No asistió")
        # mientras la sesión sigue abierta.
        registration = Registration.query.filter_by(
            student_id=student.id, activity_id=activity.id
        ).first()
        if registration:
            registration.attended = True
            db.session.add(registration)

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception(
                "self-register: error creando la asistencia (%s)", activity.id
            )
            return jsonify({"message": "Error al crear registro de asistencia"}), 500

        try:
            db.session.refresh(attendance)
        except Exception:
            pass

        return (
            jsonify(
                {
                    "message": "Asistencia registrada",
                    "attendance": attendance_schema.dump(attendance),
                }
            ),
            201,
        )

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Error al procesar auto-registro")
        return jsonify({"message": "Error al procesar el auto-registro"}), 500
