from flask import Blueprint, request, jsonify, render_template, current_app
import requests
from app import db
from app.models.student import Student
from app.models.activity import Activity
from app.models.registration import Registration
from app.models.attendance import Attendance
from app.schemas import attendance_schema
from datetime import datetime, timedelta, timezone
from app.utils.datetime_utils import localize_naive_datetime
from app.utils.token_utils import verify_activity_token, generate_activity_token

self_register_bp = Blueprint('self_register', __name__, url_prefix='')


@self_register_bp.route('/self-register', methods=['GET'])
@self_register_bp.route('/self-register/<token_param>', methods=['GET'])
def self_register_form(token_param=None):
    # Prefer a signed token in the path to avoid exposing raw IDs in the URL
    token = token_param or request.args.get('t') or request.args.get('token')
    activity = None
    activity_name = None
    activity_exists = False
    token_provided = bool(token_param is not None or request.args.get(
        't') or request.args.get('token'))
    token_invalid = False

    if token:
        aid, err = verify_activity_token(token)
        if err:
            token_invalid = True
            token = None
        else:
            try:
                if aid is not None:
                    activity = db.session.get(Activity, int(aid))
                    if activity:
                        activity_name = activity.name
                        activity_exists = True
                else:
                    token_invalid = True
                    token = None
            except Exception:
                token_invalid = True
                token = None

    # Legacy: accept raw activity id but do not expose it; generate token for the template
    if not token:
        aid = request.args.get('activity')
        if aid:
            try:
                activity = db.session.get(Activity, int(aid))
                if activity:
                    activity_name = activity.name
                    activity_exists = True
                    token = generate_activity_token(activity.id)
            except Exception:
                pass

    activity_start_iso = None
    activity_duration_hours = None
    activity_deadline_iso = None
    activity_type = None
    if activity:
        # start datetime (localized to UTC for consistency)
        try:
            if getattr(activity, 'start_datetime', None) is not None:
                app_tz = current_app.config.get(
                    'APP_TIMEZONE', 'America/Mexico_City')
                s_local = localize_naive_datetime(
                    activity.start_datetime, app_tz)
                activity_start_iso = s_local.isoformat() if s_local is not None else None
        except Exception:
            activity_start_iso = None

        # compute a safe float for duration_hours
        try:
            hours_val = getattr(activity, 'duration_hours', None)
            activity_duration_hours = float(
                hours_val) if hours_val is not None else None
        except Exception:
            activity_duration_hours = None

        # compute registration deadline = start + 20 minutes (use localized UTC)
        try:
            start_dt = getattr(activity, 'start_datetime', None)
            if start_dt is not None:
                app_tz = current_app.config.get(
                    'APP_TIMEZONE', 'America/Mexico_City')
                s_local = localize_naive_datetime(start_dt, app_tz)
                if s_local is not None:
                    deadline_dt = s_local + timedelta(minutes=20)
                    activity_deadline_iso = deadline_dt.isoformat()
                else:
                    activity_deadline_iso = None
        except Exception:
            activity_deadline_iso = None
        try:
            activity_type = getattr(activity, 'activity_type', None) or None
        except Exception:
            activity_type = None

    return render_template(
        'public/self_register.html',
        activity_token=token,
        activity_name=activity_name,
        activity_exists=activity_exists,
        token_provided=token_provided,
        token_invalid=token_invalid,
        activity_start_iso=activity_start_iso,
        activity_duration_hours=activity_duration_hours,
        activity_deadline_iso=activity_deadline_iso,
        activity_type=activity_type,
    )


@self_register_bp.route('/api/registrations/self', methods=['POST'])
def self_register_api():
    try:
        payload = request.get_json() or {}
        control_number = (payload.get('control_number') or '').strip()
        password = payload.get('password')
        activity_token = payload.get('activity_token')
        activity_id = payload.get('activity_id')

        # Prefer token; if present decode to activity_id using stateless helper
        if activity_token:
            aid, err = verify_activity_token(activity_token)
            if err:
                return jsonify({'message': 'Token de actividad inválido'}), 400
            activity_id = int(aid) if aid is not None else None

        if not control_number or not password or not activity_id:
            return jsonify({'message': 'control_number, password y activity_id son requeridos'}), 400

        # Validate activity and time window: allow until start + 20 minutes
        activity = db.session.get(Activity, activity_id)
        if not activity:
            return jsonify({'message': 'Actividad no encontrada'}), 404

        # Use timezone-aware datetimes for comparison to avoid naive/aware errors
        now = datetime.now(timezone.utc)
        cutoff = None
        if getattr(activity, 'start_datetime', None):
            app_tz = current_app.config.get(
                'APP_TIMEZONE', 'America/Mexico_City')
            s_local = localize_naive_datetime(activity.start_datetime, app_tz)
            if s_local is not None:
                cutoff = s_local + timedelta(minutes=20)

        if cutoff and now > cutoff:
            return jsonify({'message': 'La ventana de registro in situ ha terminado'}), 400

        # Authenticate student against external validation endpoint by calling internal auth route
        # We call the existing student-login endpoint internally to reuse its logic.
        auth_url = request.host_url.rstrip('/') + '/api/auth/student-login'
        try:
            r = requests.post(auth_url, json={
                              'control_number': control_number, 'password': password}, timeout=5)
        except requests.RequestException as e:
            return jsonify({'message': 'Error conectando al servicio de validación de credenciales', 'error': str(e)}), 503

        if r.status_code != 200:
            # propagate 401 or 503 as appropriate
            if r.status_code == 401:
                return jsonify({'message': 'Credenciales inválidas'}), 401
            return jsonify({'message': 'Error en la validación de credenciales'}), 503

        auth_data = r.json()
        student_info = auth_data.get('student')
        if not student_info:
            return jsonify({'message': 'No se obtuvo información del estudiante tras validar credenciales'}), 503

        # Ensure student exists/updated in DB
        student = Student.query.filter_by(
            control_number=control_number).first()
        if not student:
            student = Student()
            student.control_number = control_number
            student.full_name = student_info.get(
                'full_name') or student_info.get('full_name') or ''
            student.email = student_info.get('email') or ''
            db.session.add(student)
            db.session.commit()
        else:
            # update small fields
            student.full_name = student_info.get(
                'full_name') or student.full_name
            student.email = student_info.get('email') or student.email
            db.session.add(student)
            db.session.commit()

        # Check existing attendance for this student+activity and refuse duplicates
        existing_att = Attendance.query.filter_by(
            student_id=student.id, activity_id=activity.id).first()
        if existing_att:
            return jsonify({'message': 'Ya existe un registro de asistencia para esta actividad'}), 409

        # Create attendance (self check-in). For magistral activities we record
        # a check-in time and mark as 'Parcial' (same behavior as admin check-in).
        now = datetime.now(timezone.utc)
        attendance = Attendance()
        attendance.student_id = student.id
        attendance.activity_id = activity.id
        attendance.check_in_time = now
        attendance.status = 'Parcial'
        db.session.add(attendance)

        # If there's an existing registration, mark it as attended/confirmed
        registration = Registration.query.filter_by(
            student_id=student.id, activity_id=activity.id).first()
        if registration:
            registration.attended = True
            registration.status = 'Asistió'
            registration.confirmation_date = db.func.now()
            db.session.add(registration)

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return jsonify({'message': 'Error al crear registro de asistencia', 'error': str(e)}), 500

        try:
            db.session.refresh(attendance)
        except Exception:
            pass

        return jsonify({'message': 'Asistencia registrada', 'attendance': attendance_schema.dump(attendance)}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error al procesar registro in situ', 'error': str(e)}), 500
