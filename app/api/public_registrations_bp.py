from flask import Blueprint, request, jsonify, render_template, current_app, send_file
from app import db
from app.models.activity import Activity
from app.models.registration import Registration
from app.models.attendance import Attendance
from app.models.student import Student
from datetime import datetime, timedelta, timezone
import requests
from app.utils.slug_utils import slugify as canonical_slugify
from app.utils.datetime_utils import localize_naive_datetime, safe_iso
from sqlalchemy.exc import IntegrityError
import io
import re
import traceback
import pandas as pd

public_registrations_bp = Blueprint("public_registrations", __name__, url_prefix="")


def resolve_activity_by_id(activity_id):
    """
    Resuelve una actividad a partir de activity_id.
    Estrategia: intenta primero como slug (si no es numérico), luego como ID numérico.
    Retorna la Activity encontrada o None.
    """
    if not activity_id:
        return None

    activity = None
    activity_id_str = str(activity_id).strip()

    # Intentar por slug primero (preferido), luego fallback a ID numérico
    try:
        activity = Activity.query.filter_by(public_slug=activity_id_str).first()
    except Exception:
        activity = None

    # Si no se encontró por slug y el valor parece numérico, intentar por ID
    if not activity and activity_id_str.isdigit():
        try:
            activity = db.session.get(Activity, int(activity_id_str))
        except Exception:
            activity = None

    return activity


# use centralized safe_iso from app.utils.datetime_utils


@public_registrations_bp.route(
    "/public/registrations/<path:activity_ref>", methods=["GET"]
)
def public_registrations_view(activity_ref):
    """Resolve an activity by slug (public_slug from DB, preferred) or numeric ID.

    Accepted formats for activity_ref:
      - activity.public_slug (from DB, preferred)
      - numeric activity.id (fallback)

    Returns: registrations_public.html with activity details and registrations.
    """
    activity = None

    # Slug-first + ID fallback strategy
    # 1. Try to find activity by public_slug (prefer DB lookup)
    try:
        activity = Activity.query.filter_by(public_slug=activity_ref).first()
    except Exception:
        activity = None

    # 2. Try numeric id as fallback
    if not activity:
        try:
            if str(activity_ref).isdigit():
                activity = db.session.get(Activity, int(activity_ref))
        except Exception:
            activity = None

    if not activity:
        return render_template(
            "public/registrations_public.html",
            activity_id="",
            activity_name="",
            activity_invalid=True,
            activity_allowed=False,
            error_message="Actividad no encontrada",
        )

    # Prepare context
    activity_name = activity.name
    activity_type = getattr(activity, "activity_type", None)
    activity_deadline_iso = None
    activity_start_iso = None
    activity_end_iso = None
    activity_location = getattr(activity, "location", None)
    activity_modality = getattr(activity, "modality", None)
    event_name = None
    event_id = getattr(activity, "event_id", None)
    event_slug = None
    activity_slug = None

    try:
        # confirmation window: localize activity.end_datetime then add configured days (default 30)
        window_days = int(current_app.config.get("PUBLIC_CONFIRM_WINDOW_DAYS", 30))
        if getattr(activity, "end_datetime", None) is not None:
            app_timezone = current_app.config.get("APP_TIMEZONE", "America/Mexico_City")
            end_dt = localize_naive_datetime(activity.end_datetime, app_timezone)
            if end_dt is not None:
                deadline_dt = end_dt + timedelta(days=window_days)
                activity_deadline_iso = safe_iso(deadline_dt)
    except Exception:
        activity_deadline_iso = None

    try:
        app_timezone = current_app.config.get("APP_TIMEZONE", "America/Mexico_City")
        if getattr(activity, "start_datetime", None) is not None:
            sdt = localize_naive_datetime(activity.start_datetime, app_timezone)
            if sdt is not None:
                activity_start_iso = safe_iso(sdt)
            else:
                activity_start_iso = safe_iso(activity.start_datetime)
        if getattr(activity, "end_datetime", None) is not None:
            edt = localize_naive_datetime(activity.end_datetime, app_timezone)
            if edt is not None:
                activity_end_iso = safe_iso(edt)
            else:
                activity_end_iso = safe_iso(activity.end_datetime)
    except Exception:
        activity_start_iso = None
        activity_end_iso = None

    try:
        # event relation may be lazy; try to read name
        event_name = (
            getattr(activity, "event").name
            if getattr(activity, "event", None)
            else None
        )
    except Exception:
        event_name = None

    # Get event slug from database (Activity -> Event -> public_slug)
    if event_id:
        try:
            from app.models.event import Event

            evt = db.session.get(Event, int(event_id))
            if evt and evt.public_slug:
                event_slug = evt.public_slug
            elif evt and evt.name:
                event_slug = canonical_slugify(evt.name)
        except Exception:
            event_slug = None

    # Get activity slug from database
    try:
        activity_slug = (
            activity.public_slug
            if activity.public_slug
            else canonical_slugify(activity.name or "")
        )
    except Exception:
        activity_slug = None

    return render_template(
        "public/registrations_public.html",
        activity_id=activity.public_slug if activity.public_slug else activity.id,
        activity_name=activity_name,
        activity_type=activity_type,
        activity_deadline_iso=activity_deadline_iso,
        activity_start_iso=activity_start_iso,
        activity_end_iso=activity_end_iso,
        activity_location=activity_location,
        activity_modality=activity_modality,
        event_name=event_name,
        event_id=event_id,
        event_slug=event_slug,
        activity_slug=activity_slug,
    )


@public_registrations_bp.route("/api/public/registrations", methods=["GET"])
def api_list_registrations():
    # Extract activity_id from query param (slug or numeric)
    activity_id = request.args.get("activity_id")
    page = int(request.args.get("page") or 1)
    per_page = int(request.args.get("per_page") or 20)

    if not activity_id:
        return jsonify({"message": "activity_id es requerido"}), 400

    # Resolve activity using slug-first strategy
    activity = resolve_activity_by_id(activity_id)

    if not activity:
        return jsonify({"message": "Actividad no encontrada"}), 404

    # Merge registrations and attendance-only records so the UI can display
    # participants coming from either source. Strategy:
    #  - Load all registrations for the activity
    #  - Load all attendances for the activity and map them by student_id
    #  - For registrations, attach attendance info if present
    #  - For attendances without a registration, synthesize a row
    #  - Merge, sort by control_number (fallback by name), and apply pagination in Python

    regs_all = Registration.query.filter_by(activity_id=activity.id).all()
    atts_all = Attendance.query.filter_by(activity_id=activity.id).all()

    # Map attendances by student_id for quick lookup
    atts_by_student = {}
    for a in atts_all:
        if a.student_id:
            # prefer the first attendance per student for display
            if a.student_id not in atts_by_student:
                atts_by_student[a.student_id] = a

    items = []
    registration_student_ids = set()

    def _is_excluded_status(status_obj):
        """Return True if status_obj represents an excluded status (ausente/cancelado).

        Handles strings, Enum members (checking .name and .value) and falls back
        to str(). Comparison is case-insensitive and tolerant (checks substring
        'ausente' or 'cancel').
        """
        try:
            if not status_obj:
                return False
            candidates = []
            if isinstance(status_obj, str):
                candidates.append(status_obj)
            else:
                # Enum-like: try value and name
                val = getattr(status_obj, "value", None)
                name = getattr(status_obj, "name", None)
                if val is not None:
                    candidates.append(val)
                if name is not None:
                    candidates.append(name)
                # fallback to str()
                candidates.append(str(status_obj))

            for c in candidates:
                if not c:
                    continue
                s = str(c).strip().lower()
                if "ausente" in s or "cancel" in s:
                    return True
            return False
        except Exception:
            return False

    for r in regs_all:
        # skip registrations explicitly marked as Ausente or Cancelado
        if _is_excluded_status(getattr(r, "status", None)):
            continue
        student = r.student
        registration_student_ids.add(r.student_id)
        attendance = atts_by_student.get(r.student_id)
        items.append(
            {
                "id": r.id,
                "registration_id": r.id,
                "attendance_id": attendance.id if attendance else None,
                "student_id": student.id if student else None,
                "control_number": student.control_number if student else None,
                "student_name": student.full_name if student else r.name or None,
                "email": student.email if student else None,
                "status": r.status,
                "attended": bool(r.attended),
                "registration_date": safe_iso(getattr(r, "registration_date", None)),
                "check_in_time": safe_iso(getattr(attendance, "check_in_time", None))
                if attendance
                else None,
                "notes": getattr(r, "notes", None),
                "source": "registration",
            }
        )

    # Add attendance-only rows (those students without a registration)
    for a in atts_all:
        if a.student_id in registration_student_ids:
            continue
        # also skip attendance rows where status is ausente/cancelado
        try:
            if _is_excluded_status(getattr(a, "status", None)):
                continue
        except Exception:
            pass
        student = a.student
        items.append(
            {
                "id": None,
                "registration_id": None,
                "attendance_id": a.id,
                "student_id": student.id if student else None,
                "control_number": student.control_number if student else None,
                "student_name": student.full_name if student else None,
                "email": student.email if student else None,
                "status": getattr(a, "status", "Asistió"),
                "attended": True,
                "registration_date": None,
                "check_in_time": safe_iso(getattr(a, "check_in_time", None)),
                "notes": None,
                "source": "attendance",
            }
        )

    # Sort by control_number if present, fallback to student_name
    def sort_key(it):
        cn = it.get("control_number") or ""
        # pad numeric-like values for better lexicographic order
        try:
            return (cn.zfill(20), it.get("student_name") or "")
        except Exception:
            return (cn, it.get("student_name") or "")

    items.sort(key=sort_key)

    # Apply server-side search filter (if provided)
    q = (request.args.get("q") or "").strip()
    if q:
        q_lower = q.lower()

        def matches_query(it):
            # check control_number (as substring) and student_name (case-insensitive)
            cn = it.get("control_number")
            name = it.get("student_name")
            try:
                if cn and q_lower in str(cn).lower():
                    return True
            except Exception:
                pass
            try:
                if name and q_lower in str(name).lower():
                    return True
            except Exception:
                pass
            return False

        items = [it for it in items if matches_query(it)]

    total = len(items)
    start = (page - 1) * per_page
    end = start + per_page
    page_items = items[start:end]

    return jsonify(
        {
            "registrations": page_items,
            "total": total,
            "page": page,
            "per_page": per_page,
        }
    ), 200


@public_registrations_bp.route(
    "/api/public/registrations/lookup-student", methods=["GET"]
)
def api_public_lookup_student():
    """Lookup a student by control_number for a given activity.

    Query params: activity_id=<int|slug>, control_number=<string>
    Behavior:
      - Verify activity (by slug or ID)
      - Try to find Student locally by control_number
      - If found: return { found: True, student: {...}, created: False }
      - Else: query external validation API; if found, create local Student and return { found: True, student: {...}, created: True }
      - Else: return { found: False }
    """
    activity_id = request.args.get("activity_id")
    control_number = (request.args.get("control_number") or "").strip()

    if not control_number:
        return jsonify({"found": False}), 400

    if not activity_id:
        return jsonify({"found": False}), 400

    # Resolve activity using slug-first strategy
    activity = resolve_activity_by_id(activity_id)

    if not activity:
        return jsonify({"found": False}), 404

    # Try local DB first
    student = Student.query.filter_by(control_number=control_number).first()
    if student:
        return jsonify(
            {
                "found": True,
                "student": student.to_dict()
                if hasattr(student, "to_dict")
                else {
                    "id": student.id,
                    "full_name": student.full_name,
                    "control_number": student.control_number,
                },
                "created": False,
            }
        ), 200

    # Not found locally -> try external API (reuse same endpoint used by walkin)
    external_api = (
        f"http://apps.tecvalles.mx:8091/api/validate/student?username={control_number}"
    )
    try:
        resp = requests.get(external_api, timeout=5)
    except requests.exceptions.RequestException:
        current_app.logger.exception(
            "Error contacting external student API for %s", control_number
        )
        return jsonify({"found": False}), 200

    if resp.status_code == 404:
        current_app.logger.debug("External API returned 404 for %s", control_number)
        return jsonify({"found": False}), 200

    if resp.status_code != 200:
        current_app.logger.warning(
            "External API returned status %s for %s", resp.status_code, control_number
        )
        # log response body truncated for debugging (avoid huge logs)
        try:
            txt = resp.text or ""
            current_app.logger.debug("External API body: %s", txt[:1000])
        except Exception:
            pass
        return jsonify({"found": False}), 200

    try:
        data = resp.json() if resp.text else {}
    except Exception:
        current_app.logger.exception(
            "Invalid JSON from external student API for %s", control_number
        )
        data = {}

    # Normalize response similar to walkin behavior
    d = data if isinstance(data, dict) else {}
    career = d.get("career") or d.get("carrera") or {}
    career_name = None
    if isinstance(career, dict):
        career_name = career.get("name") or career.get("nombre")
    else:
        career_name = career

    ext_control = d.get("username") or d.get("control_number") or control_number
    ext_full_name = d.get("name") or d.get("full_name") or d.get("nombre")
    ext_email = d.get("email") or ""

    if not ext_control or not ext_full_name:
        current_app.logger.warning(
            "External student data incomplete for %s: control=%s name=%s",
            control_number,
            ext_control,
            ext_full_name,
        )
        return jsonify({"found": False}), 200

    # Create local Student safely inside a transaction
    try:
        student = Student()
        student.control_number = ext_control
        student.full_name = ext_full_name
        student.email = ext_email
        student.career = career_name
        db.session.add(student)
        db.session.commit()
        current_app.logger.info(
            "Created local student %s (%s) from external API",
            student.full_name,
            student.control_number,
        )
        return jsonify(
            {
                "found": True,
                "student": student.to_dict()
                if hasattr(student, "to_dict")
                else {
                    "id": student.id,
                    "full_name": student.full_name,
                    "control_number": student.control_number,
                },
                "created": True,
            }
        ), 201
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Error creating local student for %s", control_number
        )
        return jsonify({"found": False}), 200


@public_registrations_bp.route(
    "/api/public/registrations/<int:reg_id>/confirm", methods=["POST"]
)
def api_confirm_registration(reg_id):
    payload = request.get_json() or {}
    activity_id = payload.get("activity_id")
    confirm = bool(payload.get("confirm", True))
    create_attendance = bool(payload.get("create_attendance", True))
    mark_absent = bool(payload.get("mark_absent", False))

    if not activity_id:
        return jsonify({"message": "activity_id es requerido"}), 400

    reg = db.session.get(Registration, reg_id)
    if not reg or reg.activity_id != int(activity_id):
        return jsonify({"message": "Registro no encontrado para esta actividad"}), 404

    # enforce confirmation window
    activity = db.session.get(Activity, int(activity_id))
    if not activity:
        return jsonify({"message": "Actividad no encontrada"}), 404

    window_days = int(current_app.config.get("PUBLIC_CONFIRM_WINDOW_DAYS", 30))
    if getattr(activity, "end_datetime", None) is not None:
        app_timezone = current_app.config.get("APP_TIMEZONE", "America/Mexico_City")
        end_dt = localize_naive_datetime(activity.end_datetime, app_timezone)
        if end_dt is None:
            return jsonify({"message": "La ventana de confirmación ha expirado"}), 400
        cutoff = end_dt + timedelta(days=window_days)
        now = datetime.now(timezone.utc)
        if now > cutoff:
            return jsonify({"message": "La ventana de confirmación ha expirado"}), 400

    # update registration
    if confirm:
        reg.attended = True
        reg.status = "Asistió"
        reg.confirmation_date = db.func.now()
    else:
        # Desconfirmación: two possible flows
        if mark_absent:
            # explicit request to mark as Ausente
            reg.attended = False
            reg.status = "Ausente"
            reg.confirmation_date = db.func.now()
        else:
            # revert to preregistro state
            reg.attended = False
            reg.status = "Registrado"
            reg.confirmation_date = None
    db.session.add(reg)

    # create attendance if requested, avoid duplicates
    attendance = None
    if confirm and create_attendance:
        # check existing attendance
        existing = Attendance.query.filter_by(
            student_id=reg.student_id, activity_id=reg.activity_id
        ).first()
        if not existing:
            attendance = Attendance()
            attendance.student_id = reg.student_id
            attendance.activity_id = reg.activity_id
            attendance.check_in_time = datetime.now(timezone.utc)
            # 'status' is an Enum('Asistió','Parcial','Ausente') in the model.
            # Use a valid value to avoid DB errors; map internal labels to 'Asistió'.
            attendance.status = "Asistió"
            db.session.add(attendance)
    else:
        # if un-confirming, remove existing attendance created earlier (if any)
        existing = Attendance.query.filter_by(
            student_id=reg.student_id, activity_id=reg.activity_id
        ).first()
        if existing:
            try:
                db.session.delete(existing)
                attendance = None
            except Exception:
                # failure to delete should not break the flow; will be rolled back later
                pass

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        # Log full exception server-side for debugging without leaking internals to clients
        current_app.logger.exception("Error confirming registration %s", reg_id)
        return jsonify({"message": "Error al confirmar"}), 500

    # Return updated registration representation to help frontend update row without refetch
    if hasattr(reg, "to_dict"):
        reg_dict = reg.to_dict()
    else:
        conf = getattr(reg, "confirmation_date", None)
        reg_dict = {
            "id": reg.id,
            "attended": reg.attended,
            "status": reg.status,
            "confirmation_date": safe_iso(conf),
        }
    # Ensure attended is explicitly a boolean in API responses
    try:
        if isinstance(reg_dict, dict) and "attended" in reg_dict:
            reg_dict["attended"] = bool(reg_dict.get("attended"))
    except Exception:
        # defensive: if coercion fails, leave as-is
        pass
    return jsonify(
        {
            "message": "Confirmación registrada",
            "registration_id": reg.id,
            "attendance_id": attendance.id if attendance else None,
            "registration": reg_dict,
        }
    ), 200


@public_registrations_bp.route("/api/public/registrations/walkin", methods=["POST"])
def api_walkin():
    payload = request.get_json(silent=True) or {}
    # Accept activity_id (slug or numeric)
    activity_id = payload.get("activity_id")
    control_number = (payload.get("control_number") or "").strip()
    payload.get("full_name")
    payload.get("email")
    # optional external student payload (from frontend's external lookup)
    payload.get("external_student")

    # Require activity_id and control_number
    if not control_number:
        return jsonify({"message": "control_number es requerido"}), 400

    if not activity_id:
        return jsonify({"message": "activity_id es requerido"}), 400

    # Resolve activity using slug-first strategy
    activity = resolve_activity_by_id(activity_id)

    if not activity:
        return jsonify({"message": "Actividad no encontrada"}), 404

    # allow walk-in within confirmation window
    window_days = int(current_app.config.get("PUBLIC_CONFIRM_WINDOW_DAYS", 30))
    if getattr(activity, "end_datetime", None) is not None:
        app_timezone = current_app.config.get("APP_TIMEZONE", "America/Mexico_City")
        end_dt = localize_naive_datetime(activity.end_datetime, app_timezone)
        if end_dt is None:
            return jsonify({"message": "La ventana de confirmación ha expirado"}), 400
        cutoff = end_dt + timedelta(days=window_days)
        now = datetime.now(timezone.utc)
        if now > cutoff:
            return jsonify({"message": "La ventana de confirmación ha expirado"}), 400

    # find existing student locally
    student = Student.query.filter_by(control_number=control_number).first()
    if not student:
        # Backend will call the external validation API to fetch student data
        # and create the Student locally. This prevents trusting client payloads.
        external_api = f"http://apps.tecvalles.mx:8091/api/validate/student?username={control_number}"
        try:
            resp = requests.get(external_api, timeout=8)
        except requests.exceptions.RequestException:
            return jsonify({"message": "Error conectando al servicio externo"}), 503

        if resp.status_code == 404:
            return jsonify(
                {"message": "Estudiante no encontrado en sistema externo"}
            ), 404
        if resp.status_code != 200:
            return jsonify({"message": "Error desde servicio externo"}), 503

        try:
            data = resp.json()
        except Exception:
            return jsonify({"message": "Respuesta externa inválida"}), 502

        # Normalize payload similar to students_bp.validate_student_proxy
        if (
            isinstance(data, dict)
            and "data" in data
            and isinstance(data.get("data"), dict)
        ):
            data = data.get("data")

        d = data if isinstance(data, dict) else {}

        career = d.get("career") or d.get("carrera") or {}
        career_name = None
        if isinstance(career, dict):
            career_name = career.get("name") or career.get("nombre") or None
        else:
            career_name = career

        ext_control = d.get("username") or d.get("control_number") or control_number
        ext_full_name = d.get("name") or d.get("full_name") or d.get("nombre")
        ext_email = d.get("email") or ""

        if not ext_control or not ext_full_name:
            return jsonify(
                {"message": "Datos externos incompletos para crear estudiante"}
            ), 502

        # Create student inside DB transaction below (so registration+attendance are atomic)
        # We'll create it here but don't commit until the outer try/commit
        try:
            student = Student()
            student.control_number = ext_control
            student.full_name = ext_full_name
            student.career = career_name
            student.email = ext_email
            db.session.add(student)
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            # Concurrent creation: try to load again
            student = Student.query.filter_by(control_number=control_number).first()
            if not student:
                current_app.logger.exception(
                    "IntegrityError creating student during walk-in"
                )
                return jsonify({"message": "Conflicto al crear estudiante"}), 409

    # perform all DB changes in a single transaction for atomicity
    try:
        # If a Registration exists, mark it attended; DO NOT create a new Registration
        # when none existed previously. The walk-in flow should create only the
        # Attendance record for students without a preregistro.
        reg = Registration.query.filter_by(
            student_id=student.id, activity_id=activity.id
        ).first()
        if reg:
            # If registration exists but not marked attended, mark it
            if not reg.attended:
                reg.attended = True
                reg.status = "Asistió"
                reg.confirmation_date = db.func.now()
                db.session.add(reg)

        # avoid duplicate attendance
        existing = Attendance.query.filter_by(
            student_id=student.id, activity_id=activity.id
        ).first()
        if existing:
            # Return conflict with existing attendance info
            return jsonify(
                {
                    "message": "Ya existe una asistencia registrada para este estudiante",
                    "attendance": existing.to_dict(),
                }
            ), 409

        attendance = Attendance()
        attendance.student_id = student.id
        attendance.activity_id = activity.id
        attendance.check_in_time = datetime.now(timezone.utc)
        attendance.status = "Asistió"
        db.session.add(attendance)
        db.session.flush()

        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        current_app.logger.exception(
            "Integrity error creating walk-in for activity %s", activity.id
        )
        return jsonify({"message": "Conflicto al crear walk-in"}), 409
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Error creating walk-in for activity %s", activity.id
        )
        return jsonify({"message": "Error al crear walk-in"}), 500

    # Build response with created/updated resources
    resp = {
        "message": "Walk-in registrado",
        "student": student.to_dict()
        if hasattr(student, "to_dict")
        else {"id": student.id},
        "attendance": attendance.to_dict()
        if hasattr(attendance, "to_dict")
        else {"id": attendance.id, "student_id": student.id},
        # include registration only if it existed
        "registration": (
            reg.to_dict()
            if reg and hasattr(reg, "to_dict")
            else (reg and {"id": reg.id, "student_id": student.id} or None)
        ),
    }
    # Normalize registration.attended to boolean when present
    try:
        r = resp.get("registration")
        if isinstance(r, dict) and "attended" in r:
            r["attended"] = bool(r.get("attended"))
    except Exception:
        pass
    return jsonify(resp), 201


@public_registrations_bp.route(
    "/api/public/attendances/<int:attendance_id>/toggle", methods=["POST"]
)
def api_toggle_attendance(attendance_id):
    payload = request.get_json(silent=True) or {}
    activity_id = payload.get("activity_id")
    # confirm: True means ensure attendance exists; False means remove it
    confirm = bool(payload.get("confirm", True))

    if not activity_id:
        return jsonify({"message": "activity_id es requerido"}), 400

    # Resolve activity using slug-first strategy
    activity = resolve_activity_by_id(activity_id)

    if not activity:
        return jsonify({"message": "Actividad no encontrada"}), 404

    att = db.session.get(Attendance, int(attendance_id))
    if not att or att.activity_id != activity.id:
        return jsonify({"message": "Asistencia no encontrada para esta actividad"}), 404

    # Only allow deletion (un-mark) via public flow for attendance-only rows.
    # If confirm is False, delete the attendance record.
    if not confirm:
        try:
            # If there is a registration linked to this student and activity, do not touch it here.
            db.session.delete(att)
            db.session.commit()
            return jsonify(
                {"message": "Asistencia removida", "attendance_id": attendance_id}
            ), 200
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Error deleting attendance %s", attendance_id)
            return jsonify({"message": "Error al eliminar asistencia"}), 500

    # For confirm=True, if attendance already exists we simply return ok
    return jsonify(
        {"message": "Asistencia existente", "attendance_id": attendance_id}
    ), 200


@public_registrations_bp.route(
    "/public/pause-attendance/<path:activity_ref>", methods=["GET"]
)
def public_pause_attendance_view(activity_ref):
    """Public view for pausing/resuming attendances for Magistral activities.

    Accepts:
      - activity.public_slug (preferred)
      - public token (fallback)
      - numeric activity.id (fallback)
    """
    # Resolve activity by slug (preferred) or numeric id (fallback)
    activity = resolve_activity_by_id(activity_ref)

    # If activity not found, render template indicating invalid reference
    if not activity:
        return render_template(
            "public/pause_attendance.html",
            activity_id="",
            activity_name="",
            activity_invalid=True,
            activity_allowed=False,
            error_message="Actividad no encontrada",
        )

    # Only allow for Magistral activities
    if getattr(activity, "activity_type", None) != "Magistral":
        return render_template(
            "public/pause_attendance.html",
            activity_id="",
            activity_name=activity.name,
            activity_invalid=False,
            activity_allowed=False,
            error_message="Solo disponible para conferencias magistrales",
        )

    # Check time window: for public pause/resume we allow from NOW until configured minutes after end
    now = datetime.now(timezone.utc)
    app_timezone = current_app.config.get("APP_TIMEZONE", "America/Mexico_City")

    end_dt = activity.end_datetime
    if end_dt is None:
        return render_template(
            "public/pause_attendance.html",
            activity_id="",
            activity_name=activity.name,
            activity_invalid=False,
            activity_allowed=False,
            error_message="Actividad sin fecha de finalización",
        )

    end_dt = localize_naive_datetime(end_dt, app_timezone)
    if end_dt is None:
        return render_template(
            "public/pause_attendance.html",
            activity_id="",
            activity_name=activity.name,
            activity_invalid=False,
            activity_allowed=False,
            error_message="Actividad inválida",
        )

    from_seconds = int(current_app.config.get("PUBLIC_PAUSE_AVAILABLE_FROM_SECONDS", 0))
    until_minutes = int(
        current_app.config.get("PUBLIC_PAUSE_AVAILABLE_UNTIL_AFTER_END_MINUTES", 5)
    )

    start_dt = activity.start_datetime
    if from_seconds > 0 and start_dt is not None:
        start_dt = localize_naive_datetime(start_dt, app_timezone)
        if start_dt is None:
            available_from = now
        else:
            available_from = start_dt + timedelta(seconds=from_seconds)
    else:
        available_from = now

    available_until = end_dt + timedelta(minutes=until_minutes)

    if now < available_from:
        return render_template(
            "public/pause_attendance.html",
            activity_id="",
            activity_name=activity.name,
            activity_invalid=False,
            activity_allowed=False,
            error_message=f"Esta vista estará disponible a partir de {safe_iso(available_from)}",
        )

    if now > available_until:
        return render_template(
            "public/pause_attendance.html",
            activity_id="",
            activity_name=activity.name,
            activity_invalid=False,
            activity_allowed=False,
            error_message="La ventana pública de control ha expirado.",
        )

    # Ok — activity allowed: pass activity_id (prefer slug) and name to template
    activity_id = activity.public_slug if activity.public_slug else activity.id
    return render_template(
        "public/pause_attendance.html",
        activity_id=activity_id,
        activity_name=activity.name,
        activity_invalid=False,
        activity_allowed=True,
    )


@public_registrations_bp.route("/public/pause-attendance", methods=["GET"])
def public_pause_attendance_query():
    # Accept activity_ref (slug or ID) as query param
    activity_ref = request.args.get("activity_ref") or request.args.get("slug") or ""
    return public_pause_attendance_view(activity_ref)


@public_registrations_bp.route(
    "/public/staff-walkin/<path:activity_ref>", methods=["GET"]
)
def public_staff_walkin_view(activity_ref):
    """Mobile-first public view for staff to register walk-ins quickly via activity slug or ID."""
    activity = resolve_activity_by_id(activity_ref)

    if not activity:
        return render_template(
            "public/staff_walkin.html",
            activity_id="",
            activity_name="",
            activity_invalid=True,
            activity_allowed=False,
            error_message="Actividad no encontrada",
        )

    if getattr(activity, "activity_type", None) != "Magistral":
        return render_template(
            "public/staff_walkin.html",
            activity_id="",
            activity_name=activity.name if activity else "",
            activity_invalid=False,
            activity_allowed=False,
            error_message="Solo disponible para conferencias magistrales",
        )

    # include start datetime ISO so frontend can compute staff registration window
    activity_start_iso = None
    try:
        if getattr(activity, "start_datetime", None) is not None:
            app_tz = current_app.config.get("APP_TIMEZONE", "America/Mexico_City")
            sdt = localize_naive_datetime(activity.start_datetime, app_tz)
            if sdt is not None:
                activity_start_iso = safe_iso(sdt)
            else:
                activity_start_iso = safe_iso(activity.start_datetime)
    except Exception:
        activity_start_iso = None

    activity_id = activity.public_slug if activity.public_slug else activity.id
    return render_template(
        "public/staff_walkin.html",
        activity_id=activity_id,
        activity_name=activity.name,
        activity_start_iso=activity_start_iso,
        activity_invalid=False,
        activity_allowed=True,
    )


@public_registrations_bp.route("/public/staff-walkin", methods=["GET"])
def public_staff_walkin_query():
    # Accept activity_ref (slug or ID) as query param
    activity_ref = request.args.get("activity_ref") or request.args.get("slug") or ""
    if activity_ref:
        return public_staff_walkin_view(activity_ref)
    return render_template(
        "public/staff_walkin.html",
        activity_id="",
        activity_name="",
        activity_invalid=True,
        activity_allowed=False,
    )


@public_registrations_bp.route("/public/event/<path:event_ref>", methods=["GET"])
def public_event_registrations_view(event_ref):
    """Resolve an event by slug (public_slug from DB, preferred) or numeric ID
    and render the public event view page with list of activities.

    Accepted formats for event_ref:
      - event.public_slug (from DB, preferred)
      - numeric event.id (fallback)

    Returns: event_registrations_public.html with:
      - event_slug (from DB public_slug or fallback slugified name)
      - event_id
      - event_name
    """
    found_event = None

    # Slug-first + ID fallback strategy
    # 1. Try to find event by public_slug (prefer DB lookup)
    try:
        from app.models.event import Event

        found_event = Event.query.filter_by(public_slug=event_ref).first()
    except Exception:
        found_event = None

    # 2. Try numeric id as fallback
    if not found_event:
        try:
            if str(event_ref).isdigit():
                found_event = db.session.get(Event, int(event_ref))
        except Exception:
            found_event = None

    if not found_event:
        # Invalid event reference: render error state
        return render_template(
            "public/event_registrations_public.html",
            event_name=event_ref or "Evento no encontrado",
            event_id=None,
            event_slug="",
            event_invalid=True,
        )

    # Log resolution for debugging: which event_ref resolved to which event id/slug
    try:
        current_app.logger.debug(
            f"public_event_registrations_view: event_ref={event_ref} -> id={found_event.id} slug={getattr(found_event, 'public_slug', None)}"
        )
    except Exception:
        pass

    # Prefer public_slug from DB; fallback to slugified name for display
    event_slug = (
        found_event.public_slug
        if found_event.public_slug
        else canonical_slugify(found_event.name or "")
    )

    return render_template(
        "public/event_registrations_public.html",
        event_name=found_event.name,
        event_id=found_event.id,
        event_slug=event_slug,
    )


@public_registrations_bp.route("/api/public/attendances/search", methods=["GET"])
def api_public_search_attendances():
    """Search attendances for a specific activity using activity_id (slug or numeric)."""
    activity_id = request.args.get("activity_id")
    search = request.args.get("search", "").strip()

    if not activity_id:
        return jsonify({"message": "activity_id es requerido"}), 400

    # Resolve activity using slug-first strategy
    activity = resolve_activity_by_id(activity_id)

    if not activity:
        return jsonify({"message": "Actividad no encontrada"}), 404

    # Only allow for Magistral activities
    if getattr(activity, "activity_type", None) != "Magistral":
        return jsonify(
            {"message": "Solo disponible para conferencias magistrales"}
        ), 400

    # Check time window: public search available from NOW until 5 minutes after end
    now = datetime.now(timezone.utc)

    # Get app timezone configuration
    app_timezone = current_app.config.get("APP_TIMEZONE", "America/Mexico_City")

    end_dt = activity.end_datetime
    if end_dt is None:
        return jsonify({"attendances": [], "total": 0, "page": 1, "per_page": 0}), 200

    # Use localize_naive_datetime to properly handle naive datetimes
    end_dt = localize_naive_datetime(end_dt, app_timezone)
    if end_dt is None:
        return jsonify({"message": "Actividad inválida o no encontrada."}), 400

    from_seconds = int(current_app.config.get("PUBLIC_PAUSE_AVAILABLE_FROM_SECONDS", 0))
    until_minutes = int(
        current_app.config.get("PUBLIC_PAUSE_AVAILABLE_UNTIL_AFTER_END_MINUTES", 5)
    )

    start_dt = activity.start_datetime
    if from_seconds > 0 and start_dt is not None:
        start_dt = localize_naive_datetime(start_dt, app_timezone)
        if start_dt is None:
            available_from = now
        else:
            available_from = start_dt + timedelta(seconds=from_seconds)
    else:
        available_from = now

    available_until = end_dt + timedelta(minutes=until_minutes)

    if now < available_from:
        return jsonify({"attendances": [], "total": 0, "page": 1, "per_page": 0}), 200

    if now > available_until:
        return jsonify({"attendances": [], "total": 0, "page": 1, "per_page": 0}), 200

    if not search:
        return jsonify({"attendances": []}), 200

    # Search attendances for this activity
    query = Attendance.query.filter_by(activity_id=activity.id)
    query = query.join(Student)
    query = query.filter(
        db.or_(
            Student.full_name.ilike(f"%{search}%"),
            Student.control_number.ilike(f"%{search}%"),
        )
    )
    # Only return attendances with check_in_time (active or paused)
    query = query.filter(Attendance.check_in_time.isnot(None))
    attendances = query.all()

    # Serialize with student info
    result = []
    for att in attendances:
        try:
            student = att.student if hasattr(att, "student") else None
            result.append(
                {
                    "id": att.id,
                    "student_id": att.student_id,
                    "student_name": student.full_name if student else "",
                    "student_identifier": getattr(student, "control_number", "")
                    if student
                    else "",
                    "is_paused": att.is_paused,
                    "check_in_time": safe_iso(getattr(att, "check_in_time", None)),
                    "check_out_time": safe_iso(getattr(att, "check_out_time", None)),
                }
            )
        except Exception:
            continue

    return jsonify({"attendances": result}), 200


@public_registrations_bp.route(
    "/api/public/attendances/<int:attendance_id>/pause", methods=["POST"]
)
def api_public_pause_attendance(attendance_id):
    """Pause an attendance via activity_id (slug or numeric) or token."""
    payload = request.get_json(silent=True) or {}
    activity_id = payload.get("activity_id")
    payload.get("token")

    # Try to resolve activity from activity_id (slug or numeric) first, then token
    activity = None
    if activity_id:
        try:
            if str(activity_id).isdigit():
                activity = db.session.get(Activity, int(activity_id))
            else:
                activity = Activity.query.filter_by(
                    public_slug=str(activity_id)
                ).first()
        except Exception:
            activity = None

    # No token fallback: resolve only via activity_id (slug or numeric)
    if not activity:
        return jsonify({"message": "Actividad no encontrada"}), 404

    # Only allow for Magistral activities
    if getattr(activity, "activity_type", None) != "Magistral":
        return jsonify(
            {"message": "Solo disponible para conferencias magistrales"}
        ), 400

    # Check time window: public pause available from NOW until 5 minutes after end
    now = datetime.now(timezone.utc)

    # Get app timezone configuration
    app_timezone = current_app.config.get("APP_TIMEZONE", "America/Mexico_City")

    end_dt = activity.end_datetime
    if end_dt is None:
        return jsonify({"message": "Actividad inválida o no encontrada."}), 400

    # Use localize_naive_datetime to properly handle naive datetimes
    end_dt = localize_naive_datetime(end_dt, app_timezone)
    if end_dt is None:
        return jsonify({"message": "Token inválido o actividad no encontrada."}), 400

    from_seconds = int(current_app.config.get("PUBLIC_PAUSE_AVAILABLE_FROM_SECONDS", 0))
    until_minutes = int(
        current_app.config.get("PUBLIC_PAUSE_AVAILABLE_UNTIL_AFTER_END_MINUTES", 5)
    )

    start_dt = activity.start_datetime
    if from_seconds > 0 and start_dt is not None:
        start_dt = localize_naive_datetime(start_dt, app_timezone)
        if start_dt is None:
            available_from = now
        else:
            available_from = start_dt + timedelta(seconds=from_seconds)
    else:
        available_from = now

    available_until = end_dt + timedelta(minutes=until_minutes)

    if now < available_from:
        return jsonify(
            {
                "message": f"Esta funcionalidad estará disponible a partir de {safe_iso(available_from)}"
            }
        ), 403

    if now > available_until:
        return jsonify({"message": "La ventana pública de control ha expirado."}), 403

    att = db.session.get(Attendance, int(attendance_id))
    if not att or att.activity_id != activity.id:
        return jsonify({"message": "Asistencia no encontrada para esta actividad"}), 404

    if not att.check_in_time:
        return jsonify({"message": "No se ha registrado check-in"}), 400

    if att.check_out_time:
        return jsonify({"message": "Ya se ha registrado check-out"}), 400

    if att.is_paused:
        return jsonify({"message": "La asistencia ya está pausada"}), 400

    try:
        from app.services.attendance_service import pause_attendance as svc_pause

        attendance = svc_pause(att.id)
        db.session.add(attendance)
        db.session.commit()

        return jsonify({"message": "Asistencia pausada exitosamente"}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error pausing attendance %s", attendance_id)
        return jsonify({"message": "Error al pausar asistencia", "error": str(e)}), 400


@public_registrations_bp.route(
    "/api/public/attendances/<int:attendance_id>/resume", methods=["POST"]
)
def api_public_resume_attendance(attendance_id):
    """Resume a paused attendance via activity_id (slug or numeric) or token."""
    payload = request.get_json(silent=True) or {}
    activity_id = payload.get("activity_id")
    payload.get("token")

    # Try to resolve activity from activity_id (slug or numeric) first, then token
    activity = None
    if activity_id:
        try:
            if str(activity_id).isdigit():
                activity = db.session.get(Activity, int(activity_id))
            else:
                activity = Activity.query.filter_by(
                    public_slug=str(activity_id)
                ).first()
        except Exception:
            activity = None

    # No token fallback: resolve only via activity_id (slug or numeric)
    if not activity:
        return jsonify({"message": "Actividad no encontrada"}), 404

    # Only allow for Magistral activities
    if getattr(activity, "activity_type", None) != "Magistral":
        return jsonify(
            {"message": "Solo disponible para conferencias magistrales"}
        ), 400

    # Check time window: public resume available from NOW until 5 minutes after end
    now = datetime.now(timezone.utc)

    # Get app timezone configuration
    app_timezone = current_app.config.get("APP_TIMEZONE", "America/Mexico_City")

    end_dt = activity.end_datetime
    if end_dt is None:
        return jsonify({"message": "Token inválido o actividad no encontrada."}), 400

    # Use localize_naive_datetime to properly handle naive datetimes
    end_dt = localize_naive_datetime(end_dt, app_timezone)
    if end_dt is None:
        return jsonify({"message": "Token inválido o actividad no encontrada."}), 400

    from_seconds = int(current_app.config.get("PUBLIC_PAUSE_AVAILABLE_FROM_SECONDS", 0))
    until_minutes = int(
        current_app.config.get("PUBLIC_PAUSE_AVAILABLE_UNTIL_AFTER_END_MINUTES", 5)
    )

    start_dt = activity.start_datetime
    if from_seconds > 0 and start_dt is not None:
        start_dt = localize_naive_datetime(start_dt, app_timezone)
        if start_dt is None:
            available_from = now
        else:
            available_from = start_dt + timedelta(seconds=from_seconds)
    else:
        available_from = now

    available_until = end_dt + timedelta(minutes=until_minutes)

    if now < available_from:
        return jsonify(
            {
                "message": f"Esta funcionalidad estará disponible a partir de {safe_iso(available_from)}"
            }
        ), 403

    if now > available_until:
        return jsonify({"message": "La ventana pública de control ha expirado."}), 403

    att = db.session.get(Attendance, int(attendance_id))
    if not att or att.activity_id != activity.id:
        return jsonify({"message": "Asistencia no encontrada para esta actividad"}), 404

    if not att.is_paused:
        return jsonify({"message": "La asistencia no está pausada"}), 400

    try:
        from app.services.attendance_service import resume_attendance as svc_resume

        attendance = svc_resume(att.id)
        db.session.add(attendance)
        db.session.commit()

        return jsonify({"message": "Asistencia reanudada exitosamente"}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error resuming attendance %s", attendance_id)
        return jsonify(
            {"message": "Error al reanudar asistencia", "error": str(e)}
        ), 400


@public_registrations_bp.route("/api/public/registrations/export", methods=["POST"])
def api_export_registrations_xlsx():
    """Exportar preregistros de una actividad a XLSX usando activity_id (slug/numeric) o token.

    Body JSON expected: { activity_id: <slug or numeric id>, token: <optional fallback token> }
    The endpoint will prioritize activity_id (resolving slug first, then numeric), falling back to token.
    The resulting XLSX will have Spanish headers: 'Número de control', 'Nombre completo', 'Correo', 'Carrera'.
    """
    payload = request.get_json(silent=True) or {}
    activity_id = payload.get("activity_id")
    activity_ref = payload.get("activity")  # Fallback alias for activity_id
    payload.get("token")

    # Consolidate activity_id from multiple possible fields
    if not activity_id and activity_ref:
        activity_id = activity_ref

    # Try to resolve activity from activity_id (slug or numeric) first
    activity = None
    if activity_id:
        try:
            if str(activity_id).isdigit():
                activity = db.session.get(Activity, int(activity_id))
            else:
                activity = Activity.query.filter_by(
                    public_slug=str(activity_id)
                ).first()
        except Exception:
            activity = None

    # No token fallback: activity must be resolved via activity_id (slug or numeric)
    if not activity:
        return jsonify({"message": "Actividad no encontrada"}), 400

    # Collect registrations
    regs = list(getattr(activity, "registrations", []) or [])
    rows = []
    for r in regs:
        # Exclude registrations with status Ausente or Cancelado
        try:
            st = getattr(r, "status", None)
            if st and str(st).strip().lower() in ("ausente", "cancelado"):
                continue
        except Exception:
            pass
        try:
            s = getattr(r, "student", None)
            rows.append(
                {
                    "Número de control": getattr(s, "control_number", None)
                    if s
                    else None,
                    "Nombre completo": getattr(s, "full_name", None) if s else None,
                    "Correo": getattr(s, "email", None) if s else None,
                    "Carrera": getattr(s, "career", None) if s else None,
                }
            )
        except Exception:
            continue

    # Build DataFrame with Spanish columns
    try:
        df = pd.DataFrame(
            rows, columns=["Número de control", "Nombre completo", "Correo", "Carrera"]
        )
    except Exception:
        # Fallback: create DataFrame directly from rows
        df = pd.DataFrame(rows)

    # generate filename using activity name (slugify) + timestamp
    def slugify(text, maxlen=50):
        if not text:
            return "actividad"
        t = text.lower()
        t = re.sub(r"[^a-z0-9]+", "-", t)
        t = t.strip("-")
        if len(t) > maxlen:
            t = t[:maxlen].rstrip("-")
        return t or "actividad"

    # Use UTC-aware timestamp for filename
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    slug = slugify(getattr(activity, "name", "")[:50])
    filename = f"{slug}-{ts}.xlsx"

    bio = io.BytesIO()
    try:
        with pd.ExcelWriter(bio, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="preregistros")
        bio.seek(0)
        return send_file(
            bio,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as e:
        tb = traceback.format_exc()
        current_app.logger.exception("Error generando XLSX publico")
        return jsonify(
            {"message": "Error generando XLSX", "error": str(e), "trace": tb}
        ), 500
