from flask import Blueprint, request, jsonify, render_template, current_app
from app import db
from app.models.activity import Activity
from app.models.registration import Registration
from app.models.attendance import Attendance
from app.models.student import Student
from datetime import datetime, timedelta, timezone
import requests
from app.utils.token_utils import verify_public_token, verify_public_event_token, generate_public_token
from sqlalchemy.exc import IntegrityError

public_registrations_bp = Blueprint(
    'public_registrations', __name__, url_prefix='')


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
        # confirmation window: activity.end_datetime + configured days (default 30)
        window_days = int(current_app.config.get(
            'PUBLIC_CONFIRM_WINDOW_DAYS', 30))
        if getattr(activity, 'end_datetime', None) is not None:
            deadline_dt = activity.end_datetime + timedelta(days=window_days)
            activity_deadline_iso = deadline_dt.isoformat()
    except Exception:
        activity_deadline_iso = None

    try:
        if getattr(activity, 'start_datetime', None) is not None:
            activity_start_iso = activity.start_datetime.isoformat()
        if getattr(activity, 'end_datetime', None) is not None:
            activity_end_iso = activity.end_datetime.isoformat()
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

    for r in regs_all:
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
            'registration_date': r.registration_date.isoformat() if getattr(r, 'registration_date', None) else None,
            'check_in_time': attendance.check_in_time.isoformat() if attendance and getattr(attendance, 'check_in_time', None) else None,
            'notes': getattr(r, 'notes', None),
            'source': 'registration'
        })

    # Add attendance-only rows (those students without a registration)
    for a in atts_all:
        if a.student_id in registration_student_ids:
            continue
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
            'check_in_time': a.check_in_time.isoformat() if getattr(a, 'check_in_time', None) else None,
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


@public_registrations_bp.route('/api/public/registrations/<int:reg_id>/confirm', methods=['POST'])
def api_confirm_registration(reg_id):
    payload = request.get_json() or {}
    token = payload.get('token')
    confirm = bool(payload.get('confirm', True))
    create_attendance = bool(payload.get('create_attendance', True))

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
        cutoff = activity.end_datetime + timedelta(days=window_days)
        if datetime.utcnow() > cutoff.replace(tzinfo=None):
            return jsonify({'message': 'La ventana de confirmación ha expirado'}), 400

    # update registration
    if confirm:
        reg.attended = True
        reg.status = 'Asistió'
        reg.confirmation_date = db.func.now()
    else:
        # Desconfirmación: remove attendance and set preregistro back to 'Registrado'
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
            'confirmation_date': conf.isoformat() if conf else None
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
        cutoff = activity.end_datetime + timedelta(days=window_days)
        if datetime.utcnow() > cutoff.replace(tzinfo=None):
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
