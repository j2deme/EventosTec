from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timezone
from app.utils.datetime_utils import parse_datetime_with_timezone
from app import db
from app.schemas import attendance_schema, attendances_schema
from app.models.attendance import Attendance
from app.models.student import Student
from app.models.activity import Activity
from app.utils.auth_helpers import require_admin
from app.services.attendance_service import calculate_attendance_percentage
from app.models.registration import Registration

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
        student = db.session.get(Student, student_id)
        if not student:
            return jsonify({'message': 'Estudiante no encontrado'}), 404

        activity = db.session.get(Activity, activity_id)
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

        if activity.activity_type == 'Magistral' and activity.related_activities:
            from app.services.attendance_service import create_related_attendances
            try:
                create_related_attendances(student_id, activity_id)
                db.session.commit()  # Commit de las asistencias relacionadas
            except Exception as e:
                db.session.rollback()
                # Opcional: loggear el error pero no fallar el check-in principal?
                # Por ahora, dejamos que el error se propague
                raise e

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
    """
    Registra la hora de salida (check-out) para un estudiante en una actividad magistral.
    Calcula el porcentaje de asistencia automáticamente.
    """
    try:
        data = request.get_json()
        student_id = data.get('student_id')
        activity_id = data.get('activity_id')

        if not student_id or not activity_id:
            return jsonify({'message': 'Se requieren student_id y activity_id'}), 400

        # 1. Buscar registro de asistencia
        attendance = db.session.query(Attendance).filter_by(
            student_id=student_id, activity_id=activity_id
        ).first()

        if not attendance:
            return jsonify({'message': 'No se encontró registro de asistencia'}), 404

        # 2. Validaciones de estado
        if not attendance.check_in_time:
            return jsonify({'message': 'No se ha registrado check-in'}), 400

        if attendance.check_out_time:
            # Si ya hay check-out, recalculamos por si acaso (aunque no es lo típico)
            # O simplemente devolvemos el existente. Aquí optamos por recalcular.
            # Esto puede ser útil si se pausó/reanudó después del primer check-out.
            pass  # Continuamos para recalcular

            # 3. Registrar check-out
            # Importante: Usar datetime.now(timezone.utc) o datetime.utcnow() si tus modelos lo requieren.
            # Asegúrate de la consistencia de zonas horarias.
            attendance.check_out_time = datetime.now(timezone.utc)

        # 4. Calcular porcentaje de asistencia y estado
        # Esta función ahora está en el servicio y considera pausas.
        try:
            # Pasamos el ID para que el servicio haga el query y el commit
            calculate_attendance_percentage(attendance.id)
            # Recargamos el objeto attendance desde la DB para tener los valores actualizados
            # que fueron modificados por calculate_attendance_percentage
            db.session.refresh(attendance)
            # Sincronizar con preregistro si existe: si la asistencia resultó en 'Asistió', actualizar Registration
            if attendance.status == 'Asistió':
                registration = db.session.query(Registration).filter_by(
                    student_id=attendance.student_id, activity_id=attendance.activity_id
                ).first()
                if registration:
                    registration.attended = True
                    registration.status = 'Asistió'
                    registration.confirmation_date = db.func.now()
                    db.session.add(registration)
        except Exception as e:
            # Si falla el cálculo, hacemos rollback y reportamos error
            db.session.rollback()
            return jsonify({
                'message': 'Error al calcular el porcentaje de asistencia',
                'error': str(e)
            }), 500

        # 5. Guardar cambios en la base de datos
        db.session.commit()

        return jsonify({
            'message': 'Check-out registrado exitosamente',
            'attendance': attendance_schema.dump(attendance)
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'message': 'Error al registrar check-out',
            'error': str(e)
        }), 500

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
        from app.services.attendance_service import pause_attendance
        attendance = pause_attendance(attendance.id)

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
        from app.services.attendance_service import resume_attendance
        attendance = resume_attendance(attendance.id)

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
        activity = db.session.get(Activity, activity_id)
        if not activity:
            return jsonify({'message': 'Actividad no encontrada'}), 404

        created_attendances = []

        for student_id in student_ids:
            # Verificar que el estudiante exista
            student = db.session.get(Student, student_id)
            if not student:
                continue

            # Verificar si ya existe registro
            existing_attendance = db.session.query(Attendance).filter_by(
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

        query = db.session.query(Attendance)

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
        attendance = db.session.get(Attendance, attendance_id)
        if not attendance:
            return jsonify({'message': 'Asistencia no encontrada'}), 404

        return jsonify({'attendance': attendance_schema.dump(attendance)}), 200

    except Exception as e:
        return jsonify({'message': 'Error al obtener asistencia', 'error': str(e)}), 500


@attendances_bp.route('/<int:attendance_id>', methods=['DELETE'])
@jwt_required()
@require_admin
def delete_attendance(attendance_id):
    try:
        attendance = db.session.get(Attendance, attendance_id)
        if not attendance:
            return jsonify({'message': 'Asistencia no encontrada'}), 404

        # Intentar sincronizar con preregistro si existe
        registration = db.session.query(Registration).filter_by(
            student_id=attendance.student_id, activity_id=attendance.activity_id
        ).first()

        if registration:
            # Revertir el preregistro a estado 'Registrado' y limpiar confirmation_date/attended
            registration.attended = False
            registration.confirmation_date = None
            registration.status = 'Registrado'
            db.session.add(registration)

        # Borrado físico de la asistencia
        db.session.delete(attendance)
        db.session.commit()

        return jsonify({'message': 'Asistencia eliminada exitosamente'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error al eliminar asistencia', 'error': str(e)}), 500


@attendances_bp.route('/register', methods=['POST'])
@jwt_required()
@require_admin
def register_attendance():
    """
    Endpoint para que el administrador registre manualmente una asistencia.
    Payload esperado (JSON):
      - student_id (int)
      - activity_id (int)
      - mark_present (bool) opcional -> si true marca 100% y status 'Asistió'
      - check_in_time / check_out_time (ISO strings) opcionales
    Si existe un preregistro asociado, se sincroniza (attended=True, status='Asistió').
    """
    try:
        data = request.get_json() or {}
        student_id = data.get('student_id')
        activity_id = data.get('activity_id')
        mark_present = data.get('mark_present', False)
        check_in = data.get('check_in_time')
        check_out = data.get('check_out_time')

        if not student_id or not activity_id:
            return jsonify({'message': 'student_id y activity_id son requeridos'}), 400

        student = db.session.get(Student, student_id)
        if not student:
            return jsonify({'message': 'Estudiante no encontrado'}), 404

        activity = db.session.get(Activity, activity_id)
        if not activity:
            return jsonify({'message': 'Actividad no encontrada'}), 404

        # Buscar o crear attendance
        attendance = db.session.query(Attendance).filter_by(
            student_id=student_id, activity_id=activity_id
        ).first()

        now = datetime.now(timezone.utc)

        if attendance:
            # actualizar campos si se proporcionan
            if check_in:
                try:
                    attendance.check_in_time = parse_datetime_with_timezone(
                        check_in)
                except Exception:
                    attendance.check_in_time = now
            if check_out:
                try:
                    attendance.check_out_time = parse_datetime_with_timezone(
                        check_out)
                except Exception:
                    attendance.check_out_time = now
            if mark_present:
                attendance.attendance_percentage = 100.0
                attendance.status = 'Asisti\u00f3'
                if not attendance.check_in_time:
                    attendance.check_in_time = now
                if not attendance.check_out_time:
                    attendance.check_out_time = now

            db.session.add(attendance)
        else:
            # crear nuevo registro
            if mark_present:
                attendance = Attendance(
                    student_id=student_id,
                    activity_id=activity_id,
                    attendance_percentage=100.0,
                    status='Asisti\u00f3',
                    check_in_time=parse_datetime_with_timezone(
                        check_in) if check_in else now,
                    check_out_time=parse_datetime_with_timezone(
                        check_out) if check_out else now
                )
            else:
                attendance = Attendance(
                    student_id=student_id,
                    activity_id=activity_id,
                    check_in_time=parse_datetime_with_timezone(
                        check_in) if check_in else None,
                    check_out_time=parse_datetime_with_timezone(
                        check_out) if check_out else None,
                    status='Parcial' if check_in and not check_out else 'Ausente'
                )
            db.session.add(attendance)

        # Sincronizar con preregistro si existe y si se marca presente
        if mark_present:
            registration = db.session.query(Registration).filter_by(
                student_id=student_id, activity_id=activity_id
            ).first()
            if registration:
                registration.attended = True
                registration.status = 'Asisti\u00f3'
                registration.confirmation_date = db.func.now()
                db.session.add(registration)

        db.session.commit()

        return jsonify({'message': 'Asistencia registrada', 'attendance': attendance_schema.dump(attendance)}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error al registrar asistencia', 'error': str(e)}), 500
