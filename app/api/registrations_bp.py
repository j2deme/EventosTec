from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.schemas import registration_schema, registrations_schema
from app.models.registration import Registration
from app.models.student import Student
from app.models.activity import Activity
from app.models.attendance import Attendance
from app.utils.auth_helpers import require_admin, get_user_or_403

registrations_bp = Blueprint(
    'registrations', __name__, url_prefix='/api/registrations')

# Crear preregistro


@registrations_bp.route('/', methods=['POST'])
@jwt_required()
def create_registration():
    try:
        user, user_type, error = get_user_or_403()
        if error:
            return error

        payload = request.get_json() or {}
        student_id = payload.get('student_id')
        activity_id = payload.get('activity_id')

        # Validar acceso
        if user_type == 'student':
            # Estudiante solo puede preregistrarse a sí mismo
            if int(get_jwt_identity()) != student_id:
                return jsonify({'message': 'Acceso denegado. No puedes preregistrar a otros estudiantes.'}), 403
        elif user_type == 'admin':
            # Admin puede preregistrar a cualquier estudiante
            pass
        else:
            return jsonify({'message': 'Tipo de usuario no válido'}), 400

        # Validar que el estudiante y actividad existan
        student = db.session.get(Student, student_id)
        if not student:
            return jsonify({'message': 'Estudiante no encontrado'}), 404

        activity = db.session.get(Activity, activity_id)
        if not activity:
            return jsonify({'message': 'Actividad no encontrada'}), 404

        # Verificar si ya existe un preregistro
        existing_registration = Registration.query.filter_by(
            student_id=student_id, activity_id=activity_id
        ).first()

        if existing_registration:
            # ✨ Si existe y está cancelado, permitir re-registro
            if existing_registration.status == 'Cancelado':
                # Verificar conflictos de horario
                from app.services.registration_service import has_schedule_conflict
                conflict_exists, conflict_message = has_schedule_conflict(
                    student_id, activity_id)
                if conflict_exists:
                    # 409 Conflict
                    return jsonify({'message': conflict_message}), 409

                # Verificar cupo
                from app.services.registration_service import is_registration_allowed
                if not is_registration_allowed(activity_id):
                    return jsonify({'message': 'Cupo lleno para esta actividad.'}), 400

                # ✨ Re-registrar: actualizar estado y datos
                existing_registration.status = 'Registrado'
                existing_registration.registration_date = db.func.now()
                existing_registration.confirmation_date = None
                existing_registration.attended = False

                db.session.commit()

                return jsonify({
                    'message': 'Reactivación del registro realizado exitosamente',
                    'registration': registration_schema.dump(existing_registration)
                }), 200
            else:
                # Si ya está registrado y no cancelado, no permitir nuevo preregistro
                return jsonify({
                    'message': 'Ya existe un preregistro para esta actividad',
                    'registration': registration_schema.dump(existing_registration)
                }), 200

        # Verificar conflictos de horario
        from app.services.registration_service import has_schedule_conflict
        conflict_exists, conflict_message = has_schedule_conflict(
            student_id, activity_id)
        if conflict_exists:
            return jsonify({'message': conflict_message}), 409  # 409 Conflict

        # Verificar cupo
        from app.services.registration_service import is_registration_allowed
        if not is_registration_allowed(activity_id):
            return jsonify({'message': 'Cupo lleno para esta actividad.'}), 400

        # Sino hubo conflictos, crear preregistro
        registration = Registration()
        registration.student_id = student_id
        registration.activity_id = activity_id
        registration.status = 'Registrado'

        db.session.add(registration)
        db.session.commit()

        return jsonify({
            'message': 'Preregistro creado exitosamente',
            'registration': registration_schema.dump(registration)
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error al crear preregistro', 'error': str(e)}), 400

# Listar preregistros


@registrations_bp.route('/', methods=['GET'])
@jwt_required()
@require_admin
def get_registrations():
    try:
        # Parámetros de filtrado
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        student_id = request.args.get('student_id', type=int)
        activity_id = request.args.get('activity_id', type=int)
        status = request.args.get('status')

        from sqlalchemy.orm import joinedload

        # Modificar la consulta para cargar relaciones de forma eager
        query = Registration.query.options(
            joinedload(getattr(Registration, 'activity')),
            joinedload(getattr(Registration, 'student'))
        )

        if student_id:
            query = query.filter_by(student_id=student_id)

        if activity_id:
            query = query.filter_by(activity_id=activity_id)

        if status:
            query = query.filter_by(status=status)

        # Ordenar por fecha de registro
        query = query.order_by(Registration.registration_date.desc())

        registrations = query.paginate(
            page=page, per_page=per_page, error_out=False
        )

        for registration in registrations.items:
            # Cargar la relación con la actividad
            if not registration.activity:
                # Si no hay relación, intentar cargarla
                registration.activity = db.session.get(
                    Activity, registration.activity_id)

        return jsonify({
            'registrations': registrations_schema.dump(registrations.items),
            'total': registrations.total,
            'pages': registrations.pages,
            'current_page': page
        }), 200

    except Exception as e:
        return jsonify({'message': 'Error al obtener preregistros', 'error': str(e)}), 500

# Obtener preregistro por ID


@registrations_bp.route('/<int:registration_id>', methods=['GET'])
@jwt_required()
def get_registration(registration_id):
    try:
        registration = db.session.get(Registration, registration_id)
        if not registration:
            return jsonify({'message': 'Preregistro no encontrado'}), 404

        # Control de acceso: admin puede ver cualquiera; student solo el suyo
        user, user_type, err = get_user_or_403()
        if err:
            return err

        # Determine whether the caller requested a synthesized flat view
        synth_flag = request.args.get(
            'synth') or request.args.get('synthesized')

        if user_type == 'admin':
            payload = {'registration': registration_schema.dump(registration)}
        elif user_type == 'student' and user is not None:
            if registration.student_id != user.id:
                return jsonify({'message': 'Acceso denegado'}), 403
            payload = {'registration': registration_schema.dump(registration)}
        else:
            return jsonify({'message': 'Acceso denegado'}), 403

        # If synth param is present (truthy), include a synthesized flat shape
        if synth_flag:
            try:
                reg = payload.get('registration')

                # reg may sometimes be a list, None, or an already-serialized dict-like object
                # Normalize into reg_dict (a plain dict) so static analyzers know .get is safe.
                if isinstance(reg, dict):
                    reg_dict = reg
                elif isinstance(reg, list):
                    first = reg[0] if reg else {}
                    reg_dict = first if isinstance(first, dict) else {}
                else:
                    reg_dict = {}

                # helper to safely get nested dicts (prefer dicts over lists/None)
                def as_dict(maybe):
                    if isinstance(maybe, dict):
                        return maybe
                    if isinstance(maybe, list) and maybe:
                        return maybe[0] if isinstance(maybe[0], dict) else {}
                    return {}

                student = as_dict(reg_dict.get('student'))
                activity = as_dict(reg_dict.get('activity'))
                event = as_dict(activity.get('event')) if activity else {}

                # Build synthesized convenience object with safe lookups
                synth = {
                    'registration_id': reg_dict.get('id'),
                    'status': reg_dict.get('status'),
                    'registration_date': reg_dict.get('registration_date') or reg_dict.get('created_at'),
                    'student_id': reg_dict.get('student_id'),
                    'activity_id': reg_dict.get('activity_id'),
                    # student fields (may be nested)
                    'student_name': student.get('full_name') or reg_dict.get('student_name'),
                    'student_identifier': student.get('control_number') or reg_dict.get('student_identifier'),
                    'email': student.get('email') or reg_dict.get('email'),
                    # activity/event fields
                    'activity_name': activity.get('name') or reg_dict.get('activity_name'),
                    'event_name': event.get('name') or reg_dict.get('event_name'),
                }
                payload['synthesized'] = synth
            except Exception:
                # If anything goes wrong during synthesis, skip silently to avoid breaking clients
                pass

        return jsonify(payload), 200

    except Exception as e:
        return jsonify({'message': 'Error al obtener preregistro', 'error': str(e)}), 500

# Actualizar preregistro (confirmar asistencia)


@registrations_bp.route('/<int:registration_id>', methods=['PUT'])
@jwt_required()
@require_admin
def update_registration(registration_id):
    try:
        registration = db.session.get(Registration, registration_id)
        if not registration:
            return jsonify({'message': 'Preregistro no encontrado'}), 404

        payload = request.get_json() or {}
        new_status = payload.get('status')
        attended = payload.get('attended')

        valid_transitions = {
            'Registrado': ['Confirmado', 'Cancelado', 'Asistió', 'Ausente'],
            'Confirmado': ['Registrado', 'Asistió', 'Ausente', 'Cancelado'],
            'Asistió': ['Confirmado'],
            'Ausente': ['Registrado', 'Confirmado'],
            'Cancelado': ['Registrado']
        }

        current_status = registration.status
        # Prepare reporting variables
        attendance = None
        attendance_deleted = False

        # Validate status transition
        if new_status and new_status != current_status:
            if new_status not in valid_transitions.get(current_status, []):
                return jsonify({'message': f'Transición de estado no permitida: {current_status} -> {new_status}'}), 400

            # Handle status-driven sync with Attendance
            prev_status = registration.status
            registration.status = new_status

            if prev_status != 'Asistió' and new_status == 'Asistió':
                # create or update attendance
                attendance = Attendance.query.filter_by(
                    student_id=registration.student_id, activity_id=registration.activity_id
                ).first()
                if attendance:
                    attendance.attendance_percentage = 100.0
                    attendance.status = 'Asistió'
                    if not attendance.check_in_time:
                        attendance.check_in_time = db.func.now()
                    if not attendance.check_out_time:
                        attendance.check_out_time = db.func.now()
                    db.session.add(attendance)
                else:
                    attendance = Attendance()
                    attendance.student_id = registration.student_id
                    attendance.activity_id = registration.activity_id
                    attendance.attendance_percentage = 100.0
                    attendance.status = 'Asistió'
                    attendance.check_in_time = db.func.now()
                    attendance.check_out_time = db.func.now()
                    db.session.add(attendance)

            elif prev_status == 'Asistió' and new_status != 'Asistió':
                # delete attendance if exists
                attendance = Attendance.query.filter_by(
                    student_id=registration.student_id, activity_id=registration.activity_id
                ).first()
                if attendance:
                    try:
                        db.session.delete(attendance)
                        attendance_deleted = True
                        attendance = None
                    except Exception:
                        # fallback: convert to Ausente
                        attendance.status = 'Ausente'
                        attendance.attendance_percentage = 0.0
                        db.session.add(attendance)

        # Handle explicit 'attended' flag (from UI or API)
        if attended is not None:
            registration.attended = bool(attended)
            if registration.attended:
                registration.status = 'Asistió'
                registration.confirmation_date = db.func.now()

                attendance = Attendance.query.filter_by(
                    student_id=registration.student_id, activity_id=registration.activity_id
                ).first()
                if attendance:
                    attendance.attendance_percentage = 100.0
                    attendance.status = 'Asistió'
                    if not attendance.check_in_time:
                        attendance.check_in_time = db.func.now()
                    if not attendance.check_out_time:
                        attendance.check_out_time = db.func.now()
                    db.session.add(attendance)
                else:
                    attendance = Attendance()
                    attendance.student_id = registration.student_id
                    attendance.activity_id = registration.activity_id
                    attendance.attendance_percentage = 100.0
                    attendance.status = 'Asistió'
                    attendance.check_in_time = db.func.now()
                    attendance.check_out_time = db.func.now()
                    db.session.add(attendance)
            else:
                registration.confirmation_date = None

        db.session.commit()

        # Build response payload
        resp = {
            'message': 'Preregistro actualizado exitosamente',
            'registration': registration_schema.dump(registration)
        }

        # Include attendance info or deletion flag
        try:
            from app.schemas import attendance_schema as _att_schema
            if attendance is not None:
                try:
                    resp['attendance'] = _att_schema.dump(attendance)
                except Exception:
                    resp['attendance'] = {
                        'id': getattr(attendance, 'id', None),
                        'student_id': getattr(attendance, 'student_id', None),
                        'activity_id': getattr(attendance, 'activity_id', None),
                        'status': getattr(attendance, 'status', None),
                    }
            if attendance_deleted:
                resp['attendance_deleted'] = True
        except Exception:
            pass

        return jsonify(resp), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error al actualizar preregistro', 'error': str(e)}), 400

# Cancelar preregistro


@registrations_bp.route('/<int:registration_id>', methods=['DELETE'])
@jwt_required()
def delete_registration(registration_id):
    try:
        registration = db.session.get(Registration, registration_id)
        if not registration:
            return jsonify({'message': 'Preregistro no encontrado'}), 404

        # Control de acceso: admin puede eliminar cualquiera; student solo su propio preregistro
        user, user_type, err = get_user_or_403()
        if err:
            return err

        if user_type == 'student' and user is not None:
            if registration.student_id != user.id:
                return jsonify({'message': 'Acceso denegado'}), 403

        # Solo permitir cancelación si no ha asistido
        if registration.attended:
            return jsonify({'message': 'No se puede cancelar un preregistro con asistencia confirmada'}), 400

        registration.status = 'Cancelado'
        db.session.commit()

        return jsonify({'message': 'Preregistro cancelado exitosamente'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error al cancelar preregistro', 'error': str(e)}), 400
