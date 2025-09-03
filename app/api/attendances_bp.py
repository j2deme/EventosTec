from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timezone
from app import db
from app.schemas import attendance_schema, attendances_schema
from app.models.attendance import Attendance
from app.models.student import Student
from app.models.activity import Activity
from app.utils.auth_helpers import require_admin

attendances_bp = Blueprint('attendances', __name__,
                           url_prefix='/api/attendances')

# Check-in para conferencias magistrales


@attendances_bp.route('/check-in', methods=['POST'])
@jwt_required()
@require_admin
def check_in():
    try:
        data = request.get_json()
        student_id = data.get('student_id')
        activity_id = data.get('activity_id')

        # Validar que el estudiante y actividad existan
        student = Student.query.get(student_id)
        if not student:
            return jsonify({'message': 'Estudiante no encontrado'}), 404

        activity = Activity.query.get(activity_id)
        if not activity:
            return jsonify({'message': 'Actividad no encontrada'}), 404

        # Verificar que sea una conferencia magistral
        if activity.activity_type != 'Magistral':
            return jsonify({'message': 'Solo se permite check-in para conferencias magistrales'}), 400

        # Verificar si ya existe un registro de asistencia
        attendance = Attendance.query.filter_by(
            student_id=student_id, activity_id=activity_id
        ).first()

        if attendance:
            # Si ya existe y tiene check-in, no permitir nuevo check-in
            if attendance.check_in_time:
                return jsonify({
                    'message': 'Ya se ha registrado el check-in',
                    'attendance': attendance_schema.dump(attendance)
                }), 200

            # Si existe pero no tiene check-in, actualizar
            attendance.check_in_time = datetime.now(timezone.utc)
            attendance.status = 'Parcial'
        else:
            # Crear nuevo registro de asistencia
            attendance = Attendance(
                student_id=student_id,
                activity_id=activity_id,
                check_in_time=datetime.now(timezone.utc),
                status='Parcial'
            )
            db.session.add(attendance)

        db.session.commit()

        return jsonify({
            'message': 'Check-in registrado exitosamente',
            'attendance': attendance_schema.dump(attendance)
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error al registrar check-in', 'error': str(e)}), 400

# Check-out para conferencias magistrales


@attendances_bp.route('/check-out', methods=['POST'])
@jwt_required()
@require_admin
def check_out():
    try:
        data = request.get_json()
        student_id = data.get('student_id')
        activity_id = data.get('activity_id')

        # Buscar registro de asistencia
        attendance = Attendance.query.filter_by(
            student_id=student_id, activity_id=activity_id
        ).first()

        if not attendance:
            return jsonify({'message': 'No se encontró registro de asistencia'}), 404

        if not attendance.check_in_time:
            return jsonify({'message': 'No se ha registrado check-in'}), 400

        if attendance.check_out_time:
            return jsonify({
                'message': 'Ya se ha registrado el check-out',
                'attendance': attendance_schema.dump(attendance)
            }), 200

        # Obtener la actividad relacionada
        activity = Activity.query.get(activity_id)
        if not activity:
            return jsonify({'message': 'Actividad no encontrada'}), 404

        # Registrar check-out
        attendance.check_out_time = datetime.now(timezone.utc)

        # Calcular porcentaje de asistencia
        if attendance.check_in_time and attendance.check_out_time:
            duration_seconds = (attendance.check_out_time -
                                attendance.check_in_time).total_seconds()
            activity_duration_seconds = activity.duration_hours * 3600

            if activity_duration_seconds > 0:
                percentage = (duration_seconds /
                              activity_duration_seconds) * 100
                attendance.attendance_percentage = round(percentage, 2)

                # Determinar estado final
                if attendance.attendance_percentage >= 80:
                    attendance.status = 'Asistió'
                else:
                    attendance.status = 'Parcial'
            else:
                attendance.attendance_percentage = 100
                attendance.status = 'Asistió'

        db.session.commit()

        return jsonify({
            'message': 'Check-out registrado exitosamente',
            'attendance': attendance_schema.dump(attendance)
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error al registrar check-out', 'error': str(e)}), 400

# Pausar asistencia


@attendances_bp.route('/pause', methods=['POST'])
@jwt_required()
@require_admin
def pause_attendance():
    try:
        data = request.get_json()
        student_id = data.get('student_id')
        activity_id = data.get('activity_id')

        attendance = Attendance.query.filter_by(
            student_id=student_id, activity_id=activity_id
        ).first()

        if not attendance:
            return jsonify({'message': 'No se encontró registro de asistencia'}), 404

        if not attendance.check_in_time:
            return jsonify({'message': 'No se ha registrado check-in'}), 400

        if attendance.check_out_time:
            return jsonify({'message': 'Ya se ha registrado check-out'}), 400

        # Registrar pausa
        attendance.is_paused = True

        db.session.commit()

        return jsonify({
            'message': 'Asistencia pausada exitosamente',
            'attendance': attendance_schema.dump(attendance)
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error al pausar asistencia', 'error': str(e)}), 400

# Reanudar asistencia


@attendances_bp.route('/resume', methods=['POST'])
@jwt_required()
@require_admin
def resume_attendance():
    try:
        data = request.get_json()
        student_id = data.get('student_id')
        activity_id = data.get('activity_id')

        attendance = Attendance.query.filter_by(
            student_id=student_id, activity_id=activity_id
        ).first()

        if not attendance:
            return jsonify({'message': 'No se encontró registro de asistencia'}), 404

        if not attendance.is_paused:
            return jsonify({'message': 'La asistencia no está pausada'}), 400

        # Reanudar asistencia
        attendance.is_paused = False

        db.session.commit()

        return jsonify({
            'message': 'Asistencia reanudada exitosamente',
            'attendance': attendance_schema.dump(attendance)
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error al reanudar asistencia', 'error': str(e)}), 400

# Crear asistencias post-evento (para conferencias y talleres)


@attendances_bp.route('/bulk-create', methods=['POST'])
@jwt_required()
@require_admin
def bulk_create_attendances():
    try:
        data = request.get_json()
        activity_id = data.get('activity_id')
        student_ids = data.get('student_ids', [])

        if not activity_id or not student_ids:
            return jsonify({'message': 'Actividad y lista de estudiantes son requeridos'}), 400

        # Verificar que la actividad exista
        activity = Activity.query.get(activity_id)
        if not activity:
            return jsonify({'message': 'Actividad no encontrada'}), 404

        created_attendances = []

        for student_id in student_ids:
            # Verificar que el estudiante exista
            student = Student.query.get(student_id)
            if not student:
                continue

            # Verificar si ya existe registro
            existing_attendance = Attendance.query.filter_by(
                student_id=student_id, activity_id=activity_id
            ).first()

            if not existing_attendance:
                # Crear asistencia
                attendance = Attendance(
                    student_id=student_id,
                    activity_id=activity_id,
                    attendance_percentage=100.0,
                    status='Asistió'
                )
                db.session.add(attendance)
                created_attendances.append(attendance)

        db.session.commit()

        return jsonify({
            'message': f'Asistencias creadas exitosamente: {len(created_attendances)}',
            'attendances': attendances_schema.dump(created_attendances)
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error al crear asistencias', 'error': str(e)}), 400

# Listar asistencias


@attendances_bp.route('/', methods=['GET'])
@jwt_required()
def get_attendances():
    try:
        # Parámetros de filtrado
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        student_id = request.args.get('student_id', type=int)
        activity_id = request.args.get('activity_id', type=int)
        status = request.args.get('status')

        query = Attendance.query

        if student_id:
            query = query.filter_by(student_id=student_id)

        if activity_id:
            query = query.filter_by(activity_id=activity_id)

        if status:
            query = query.filter_by(status=status)

        # Ordenar por fecha de creación
        query = query.order_by(Attendance.created_at.desc())

        attendances = query.paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify({
            'attendances': attendances_schema.dump(attendances.items),
            'total': attendances.total,
            'pages': attendances.pages,
            'current_page': page
        }), 200

    except Exception as e:
        return jsonify({'message': 'Error al obtener asistencias', 'error': str(e)}), 500

# Obtener asistencia por ID


@attendances_bp.route('/<int:attendance_id>', methods=['GET'])
@jwt_required()
def get_attendance(attendance_id):
    try:
        attendance = Attendance.query.get(attendance_id)
        if not attendance:
            return jsonify({'message': 'Asistencia no encontrada'}), 404

        return jsonify({'attendance': attendance_schema.dump(attendance)}), 200

    except Exception as e:
        return jsonify({'message': 'Error al obtener asistencia', 'error': str(e)}), 500
