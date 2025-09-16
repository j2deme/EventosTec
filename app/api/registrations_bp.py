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

        data = request.get_json()
        student_id = data.get('student_id')
        activity_id = data.get('activity_id')

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

        if user_type == 'admin':
            return jsonify({'registration': registration_schema.dump(registration)}), 200
        elif user_type == 'student' and user is not None:
            if registration.student_id != user.id:
                return jsonify({'message': 'Acceso denegado'}), 403
            return jsonify({'registration': registration_schema.dump(registration)}), 200
        else:
            return jsonify({'message': 'Acceso denegado'}), 403

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

        data = request.get_json()
        new_status = data.get('status')
        attended = data.get('attended')

        valid_transitions = {
            'Registrado': ['Confirmado', 'Cancelado', 'Asistió', 'Ausente'],
            'Confirmado': ['Registrado', 'Asistió', 'Ausente', 'Cancelado'],
            'Asistió': [],  # No se puede cambiar una vez asistido
            # Esto puede ser útil si el estudiante llega tarde y se confirma su asistencia, o si regresa después de haber sido marcado como ausente.
            'Ausente': ['Registrado', 'Confirmado'],
            'Cancelado': ['Registrado']  # Permitir reactivar un cancelado
        }

        current_status = registration.status
        if new_status and new_status != current_status:
            if new_status not in valid_transitions.get(current_status, []):
                return jsonify({'message': f'Transición de estado no permitida: {current_status} -> {new_status}'}), 400

        if new_status:
            registration.status = new_status

        if attended is not None:
            registration.attended = attended
            if attended:
                # Marcar asistencia en el preregistro y setear fecha de confirmacion
                registration.status = 'Asistió'
                registration.confirmation_date = db.func.now()

                # Sincronizar con Attendance: crear o actualizar registro de asistencia asociado
                attendance = Attendance.query.filter_by(
                    student_id=registration.student_id, activity_id=registration.activity_id
                ).first()
                if attendance:
                    attendance.attendance_percentage = 100.0
                    attendance.status = 'Asistió'
                else:
                    attendance = Attendance()
                    attendance.student_id = registration.student_id
                    attendance.activity_id = registration.activity_id
                    attendance.attendance_percentage = 100.0
                    attendance.status = 'Asistió'
                    db.session.add(attendance)
            else:
                # Si se desmarca attended, limpiar confirmation_date para mantener consistencia
                registration.confirmation_date = None

        db.session.commit()

        return jsonify({
            'message': 'Preregistro actualizado exitosamente',
            'registration': registration_schema.dump(registration)
        }), 200

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
