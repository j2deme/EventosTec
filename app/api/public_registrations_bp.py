from flask import Blueprint, request, jsonify, render_template, current_app, send_file
from app import db
from app.models.activity import Activity
from app.models.registration import Registration
from app.models.attendance import Attendance
from app.models.student import Student
from datetime import datetime, timedelta, timezone
import requests
from app.utils.token_utils import verify_public_token, verify_public_event_token, generate_public_token
from app.utils.datetime_utils import localize_naive_datetime, safe_iso
from sqlalchemy.exc import IntegrityError
import io
import re
import traceback
import pandas as pd

public_registrations_bp = Blueprint(
    'public_registrations', __name__, url_prefix='')


# use centralized safe_iso from app.utils.datetime_utils


@public_registrations_bp.route('/public/registrations/<token>', methods=['GET'])
def public_registrations_view(token):
    # First try: token is a public activity token (p:...)
    aid, err = verify_public_token(token)

    activity = None
    activity_token_to_use = None

    if err is None and aid is not None:
        # Token directly references an activity
        try:
            activity = db.session.get(Activity, int(aid))
            activity_token_to_use = token
        except Exception:
            activity = None

    if not activity:
        # Maybe the token is an event-level public token (pe:...). In that
        # case we expect a query param 'activity' with the activity id to open.
        eid, eerr = verify_public_event_token(token)
        if eerr is None and eid is not None:
            # get activity id from query string
            initial_activity = request.args.get('activity')
            if initial_activity:
                try:
                    a = db.session.get(Activity, int(initial_activity))
                    if a and a.event_id == int(eid):
                        activity = a
                        # generate a public activity token (p:...) for client/API use
                        activity_token_to_use = generate_public_token(
                            activity.id)
                except Exception:
                    activity = None

    # If still no activity and the path didn't look like a token, try slug-based resolution
    if not activity and ':' not in (token or ''):
        # Try parse leading numeric id (e.g. '123-activity-slug') or slug-only
        m = re.match(r'^(\d+)(?:-.*)?$', token or '')
        if m:
            try:
                aid2 = int(m.group(1))
                a = db.session.get(Activity, aid2)
                if a:
                    activity = a
                    try:
                        activity_token_to_use = generate_public_token(
                            activity.id)
                    except Exception:
                        activity_token_to_use = None
            except Exception:
                activity = None
        else:
            # fallback: slug-only match by slugifying activity.name
            def slugify(text, maxlen=50):
                if not text:
                    return ''
                t = text.lower()
                t = re.sub(r"[^a-z0-9]+", '-', t)
                t = t.strip('-')
                if len(t) > maxlen:
                    t = t[:maxlen].rstrip('-')
                return t or ''

            try:
                target = token or ''
                for a in Activity.query.all():
                    try:
                        if slugify(getattr(a, 'name', '') or '') == target:
                            activity = a
                            try:
                                activity_token_to_use = generate_public_token(
                                    activity.id)
                            except Exception:
                                activity_token_to_use = None
                            break
                    except Exception:
                        continue
            except Exception:
                activity = None

    if not activity:
        return render_template('public/registrations_public.html', token_provided=True, token_invalid=True)

    # Prepare context
    activity_name = activity.name
    activity_type = getattr(activity, 'activity_type', None)
    activity_deadline_iso = None
    activity_start_iso = None
    activity_end_iso = None
    activity_location = getattr(activity, 'location', None)
    activity_modality = getattr(activity, 'modality', None)
    event_name = None
    event_id = getattr(activity, 'event_id', None)
    event_token_for_back = None
    try:
        # confirmation window: localize activity.end_datetime then add configured days (default 30)
        window_days = int(current_app.config.get(
            'PUBLIC_CONFIRM_WINDOW_DAYS', 30))
        if getattr(activity, 'end_datetime', None) is not None:
            app_timezone = current_app.config.get(
                'APP_TIMEZONE', 'America/Mexico_City')
            end_dt = localize_naive_datetime(
                activity.end_datetime, app_timezone)
            if end_dt is not None:
                deadline_dt = end_dt + timedelta(days=window_days)
                activity_deadline_iso = safe_iso(deadline_dt)
    except Exception:
        activity_deadline_iso = None

    try:
        app_timezone = current_app.config.get(
            'APP_TIMEZONE', 'America/Mexico_City')
        if getattr(activity, 'start_datetime', None) is not None:
            sdt = localize_naive_datetime(
                activity.start_datetime, app_timezone)
            if sdt is not None:
                activity_start_iso = safe_iso(sdt)
            else:
                activity_start_iso = safe_iso(activity.start_datetime)
        if getattr(activity, 'end_datetime', None) is not None:
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
        event_name = getattr(activity, 'event').name if getattr(
            activity, 'event', None) else None
    except Exception:
        event_name = None

    # optional activity id from query string (used when redirected from event-level view)
    initial_activity = request.args.get('activity')
    # if request used an event-level token, expose it so the template can link back to the event list
    # The event token may be provided either as the path token (when the page was opened with a pe: token)
    # or as a query parameter 'event_token' (e.g. redirected from event listing).
    try:
        # first, if the path token itself is an event token, prefer that
        eid, eerr = verify_public_event_token(token)
        if eerr is None and eid is not None:
            event_token_for_back = token
        else:
            # otherwise, check query param `event_token`
            q_event_token = request.args.get('event_token')
            if q_event_token:
                q_eid, q_eerr = verify_public_event_token(q_event_token)
                if q_eerr is None and q_eid is not None:
                    event_token_for_back = q_event_token
    except Exception:
        event_token_for_back = None

    # If still no event token but we have an event_id from the activity, generate a public event token
    from app.utils.token_utils import generate_public_event_token
    try:
        if not event_token_for_back and event_id:
            event_token_for_back = generate_public_event_token(int(event_id))
    except Exception:
        # leave as None
        pass

    return render_template(
        'public/registrations_public.html',
        activity_token=activity_token_to_use,
        activity_name=activity_name,
        activity_type=activity_type,
        activity_deadline_iso=activity_deadline_iso,
        activity_start_iso=activity_start_iso,
        activity_end_iso=activity_end_iso,
        activity_location=activity_location,
        activity_modality=activity_modality,
        event_name=event_name,
        event_id=event_id,
        event_token=event_token_for_back,
        initial_activity_id=initial_activity,
    )


@public_registrations_bp.route('/public/event-registrations/<path:ref>', methods=['GET'])
def public_event_registrations_view(ref):
    """Accept a slug-friendly public URL.

    Supported forms:
      - token-like (contains ':') -> delegate to existing token view
      - "<id>-<slug>" -> lookup Activity by id and render the same template
      - "<slug>" -> try to match slugified activity.name and render if unique

    This keeps the visible URL free of token characters and generates
    a short-lived internal public token for client/API use.
    """
    # If the ref looks like a token (contains ':'), reuse the original handler
    if ':' in (ref or ''):
        return public_registrations_view(ref)

    activity = None
    activity_token_to_use = None

    # Try to parse a leading numeric id (e.g. '123-my-event-slug')
    m = re.match(r'^(\d+)(?:-.*)?$', ref or '')
    if m:
        try:
            aid = int(m.group(1))
            activity = db.session.get(Activity, aid)
            if activity:
                activity_token_to_use = generate_public_token(activity.id)
        except Exception:
            activity = None
    else:
        # Fallback: try slug-only match by comparing a simple slugified name.
        def slugify(text, maxlen=50):
            if not text:
                return ''
            t = text.lower()
            t = re.sub(r"[^a-z0-9]+", '-', t)
            t = t.strip('-')
            if len(t) > maxlen:
                t = t[:maxlen].rstrip('-')
            return t or ''

        try:
            target = ref or ''
            # naive scan: usually fast because number of activities is small for public pages
            for a in Activity.query.all():
                try:
                    if slugify(getattr(a, 'name', '') or '') == target:
                        activity = a
                        activity_token_to_use = generate_public_token(
                            activity.id)
                        break
                except Exception:
                    continue
        except Exception:
            activity = None

    if not activity:
        return render_template('public/registrations_public.html', token_provided=True, token_invalid=True)

    # Build the same rendering context used by public_registrations_view
    activity_name = activity.name
    activity_type = getattr(activity, 'activity_type', None)
    activity_deadline_iso = None
    activity_start_iso = None
    activity_end_iso = None
    activity_location = getattr(activity, 'location', None)
    activity_modality = getattr(activity, 'modality', None)
    event_name = None
    event_id = getattr(activity, 'event_id', None)
    event_token_for_back = None

    try:
        window_days = int(current_app.config.get(
            'PUBLIC_CONFIRM_WINDOW_DAYS', 30))
        if getattr(activity, 'end_datetime', None) is not None:
            app_timezone = current_app.config.get(
                'APP_TIMEZONE', 'America/Mexico_City')
            end_dt = localize_naive_datetime(
                activity.end_datetime, app_timezone)
            if end_dt is not None:
                deadline_dt = end_dt + timedelta(days=window_days)
                activity_deadline_iso = safe_iso(deadline_dt)
    except Exception:
        activity_deadline_iso = None

    try:
        app_timezone = current_app.config.get(
            'APP_TIMEZONE', 'America/Mexico_City')
        if getattr(activity, 'start_datetime', None) is not None:
            sdt = localize_naive_datetime(
                activity.start_datetime, app_timezone)
            if sdt is not None:
                activity_start_iso = safe_iso(sdt)
            else:
                activity_start_iso = safe_iso(activity.start_datetime)
        if getattr(activity, 'end_datetime', None) is not None:
            edt = localize_naive_datetime(activity.end_datetime, app_timezone)
            if edt is not None:
                activity_end_iso = safe_iso(edt)
            else:
                activity_end_iso = safe_iso(activity.end_datetime)
    except Exception:
        activity_start_iso = None
        activity_end_iso = None

    try:
        event_name = getattr(activity, 'event').name if getattr(
            activity, 'event', None) else None
    except Exception:
        event_name = None

    # Generate a back-link event token when possible, keep it best-effort
    try:
        if event_id:
            from app.utils.token_utils import generate_public_event_token

            event_token_for_back = generate_public_event_token(int(event_id))
    except Exception:
        event_token_for_back = None

    return render_template(
        'public/registrations_public.html',
        activity_token=activity_token_to_use,
        activity_name=activity_name,
        activity_type=activity_type,
        activity_deadline_iso=activity_deadline_iso,
        activity_start_iso=activity_start_iso,
        activity_end_iso=activity_end_iso,
        activity_location=activity_location,
        activity_modality=activity_modality,
        event_name=event_name,
        event_id=event_id,
        event_token=event_token_for_back,
        initial_activity_id=None,
    )


@public_registrations_bp.route('/api/public/registrations', methods=['GET'])
def api_list_registrations():
    # Extract token safely: prefer JSON body when present, else query param
    token = None
    if request.is_json:
        j = request.get_json(silent=True) or {}
        token = j.get('token')
    if not token:
        token = request.args.get('token')
    page = int(request.args.get('page') or 1)
    per_page = int(request.args.get('per_page') or 20)

    if not token:
        return jsonify({'message': 'Token inválido'}), 400

    aid, err = verify_public_token(str(token))
    if err or aid is None:
        return jsonify({'message': 'Token inválido'}), 400

    activity = db.session.get(Activity, int(aid))
    if not activity:
        return jsonify({'message': 'Actividad no encontrada'}), 404

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
                val = getattr(status_obj, 'value', None)
                name = getattr(status_obj, 'name', None)
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
                if 'ausente' in s or 'cancel' in s:
                    return True
            return False
        except Exception:
            return False

    for r in regs_all:
        # skip registrations explicitly marked as Ausente or Cancelado
        if _is_excluded_status(getattr(r, 'status', None)):
            continue
        student = r.student
        registration_student_ids.add(r.student_id)
        attendance = atts_by_student.get(r.student_id)
        items.append({
            'id': r.id,
            'registration_id': r.id,
            'attendance_id': attendance.id if attendance else None,
            'student_id': student.id if student else None,
            'control_number': student.control_number if student else None,
            'student_name': student.full_name if student else r.name or None,
            'email': student.email if student else None,
            'status': r.status,
            'attended': bool(r.attended),
            'registration_date': safe_iso(getattr(r, 'registration_date', None)),
            'check_in_time': safe_iso(getattr(attendance, 'check_in_time', None)) if attendance else None,
            'notes': getattr(r, 'notes', None),
            'source': 'registration'
        })

    # Add attendance-only rows (those students without a registration)
    for a in atts_all:
        if a.student_id in registration_student_ids:
            continue
        # also skip attendance rows where status is ausente/cancelado
        try:
            if _is_excluded_status(getattr(a, 'status', None)):
                continue
        except Exception:
            pass
        student = a.student
        items.append({
            'id': None,
            'registration_id': None,
            'attendance_id': a.id,
            'student_id': student.id if student else None,
            'control_number': student.control_number if student else None,
            'student_name': student.full_name if student else None,
            'email': student.email if student else None,
            'status': getattr(a, 'status', 'Asistió'),
            'attended': True,
            'registration_date': None,
            'check_in_time': safe_iso(getattr(a, 'check_in_time', None)),
            'notes': None,
            'source': 'attendance'
        })

    # Sort by control_number if present, fallback to student_name
    def sort_key(it):
        cn = (it.get('control_number') or '')
        # pad numeric-like values for better lexicographic order
        try:
            return (cn.zfill(20), it.get('student_name') or '')
        except Exception:
            return (cn, it.get('student_name') or '')

    items.sort(key=sort_key)

    # Apply server-side search filter (if provided)
    q = (request.args.get('q') or '').strip()
    if q:
        q_lower = q.lower()

        def matches_query(it):
            # check control_number (as substring) and student_name (case-insensitive)
            cn = it.get('control_number')
            name = it.get('student_name')
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

    return jsonify({'registrations': page_items, 'total': total, 'page': page, 'per_page': per_page}), 200


@public_registrations_bp.route('/api/public/registrations/lookup-student', methods=['GET'])
def api_public_lookup_student():
    """Lookup a student by control_number for a given activity token.

    Query params: token=<public token>, control_number=<string>
    Behavior:
      - Verify public token -> activity
      - Try to find Student locally by control_number
      - If found: return { found: True, student: {...}, created: False }
      - Else: query external validation API; if found, create local Student and return { found: True, student: {...}, created: True }
      - Else: return { found: False }
    """
    token = request.args.get('token')
    control_number = (request.args.get('control_number') or '').strip()
    if not token or not control_number:
        return jsonify({'found': False}), 400

    aid, err = verify_public_token(str(token))
    if err or aid is None:
        return jsonify({'found': False}), 403

    activity = db.session.get(Activity, int(aid))
    if not activity:
        return jsonify({'found': False}), 404

    # Try local DB first
    student = Student.query.filter_by(control_number=control_number).first()
    if student:
        return jsonify({'found': True, 'student': student.to_dict() if hasattr(student, 'to_dict') else {'id': student.id, 'full_name': student.full_name, 'control_number': student.control_number}, 'created': False}), 200

    # Not found locally -> try external API (reuse same endpoint used by walkin)
    external_api = f"http://apps.tecvalles.mx:8091/api/validate/student?username={control_number}"
    try:
        resp = requests.get(external_api, timeout=5)
    except requests.exceptions.RequestException:
        current_app.logger.exception(
            'Error contacting external student API for %s', control_number)
        return jsonify({'found': False}), 200

    if resp.status_code == 404:
        current_app.logger.debug(
            'External API returned 404 for %s', control_number)
        return jsonify({'found': False}), 200

    if resp.status_code != 200:
        current_app.logger.warning(
            'External API returned status %s for %s', resp.status_code, control_number)
        # log response body truncated for debugging (avoid huge logs)
        try:
            txt = resp.text or ''
            current_app.logger.debug('External API body: %s', txt[:1000])
        except Exception:
            pass
        return jsonify({'found': False}), 200

    try:
        data = resp.json() if resp.text else {}
    except Exception:
        current_app.logger.exception(
            'Invalid JSON from external student API for %s', control_number)
        data = {}

    # Normalize response similar to walkin behavior
    d = data if isinstance(data, dict) else {}
    career = d.get('career') or d.get('carrera') or {}
    career_name = None
    if isinstance(career, dict):
        career_name = career.get('name') or career.get('nombre')
    else:
        career_name = career

    ext_control = d.get('username') or d.get(
        'control_number') or control_number
    ext_full_name = d.get('name') or d.get('full_name') or d.get('nombre')
    ext_email = d.get('email') or ''

    if not ext_control or not ext_full_name:
        current_app.logger.warning(
            'External student data incomplete for %s: control=%s name=%s', control_number, ext_control, ext_full_name)
        return jsonify({'found': False}), 200

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
            'Created local student %s (%s) from external API', student.full_name, student.control_number)
        return jsonify({'found': True, 'student': student.to_dict() if hasattr(student, 'to_dict') else {'id': student.id, 'full_name': student.full_name, 'control_number': student.control_number}, 'created': True}), 201
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            'Error creating local student for %s', control_number)
        return jsonify({'found': False}), 200


@public_registrations_bp.route('/api/public/registrations/<int:reg_id>/confirm', methods=['POST'])
def api_confirm_registration(reg_id):
    payload = request.get_json() or {}
    token = payload.get('token')
    confirm = bool(payload.get('confirm', True))
    create_attendance = bool(payload.get('create_attendance', True))
    mark_absent = bool(payload.get('mark_absent', False))

    if not token:
        return jsonify({'message': 'Token inválido'}), 400

    aid, err = verify_public_token(str(token))
    if err or aid is None:
        return jsonify({'message': 'Token inválido'}), 400

    reg = db.session.get(Registration, reg_id)
    if not reg or reg.activity_id != int(aid):
        return jsonify({'message': 'Registro no encontrado para esta actividad'}), 404

    # enforce confirmation window
    activity = db.session.get(Activity, int(aid))
    if not activity:
        return jsonify({'message': 'Actividad no encontrada'}), 404

    window_days = int(current_app.config.get('PUBLIC_CONFIRM_WINDOW_DAYS', 30))
    if getattr(activity, 'end_datetime', None) is not None:
        app_timezone = current_app.config.get(
            'APP_TIMEZONE', 'America/Mexico_City')
        end_dt = localize_naive_datetime(activity.end_datetime, app_timezone)
        if end_dt is None:
            return jsonify({'message': 'La ventana de confirmación ha expirado'}), 400
        cutoff = end_dt + timedelta(days=window_days)
        now = datetime.now(timezone.utc)
        if now > cutoff:
            return jsonify({'message': 'La ventana de confirmación ha expirado'}), 400

    # update registration
    if confirm:
        reg.attended = True
        reg.status = 'Asistió'
        reg.confirmation_date = db.func.now()
    else:
        # Desconfirmación: two possible flows
        if mark_absent:
            # explicit request to mark as Ausente
            reg.attended = False
            reg.status = 'Ausente'
            reg.confirmation_date = db.func.now()
        else:
            # revert to preregistro state
            reg.attended = False
            reg.status = 'Registrado'
            reg.confirmation_date = None
    db.session.add(reg)

    # create attendance if requested, avoid duplicates
    attendance = None
    if confirm and create_attendance:
        # check existing attendance
        existing = Attendance.query.filter_by(
            student_id=reg.student_id, activity_id=reg.activity_id).first()
        if not existing:
            attendance = Attendance()
            attendance.student_id = reg.student_id
            attendance.activity_id = reg.activity_id
            attendance.check_in_time = datetime.now(timezone.utc)
            # 'status' is an Enum('Asistió','Parcial','Ausente') in the model.
            # Use a valid value to avoid DB errors; map internal labels to 'Asistió'.
            attendance.status = 'Asistió'
            db.session.add(attendance)
    else:
        # if un-confirming, remove existing attendance created earlier (if any)
        existing = Attendance.query.filter_by(
            student_id=reg.student_id, activity_id=reg.activity_id).first()
        if existing:
            try:
                db.session.delete(existing)
                attendance = None
            except Exception:
                # failure to delete should not break the flow; will be rolled back later
                pass

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        # Log full exception server-side for debugging without leaking internals to clients
        current_app.logger.exception(
            'Error confirming registration %s', reg_id)
        return jsonify({'message': 'Error al confirmar'}), 500

    # Return updated registration representation to help frontend update row without refetch
    if hasattr(reg, 'to_dict'):
        reg_dict = reg.to_dict()
    else:
        conf = getattr(reg, 'confirmation_date', None)
        reg_dict = {
            'id': reg.id,
            'attended': reg.attended,
            'status': reg.status,
            'confirmation_date': safe_iso(conf)
        }
    return jsonify({
        'message': 'Confirmación registrada',
        'registration_id': reg.id,
        'attendance_id': attendance.id if attendance else None,
        'registration': reg_dict
    }), 200


@public_registrations_bp.route('/api/public/registrations/walkin', methods=['POST'])
def api_walkin():
    payload = request.get_json(silent=True) or {}
    token = payload.get('token')
    control_number = (payload.get('control_number') or '').strip()
    full_name = payload.get('full_name')
    email = payload.get('email')
    # optional external student payload (from frontend's external lookup)
    external_student = payload.get('external_student')

    # For walk-in, only token and control_number are required. The frontend
    # should perform local/external lookup and supply full_name when creating
    # a student is desired. The backend must NOT create Student records
    # automatically when the student is not present locally.
    if not token or not control_number:
        return jsonify({'message': 'token y control_number son requeridos'}), 400

    if not token:
        return jsonify({'message': 'Token inválido'}), 400

    aid, err = verify_public_token(str(token))
    if err or aid is None:
        return jsonify({'message': 'Token inválido'}), 400

    activity = db.session.get(Activity, int(aid))
    if not activity:
        return jsonify({'message': 'Actividad no encontrada'}), 404

    # allow walk-in within confirmation window
    window_days = int(current_app.config.get('PUBLIC_CONFIRM_WINDOW_DAYS', 30))
    if getattr(activity, 'end_datetime', None) is not None:
        app_timezone = current_app.config.get(
            'APP_TIMEZONE', 'America/Mexico_City')
        end_dt = localize_naive_datetime(activity.end_datetime, app_timezone)
        if end_dt is None:
            return jsonify({'message': 'La ventana de confirmación ha expirado'}), 400
        cutoff = end_dt + timedelta(days=window_days)
        now = datetime.now(timezone.utc)
        if now > cutoff:
            return jsonify({'message': 'La ventana de confirmación ha expirado'}), 400

    # find existing student locally
    student = Student.query.filter_by(control_number=control_number).first()
    if not student:
        # Backend will call the external validation API to fetch student data
        # and create the Student locally. This prevents trusting client payloads.
        external_api = f"http://apps.tecvalles.mx:8091/api/validate/student?username={control_number}"
        try:
            resp = requests.get(external_api, timeout=8)
        except requests.exceptions.RequestException:
            return jsonify({'message': 'Error conectando al servicio externo'}), 503

        if resp.status_code == 404:
            return jsonify({'message': 'Estudiante no encontrado en sistema externo'}), 404
        if resp.status_code != 200:
            return jsonify({'message': 'Error desde servicio externo'}), 503

        try:
            data = resp.json()
        except Exception:
            return jsonify({'message': 'Respuesta externa inválida'}), 502

        # Normalize payload similar to students_bp.validate_student_proxy
        if isinstance(data, dict) and 'data' in data and isinstance(data.get('data'), dict):
            data = data.get('data')

        d = data if isinstance(data, dict) else {}

        career = d.get('career') or d.get('carrera') or {}
        career_name = None
        if isinstance(career, dict):
            career_name = career.get('name') or career.get('nombre') or None
        else:
            career_name = career

        ext_control = d.get('username') or d.get(
            'control_number') or control_number
        ext_full_name = d.get('name') or d.get('full_name') or d.get('nombre')
        ext_email = d.get('email') or ''

        if not ext_control or not ext_full_name:
            return jsonify({'message': 'Datos externos incompletos para crear estudiante'}), 502

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
            student = Student.query.filter_by(
                control_number=control_number).first()
            if not student:
                current_app.logger.exception(
                    'IntegrityError creating student during walk-in')
                return jsonify({'message': 'Conflicto al crear estudiante'}), 409

    # perform all DB changes in a single transaction for atomicity
    try:

        # If a Registration exists, mark it attended; DO NOT create a new Registration
        # when none existed previously. The walk-in flow should create only the
        # Attendance record for students without a preregistro.
        reg = Registration.query.filter_by(
            student_id=student.id, activity_id=activity.id).first()
        if reg:
            # If registration exists but not marked attended, mark it
            if not reg.attended:
                reg.attended = True
                reg.status = 'Asistió'
                reg.confirmation_date = db.func.now()
                db.session.add(reg)

        # avoid duplicate attendance
        existing = Attendance.query.filter_by(
            student_id=student.id, activity_id=activity.id).first()
        if existing:
            # Return conflict with existing attendance info
            return jsonify({'message': 'Ya existe una asistencia registrada para este estudiante', 'attendance': existing.to_dict()}), 409

        attendance = Attendance()
        attendance.student_id = student.id
        attendance.activity_id = activity.id
        attendance.check_in_time = datetime.now(timezone.utc)
        attendance.status = 'Asistió'
        db.session.add(attendance)
        db.session.flush()

        db.session.commit()
    except IntegrityError as ie:
        db.session.rollback()
        current_app.logger.exception(
            'Integrity error creating walk-in for activity %s', activity.id)
        return jsonify({'message': 'Conflicto al crear walk-in'}), 409
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            'Error creating walk-in for activity %s', activity.id)
        return jsonify({'message': 'Error al crear walk-in'}), 500

    # Build response with created/updated resources
    resp = {
        'message': 'Walk-in registrado',
        'student': student.to_dict() if hasattr(student, 'to_dict') else {'id': student.id},
        'attendance': attendance.to_dict() if hasattr(attendance, 'to_dict') else {'id': attendance.id, 'student_id': student.id},
        # include registration only if it existed
        'registration': (reg.to_dict() if reg and hasattr(reg, 'to_dict') else (reg and {'id': reg.id, 'student_id': student.id} or None)),
    }
    return jsonify(resp), 201


@public_registrations_bp.route('/api/public/attendances/<int:attendance_id>/toggle', methods=['POST'])
def api_toggle_attendance(attendance_id):
    payload = request.get_json(silent=True) or {}
    token = payload.get('token')
    # confirm: True means ensure attendance exists; False means remove it
    confirm = bool(payload.get('confirm', True))

    if not token:
        return jsonify({'message': 'Token inválido'}), 400

    aid, err = verify_public_token(str(token))
    if err or aid is None:
        return jsonify({'message': 'Token inválido'}), 400

    activity = db.session.get(Activity, int(aid))
    if not activity:
        return jsonify({'message': 'Actividad no encontrada'}), 404

    att = db.session.get(Attendance, int(attendance_id))
    if not att or att.activity_id != activity.id:
        return jsonify({'message': 'Asistencia no encontrada para esta actividad'}), 404

    # Only allow deletion (un-mark) via public flow for attendance-only rows.
    # If confirm is False, delete the attendance record.
    if not confirm:
        try:
            # If there is a registration linked to this student and activity, do not touch it here.
            db.session.delete(att)
            db.session.commit()
            return jsonify({'message': 'Asistencia removida', 'attendance_id': attendance_id}), 200
        except Exception:
            db.session.rollback()
            current_app.logger.exception(
                'Error deleting attendance %s', attendance_id)
            return jsonify({'message': 'Error al eliminar asistencia'}), 500

    # For confirm=True, if attendance already exists we simply return ok
    return jsonify({'message': 'Asistencia existente', 'attendance_id': attendance_id}), 200


@public_registrations_bp.route('/public/pause-attendance/<token>', methods=['GET'])
def public_pause_attendance_view(token):
    """Public view for pausing/resuming attendances for Magistral activities."""
    aid, err = verify_public_token(str(token))
    if err or aid is None:
        return render_template('public/pause_attendance.html', token_provided=True, token_invalid=True)

    activity = db.session.get(Activity, int(aid))
    if not activity:
        return render_template('public/pause_attendance.html', token_provided=True, token_invalid=True)

    # Only allow for Magistral activities
    if getattr(activity, 'activity_type', None) != 'Magistral':
        return render_template('public/pause_attendance.html', token_provided=True, token_invalid=True, error_message='Solo disponible para conferencias magistrales')

    # Check time window: for public pause/resume we allow from NOW until 5 minutes after end
    now = datetime.now(timezone.utc)

    # Get app timezone configuration
    app_timezone = current_app.config.get(
        'APP_TIMEZONE', 'America/Mexico_City')

    # Localize naive datetimes from database to app timezone, then convert to UTC
    end_dt = activity.end_datetime
    if end_dt is None:
        return render_template('public/pause_attendance.html', token_provided=True, token_invalid=True)

    # Use localize_naive_datetime to properly handle naive datetimes
    end_dt = localize_naive_datetime(end_dt, app_timezone)
    # localize_naive_datetime may return None on failure; guard against it
    if end_dt is None:
        return render_template('public/pause_attendance.html', token_provided=True, token_invalid=True)

    # Public window: derive from configuration (overridable via .env/config)
    from_seconds = int(current_app.config.get(
        'PUBLIC_PAUSE_AVAILABLE_FROM_SECONDS', 0))
    until_minutes = int(current_app.config.get(
        'PUBLIC_PAUSE_AVAILABLE_UNTIL_AFTER_END_MINUTES', 5))

    # available_from = start_dt + from_seconds (if start_dt exists and from_seconds>0), else now
    start_dt = activity.start_datetime
    if from_seconds > 0 and start_dt is not None:
        start_dt = localize_naive_datetime(start_dt, app_timezone)
        # If localization failed, fall back to now as the available_from
        if start_dt is None:
            available_from = now
        else:
            available_from = start_dt + timedelta(seconds=from_seconds)
    else:
        available_from = now

    # end_dt is already localized and guarded above
    available_until = end_dt + timedelta(minutes=until_minutes)

    if now < available_from:
        return render_template('public/pause_attendance.html', token_provided=True, token_invalid=True, error_message=f'Esta vista estará disponible a partir de {safe_iso(available_from)}')

    if now > available_until:
        return render_template('public/pause_attendance.html', token_provided=True, token_invalid=True, error_message='La ventana pública de control ha expirado.')

    return render_template(
        'public/pause_attendance.html',
        activity_token=token,
        activity_name=activity.name,
        token_provided=True,
        token_invalid=False,
    )


@public_registrations_bp.route('/public/pause-attendance', methods=['GET'])
def public_pause_attendance_query():
    # Backwards-compatible alternative: accept token as query param to avoid path encoding issues
    token = request.args.get('token') or ''
    return public_pause_attendance_view(token)


@public_registrations_bp.route('/public/staff-walkin/<token>', methods=['GET'])
def public_staff_walkin_view(token):
    """Mobile-first public view for staff to register walk-ins quickly via activity public token."""
    aid, err = verify_public_token(str(token))
    if err or aid is None:
        return render_template('public/staff_walkin.html', activity_token='', activity_name='', token_provided=True, token_invalid=True)

    activity = db.session.get(Activity, int(aid))
    if not activity:
        return render_template('public/staff_walkin.html', activity_token='', activity_name='', token_provided=True, token_invalid=True)

    # Only allow for Magistral activities (same restriction as other public controls)
    if getattr(activity, 'activity_type', None) != 'Magistral':
        return render_template('public/staff_walkin.html', activity_token='', activity_name=activity.name if activity else '', token_provided=True, token_invalid=True)

    # include start datetime ISO so frontend can compute staff registration window
    activity_start_iso = None
    try:
        if getattr(activity, 'start_datetime', None) is not None:
            activity_start_iso = safe_iso(activity.start_datetime)
    except Exception:
        activity_start_iso = None

    return render_template('public/staff_walkin.html', activity_token=token, activity_name=activity.name, activity_start_iso=activity_start_iso, token_provided=True, token_invalid=False)


@public_registrations_bp.route('/public/staff-walkin', methods=['GET'])
def public_staff_walkin_query():
    # Backwards-compatible alternative: accept token as query param to avoid path encoding issues
    token = request.args.get('token') or ''
    return public_staff_walkin_view(token)


@public_registrations_bp.route('/public/event-registrations/<path:event_slug>', methods=['GET'])
def public_event_registrations_by_slug(event_slug):
    """Resolve an event by slug (slugified event.name) and render the public
    registrations page for chiefs. Optionally accept query param `activity` which
    can be a short activity token (sqids-based or serialized) to open the activity
    directly; if found, we generate a public activity token for client use and
    inject it in the template as `data-initial-activity-token`.
    """
    # simple slugify helper matching the one used elsewhere
    def slugify(text):
        if not text:
            return ''
        t = str(text).lower()
        t = re.sub(r'[^a-z0-9]+', '-', t)
        t = t.strip('-')
        return t

    # Find event by slug (note: this scans names; if many events exist, consider adding a slug column)
    target = (event_slug or '').strip()
    found_event = None
    try:
        from app.models.event import Event

        # naive scan: slugify each event name and compare
        events = Event.query.all()
    except Exception:
        events = []

    for e in events:
        try:
            if slugify(getattr(e, 'name', '') or '') == target:
                found_event = e
                break
        except Exception:
            continue

    if not found_event:
        # render the same template but indicate invalid token/view
        return render_template('public/event_registrations_public.html', event_token='', event_name=target, event_id=None, event_token_provided=False, event_token_invalid=True)

    # Optionally resolve activity short token from query param
    activity_param = request.args.get('activity')
    initial_activity_token = None
    if activity_param:
        # Try to verify activity token using existing helper
        from app.utils.token_utils import verify_activity_token, generate_public_token

        aid, err = verify_activity_token(str(activity_param))
        if err is None and aid is not None:
            # generate a public activity token for the client (p:...)
            try:
                initial_activity_token = generate_public_token(int(aid))
            except Exception:
                initial_activity_token = None

    # Generate event-level public token for backlink/authorization for chiefs
    from app.utils.token_utils import generate_public_event_token
    event_token_for_back = None
    try:
        event_token_for_back = generate_public_event_token(int(found_event.id))
    except Exception:
        event_token_for_back = None

    return render_template(
        'public/event_registrations_public.html',
        event_token=event_token_for_back,
        event_name=found_event.name,
        event_id=found_event.id,
        event_slug=target,
        initial_activity_token=initial_activity_token,
    )


@public_registrations_bp.route('/api/public/attendances/search', methods=['GET'])
def api_public_search_attendances():
    """Search attendances for a specific activity using public token."""
    token = request.args.get('token')
    search = request.args.get('search', '').strip()

    if not token:
        return jsonify({'message': 'Token requerido'}), 400

    aid, err = verify_public_token(str(token))
    if err or aid is None:
        return jsonify({'message': 'Token inválido'}), 400

    activity = db.session.get(Activity, int(aid))
    if not activity:
        return jsonify({'message': 'Actividad no encontrada'}), 404

    # Only allow for Magistral activities
    if getattr(activity, 'activity_type', None) != 'Magistral':
        return jsonify({'message': 'Solo disponible para conferencias magistrales'}), 400

    # Check time window: public search available from NOW until 5 minutes after end
    now = datetime.now(timezone.utc)

    # Get app timezone configuration
    app_timezone = current_app.config.get(
        'APP_TIMEZONE', 'America/Mexico_City')

    end_dt = activity.end_datetime
    if end_dt is None:
        return jsonify({'attendances': [], 'total': 0, 'page': 1, 'per_page': 0}), 200

    # Use localize_naive_datetime to properly handle naive datetimes
    end_dt = localize_naive_datetime(end_dt, app_timezone)
    if end_dt is None:
        return jsonify({'message': 'Token inválido o actividad no encontrada.'}), 400

    from_seconds = int(current_app.config.get(
        'PUBLIC_PAUSE_AVAILABLE_FROM_SECONDS', 0))
    until_minutes = int(current_app.config.get(
        'PUBLIC_PAUSE_AVAILABLE_UNTIL_AFTER_END_MINUTES', 5))

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
        return jsonify({'attendances': [], 'total': 0, 'page': 1, 'per_page': 0}), 200

    if now > available_until:
        return jsonify({'attendances': [], 'total': 0, 'page': 1, 'per_page': 0}), 200

    if not search:
        return jsonify({'attendances': []}), 200

    # Search attendances for this activity
    query = Attendance.query.filter_by(activity_id=activity.id)
    query = query.join(Student)
    query = query.filter(
        db.or_(
            Student.full_name.ilike(f'%{search}%'),
            Student.control_number.ilike(f'%{search}%')
        )
    )
    # Only return attendances with check_in_time (active or paused)
    query = query.filter(Attendance.check_in_time.isnot(None))
    attendances = query.all()

    # Serialize with student info
    result = []
    for att in attendances:
        try:
            student = att.student if hasattr(att, 'student') else None
            result.append({
                'id': att.id,
                'student_id': att.student_id,
                'student_name': student.full_name if student else '',
                'student_identifier': getattr(student, 'control_number', '') if student else '',
                'is_paused': att.is_paused,
                'check_in_time': safe_iso(getattr(att, 'check_in_time', None)),
                'check_out_time': safe_iso(getattr(att, 'check_out_time', None)),
            })
        except Exception:
            continue

    return jsonify({'attendances': result}), 200


@public_registrations_bp.route('/api/public/attendances/<int:attendance_id>/pause', methods=['POST'])
def api_public_pause_attendance(attendance_id):
    """Pause an attendance via public token."""
    payload = request.get_json(silent=True) or {}
    token = payload.get('token')

    if not token:
        return jsonify({'message': 'Token requerido'}), 400

    aid, err = verify_public_token(str(token))
    if err or aid is None:
        return jsonify({'message': 'Token inválido'}), 400

    activity = db.session.get(Activity, int(aid))
    if not activity:
        return jsonify({'message': 'Actividad no encontrada'}), 404

    # Only allow for Magistral activities
    if getattr(activity, 'activity_type', None) != 'Magistral':
        return jsonify({'message': 'Solo disponible para conferencias magistrales'}), 400

    # Check time window: public pause available from NOW until 5 minutes after end
    now = datetime.now(timezone.utc)

    # Get app timezone configuration
    app_timezone = current_app.config.get(
        'APP_TIMEZONE', 'America/Mexico_City')

    end_dt = activity.end_datetime
    if end_dt is None:
        return jsonify({'message': 'Token inválido o actividad no encontrada.'}), 400

    # Use localize_naive_datetime to properly handle naive datetimes
    end_dt = localize_naive_datetime(end_dt, app_timezone)
    if end_dt is None:
        return jsonify({'message': 'Token inválido o actividad no encontrada.'}), 400

    from_seconds = int(current_app.config.get(
        'PUBLIC_PAUSE_AVAILABLE_FROM_SECONDS', 0))
    until_minutes = int(current_app.config.get(
        'PUBLIC_PAUSE_AVAILABLE_UNTIL_AFTER_END_MINUTES', 5))

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
        return jsonify({'message': f'Esta funcionalidad estará disponible a partir de {safe_iso(available_from)}'}), 403

    if now > available_until:
        return jsonify({'message': 'La ventana pública de control ha expirado.'}), 403

    att = db.session.get(Attendance, int(attendance_id))
    if not att or att.activity_id != activity.id:
        return jsonify({'message': 'Asistencia no encontrada para esta actividad'}), 404

    if not att.check_in_time:
        return jsonify({'message': 'No se ha registrado check-in'}), 400

    if att.check_out_time:
        return jsonify({'message': 'Ya se ha registrado check-out'}), 400

    if att.is_paused:
        return jsonify({'message': 'La asistencia ya está pausada'}), 400

    try:
        from app.services.attendance_service import pause_attendance as svc_pause
        attendance = svc_pause(att.id)
        db.session.add(attendance)
        db.session.commit()

        return jsonify({'message': 'Asistencia pausada exitosamente'}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(
            'Error pausing attendance %s', attendance_id)
        return jsonify({'message': 'Error al pausar asistencia', 'error': str(e)}), 400


@public_registrations_bp.route('/api/public/attendances/<int:attendance_id>/resume', methods=['POST'])
def api_public_resume_attendance(attendance_id):
    """Resume a paused attendance via public token."""
    payload = request.get_json(silent=True) or {}
    token = payload.get('token')

    if not token:
        return jsonify({'message': 'Token requerido'}), 400

    aid, err = verify_public_token(str(token))
    if err or aid is None:
        return jsonify({'message': 'Token inválido'}), 400

    activity = db.session.get(Activity, int(aid))
    if not activity:
        return jsonify({'message': 'Actividad no encontrada'}), 404

    # Only allow for Magistral activities
    if getattr(activity, 'activity_type', None) != 'Magistral':
        return jsonify({'message': 'Solo disponible para conferencias magistrales'}), 400

    # Check time window: public resume available from NOW until 5 minutes after end
    now = datetime.now(timezone.utc)

    # Get app timezone configuration
    app_timezone = current_app.config.get(
        'APP_TIMEZONE', 'America/Mexico_City')

    end_dt = activity.end_datetime
    if end_dt is None:
        return jsonify({'message': 'Token inválido o actividad no encontrada.'}), 400

    # Use localize_naive_datetime to properly handle naive datetimes
    end_dt = localize_naive_datetime(end_dt, app_timezone)
    if end_dt is None:
        return jsonify({'message': 'Token inválido o actividad no encontrada.'}), 400

    from_seconds = int(current_app.config.get(
        'PUBLIC_PAUSE_AVAILABLE_FROM_SECONDS', 0))
    until_minutes = int(current_app.config.get(
        'PUBLIC_PAUSE_AVAILABLE_UNTIL_AFTER_END_MINUTES', 5))

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
        return jsonify({'message': f'Esta funcionalidad estará disponible a partir de {safe_iso(available_from)}'}), 403

    if now > available_until:
        return jsonify({'message': 'La ventana pública de control ha expirado.'}), 403

    att = db.session.get(Attendance, int(attendance_id))
    if not att or att.activity_id != activity.id:
        return jsonify({'message': 'Asistencia no encontrada para esta actividad'}), 404

    if not att.is_paused:
        return jsonify({'message': 'La asistencia no está pausada'}), 400

    try:
        from app.services.attendance_service import resume_attendance as svc_resume
        attendance = svc_resume(att.id)
        db.session.add(attendance)
        db.session.commit()

        return jsonify({'message': 'Asistencia reanudada exitosamente'}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(
            'Error resuming attendance %s', attendance_id)
        return jsonify({'message': 'Error al reanudar asistencia', 'error': str(e)}), 400


@public_registrations_bp.route('/api/public/registrations/export', methods=['POST'])
def api_export_registrations_xlsx():
    """Exportar preregistros de una actividad a XLSX usando un token público.

    Body JSON expected: { token: <public token p:... or pe:...>, activity: <activity_id if token is pe:...> }
    The endpoint does not expose internal activity ids in URLs — the client provides the token only.
    The resulting XLSX will have Spanish headers: 'Número de control', 'Nombre completo', 'Correo', 'Carrera'.
    """
    payload = request.get_json(silent=True) or {}
    token = payload.get('token')
    activity_ref = payload.get('activity')

    activity_slug = payload.get('activity_slug') or payload.get('slug')

    # If no token provided, allow resolving activity by slug when supplied
    if not token and not activity_slug:
        return jsonify({'message': 'Token inválido'}), 400

    # Try activity-level public token first (if token provided)
    activity = None
    if token:
        aid, aerr = verify_public_token(str(token))
        if aerr is None and aid is not None:
            try:
                activity = db.session.get(Activity, int(aid))
            except Exception:
                activity = None

    # If not activity token, maybe it's an event-level token and client provided activity id
    if not activity and token:
        eid, eerr = verify_public_event_token(str(token))
        if eerr is None and eid is not None:
            # activity_ref must be provided and belong to the event
            if not activity_ref:
                return jsonify({'message': 'Falta el ID de la actividad para token de evento'}), 400
            try:
                a = db.session.get(Activity, int(activity_ref))
                if not a or a.event_id != int(eid):
                    return jsonify({'message': 'Actividad no encontrada para este token de evento'}), 404
                activity = a
            except Exception:
                return jsonify({'message': 'Actividad inválida'}), 400

    # If still no activity but client provided an activity_slug, resolve by slug
    if not activity and activity_slug:
        def slugify(text, maxlen=80):
            if not text:
                return ''
            t = text.lower()
            t = re.sub(r"[^a-z0-9]+", '-', t)
            t = t.strip('-')
            if len(t) > maxlen:
                t = t[:maxlen].rstrip('-')
            return t or ''

        try:
            target = str(activity_slug or '')
            for a in Activity.query.all():
                try:
                    if slugify(getattr(a, 'name', '') or '') == target:
                        activity = a
                        break
                except Exception:
                    continue
        except Exception:
            activity = None

    if not activity:
        return jsonify({'message': 'Token inválido o actividad no encontrada'}), 400

    # Collect registrations
    regs = list(getattr(activity, 'registrations', []) or [])
    rows = []
    for r in regs:
        # Exclude registrations with status Ausente or Cancelado
        try:
            st = getattr(r, 'status', None)
            if st and str(st).strip().lower() in ('ausente', 'cancelado'):
                continue
        except Exception:
            pass
        try:
            s = getattr(r, 'student', None)
            rows.append({
                'Número de control': getattr(s, 'control_number', None) if s else None,
                'Nombre completo': getattr(s, 'full_name', None) if s else None,
                'Correo': getattr(s, 'email', None) if s else None,
                'Carrera': getattr(s, 'career', None) if s else None,
            })
        except Exception:
            continue

    # Build DataFrame with Spanish columns
    try:
        df = pd.DataFrame(
            rows, columns=['Número de control', 'Nombre completo', 'Correo', 'Carrera'])
    except Exception:
        # Fallback: create DataFrame directly from rows
        df = pd.DataFrame(rows)

    # generate filename using activity name (slugify) + timestamp
    def slugify(text, maxlen=50):
        if not text:
            return 'actividad'
        t = text.lower()
        t = re.sub(r"[^a-z0-9]+", '-', t)
        t = t.strip('-')
        if len(t) > maxlen:
            t = t[:maxlen].rstrip('-')
        return t or 'actividad'

    # Use UTC-aware timestamp for filename
    ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    slug = slugify(getattr(activity, 'name', '')[:50])
    filename = f"{slug}-{ts}.xlsx"

    bio = io.BytesIO()
    try:
        with pd.ExcelWriter(bio, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='preregistros')
        bio.seek(0)
        return send_file(
            bio,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename,
        )
    except Exception as e:
        tb = traceback.format_exc()
        current_app.logger.exception('Error generando XLSX publico')
        return jsonify({'message': 'Error generando XLSX', 'error': str(e), 'trace': tb}), 500
