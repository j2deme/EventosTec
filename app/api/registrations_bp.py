from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.schemas import registration_schema, registrations_schema
from app.models.registration import Registration
from app.models.student import Student
from app.models.activity import Activity
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
        existing_registration = db.session.query(Registration).filter_by(
            student_id=student_id, activity_id=activity_id
        ).first()

        if existing_registration:
            return jsonify({
                'message': 'Ya existe un preregistro para esta actividad',
                'registration': registration_schema.dump(existing_registration)
            }), 200

        # Verificar cupo disponible (para conferencias y talleres)
        from app.services.registration_service import is_registration_allowed
        if not is_registration_allowed(activity_id):
            return jsonify({'message': 'Cupo lleno para esta actividad'}), 400

        '''if activity.activity_type in ['Conferencia', 'Taller', 'Curso']:
            if activity.max_capacity:
                current_registrations = Registration.query.filter_by(
                    activity_id=activity_id, status='Registrado'
                ).count()

                if current_registrations >= activity.max_capacity:
                    return jsonify({'message': 'Cupo lleno para esta actividad'}), 400'''

        # Crear preregistro
        registration = Registration(
            student_id=student_id,
            activity_id=activity_id,
            status='Registrado'
        )

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

        query = db.session.query(Registration)

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

        return jsonify({'registration': registration_schema.dump(registration)}), 200

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

        if new_status:
            registration.status = new_status

        if attended is not None:
            registration.attended = attended
            if attended:
                registration.confirmation_date = db.func.now()

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

        # Solo permitir cancelación si no ha asistido
        if registration.attended:
            return jsonify({'message': 'No se puede cancelar un preregistro con asistencia confirmada'}), 400

        registration.status = 'Cancelado'
        db.session.commit()

        return jsonify({'message': 'Preregistro cancelado exitosamente'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error al cancelar preregistro', 'error': str(e)}), 400
