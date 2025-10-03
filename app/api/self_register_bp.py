from flask import Blueprint, request, jsonify, render_template, current_app
import requests
from app import db
from app.models.student import Student
from app.models.activity import Activity
from app.models.registration import Registration
from app.services.registration_service import is_registration_allowed, create_registration_simple, has_schedule_conflict
from app.schemas import registration_schema
from datetime import datetime, timedelta
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

    return render_template('public/self_register.html', activity_token=token, activity_name=activity_name, activity_exists=activity_exists, token_provided=token_provided, token_invalid=token_invalid)


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

        now = datetime.utcnow()
        cutoff = (activity.start_datetime + timedelta(minutes=20)
                  ) if activity.start_datetime else None
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

        # Check duplicate registration
        existing = Registration.query.filter_by(
            student_id=student.id, activity_id=activity.id).first()
        if existing and existing.status != 'Cancelado':
            return jsonify({'message': 'Ya existe un registro para esta actividad'}), 409

        # Check schedule conflicts
        conflict, msg = has_schedule_conflict(student.id, activity.id)
        if conflict:
            return jsonify({'message': msg}), 409

        # Check capacity
        if not is_registration_allowed(activity.id):
            return jsonify({'message': 'Cupo lleno para esta actividad.'}), 400

        ok, reg = create_registration_simple(student.id, activity.id)
        if not ok:
            return jsonify({'message': reg}), 400

        # Ensure server-side defaults (timestamps) are loaded from DB
        try:
            db.session.refresh(reg)
        except Exception:
            # If refresh fails (detached instance), ignore and fall back to schema
            pass

        return jsonify({
            'message': 'Registro in situ creado',
            'registration': registration_schema.dump(reg)
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error al procesar registro in situ', 'error': str(e)}), 500
