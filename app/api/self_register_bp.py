from flask import Blueprint, request, jsonify, render_template, current_app
import requests
from app import db
from app.models.student import Student
from app.models.activity import Activity
from app.models.registration import Registration
from app.models.attendance import Attendance
from app.schemas import attendance_schema
from datetime import datetime, timedelta, timezone
from app.utils.datetime_utils import localize_naive_datetime, safe_iso
# token utilities deprecated for public flows; do not import generative helpers

self_register_bp = Blueprint("self_register", __name__, url_prefix="")


# use centralized safe_iso from app.utils.datetime_utils


@self_register_bp.route("/self-register", methods=["GET"])
@self_register_bp.route("/public/self-register/<path:activity_ref>", methods=["GET"])
def self_register_form(activity_ref=None):
    """Self-registration form view. Resolve activity by:
    1. Slug first (preferred, from DB public_slug)
    2. Numeric ID (fallback, from path param or query param)
    """
    activity = None
    activity_name = None
    activity_exists = False
    bool(activity_ref is not None)
    activity_ref_invalid = False

    # Try to resolve activity from path param (activity_ref can be slug or token)
    if activity_ref:
        # First, try as slug (prefer DB lookup)
        try:
            activity = Activity.query.filter_by(public_slug=activity_ref).first()
        except Exception:
            activity = None

        # If still not found, try as numeric ID (fallback)
        if not activity:
            try:
                if str(activity_ref).isdigit():
                    activity = db.session.get(Activity, int(activity_ref))
            except Exception:
                activity = None

        if not activity:
            activity_ref_invalid = True

    # Legacy: accept raw activity id from query param
    if not activity:
        aid = request.args.get("activity")
        if aid:
            try:
                activity = db.session.get(Activity, int(aid))
                if activity:
                    activity_name = activity.name
                    activity_exists = True
            except Exception:
                pass

    if activity:
        activity_name = activity.name
        activity_exists = True

    activity_start_iso = None
    activity_duration_hours = None
    activity_deadline_iso = None
    activity_type = None
    if activity:
        # start datetime (localized to UTC for consistency)
        if getattr(activity, "start_datetime", None) is not None:
            try:
                app_tz = current_app.config.get("APP_TIMEZONE", "America/Mexico_City")
                s_local = localize_naive_datetime(activity.start_datetime, app_tz)
                activity_start_iso = (
                    safe_iso(s_local)
                    if s_local is not None
                    else safe_iso(activity.start_datetime)
                )
            except Exception:
                activity_start_iso = None

        # compute a safe float for duration_hours
        try:
            hours_val = getattr(activity, "duration_hours", None)
            activity_duration_hours = (
                float(hours_val) if hours_val is not None else None
            )
        except Exception:
            activity_duration_hours = None

        # compute registration deadline = start + 20 minutes (use localized UTC)
        try:
            start_dt = getattr(activity, "start_datetime", None)
            if start_dt is not None:
                app_tz = current_app.config.get("APP_TIMEZONE", "America/Mexico_City")
                s_local = localize_naive_datetime(start_dt, app_tz)
                if s_local is not None:
                    deadline_dt = s_local + timedelta(minutes=20)
                    activity_deadline_iso = safe_iso(deadline_dt)
                else:
                    activity_deadline_iso = None
        except Exception:
            activity_deadline_iso = None
        try:
            activity_type = getattr(activity, "activity_type", None) or None
        except Exception:
            activity_type = None

    # Prepare template context: prefer public_slug for activity_id if available
    activity_id_out = None
    if activity:
        activity_id_out = getattr(activity, "public_slug", None) or str(activity.id)

    # Determine whether activity is allowed for self-register (time window)
    activity_allowed = True
    error_message = None
    try:
        now = datetime.now(timezone.utc)
        cutoff = None
        if activity is not None and getattr(activity, "start_datetime", None):
            app_tz = current_app.config.get("APP_TIMEZONE", "America/Mexico_City")
            s_local = localize_naive_datetime(activity.start_datetime, app_tz)
            if s_local is not None:
                cutoff = s_local + timedelta(minutes=20)
        if cutoff and now > cutoff:
            activity_allowed = False
            error_message = "La ventana de registro in situ ha terminado"
    except Exception:
        pass

    return render_template(
        "public/self_register.html",
        activity_id=activity_id_out,
        activity_name=activity_name,
        activity_exists=activity_exists,
        activity_allowed=activity_allowed,
        activity_invalid=activity_ref_invalid,
        error_message=error_message,
        activity_start_iso=activity_start_iso,
        activity_duration_hours=activity_duration_hours,
        activity_deadline_iso=activity_deadline_iso,
        activity_type=activity_type,
    )


@self_register_bp.route("/api/registrations/self", methods=["POST"])
def self_register_api():
    try:
        payload = request.get_json() or {}
        control_number = (payload.get("control_number") or "").strip()
        password = payload.get("password")
        activity_ref = payload.get("activity_id")

        if not control_number or not password or not activity_ref:
            return jsonify(
                {"message": "control_number, password y activity_id son requeridos"}
            ), 400

        # Resolve activity_ref (slug preferred, else numeric id)
        activity = (
            Activity.query.filter_by(public_slug=activity_ref).first()
            if activity_ref
            else None
        )
        if not activity and str(activity_ref).isdigit():
            activity = db.session.get(Activity, int(activity_ref))

        if not activity:
            return jsonify({"message": "Actividad no encontrada"}), 404

        # Use timezone-aware datetimes for comparison to avoid naive/aware errors
        now = datetime.now(timezone.utc)
        cutoff = None
        if getattr(activity, "start_datetime", None):
            app_tz = current_app.config.get("APP_TIMEZONE", "America/Mexico_City")
            s_local = localize_naive_datetime(activity.start_datetime, app_tz)
            if s_local is not None:
                cutoff = s_local + timedelta(minutes=20)

        if cutoff and now > cutoff:
            return jsonify(
                {"message": "La ventana de registro in situ ha terminado"}
            ), 400

        # Authenticate student against external validation endpoint by calling internal auth route
        # We call the existing student-login endpoint internally to reuse its logic.
        auth_url = request.host_url.rstrip("/") + "/api/auth/student-login"
        try:
            r = requests.post(
                auth_url,
                json={"control_number": control_number, "password": password},
                timeout=5,
            )
        except requests.RequestException as e:
            return jsonify(
                {
                    "message": "Error conectando al servicio de validación de credenciales",
                    "error": str(e),
                }
            ), 503

        if r.status_code != 200:
            # propagate 401 or 503 as appropriate
            if r.status_code == 401:
                return jsonify({"message": "Credenciales inválidas"}), 401
            return jsonify({"message": "Error en la validación de credenciales"}), 503

        auth_data = r.json()
        student_info = auth_data.get("student")
        if not student_info:
            return jsonify(
                {
                    "message": "No se obtuvo información del estudiante tras validar credenciales"
                }
            ), 503

        # Ensure student exists/updated in DB
        student = Student.query.filter_by(control_number=control_number).first()
        if not student:
            student = Student()
            student.control_number = control_number
            student.full_name = (
                student_info.get("full_name") or student_info.get("name") or ""
            )
            student.email = student_info.get("email") or ""
            db.session.add(student)
            db.session.commit()
        else:
            # update small fields
            student.full_name = (
                student_info.get("full_name")
                or student_info.get("name")
                or student.full_name
            )
            student.email = student_info.get("email") or student.email
            db.session.add(student)
            db.session.commit()

        # Check existing attendance for this student+activity and refuse duplicates
        existing_att = Attendance.query.filter_by(
            student_id=student.id, activity_id=activity.id
        ).first()
        if existing_att:
            return jsonify(
                {"message": "Ya existe un registro de asistencia para esta actividad"}
            ), 409

        # Create attendance (self check-in). For magistral activities we record
        # a check-in time and mark as 'Parcial' (same behavior as admin check-in).
        now = datetime.now(timezone.utc)
        attendance = Attendance()
        attendance.student_id = student.id
        attendance.activity_id = activity.id
        attendance.check_in_time = now
        attendance.status = "Parcial"
        db.session.add(attendance)

        # If there's an existing registration, mark it as attended/confirmed
        registration = Registration.query.filter_by(
            student_id=student.id, activity_id=activity.id
        ).first()
        if registration:
            registration.attended = True
            registration.status = "Asistió"
            registration.confirmation_date = db.func.now()
            db.session.add(registration)

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return jsonify(
                {"message": "Error al crear registro de asistencia", "error": str(e)}
            ), 500

        try:
            db.session.refresh(attendance)
        except Exception:
            pass

        return jsonify(
            {
                "message": "Asistencia registrada",
                "attendance": attendance_schema.dump(attendance),
            }
        ), 201

    except Exception as e:
        db.session.rollback()
        return jsonify(
            {"message": "Error al procesar registro in situ", "error": str(e)}
        ), 500
