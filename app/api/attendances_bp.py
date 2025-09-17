from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from datetime import datetime, timezone
from marshmallow import ValidationError
from app.utils.datetime_utils import parse_datetime_with_timezone
from app import db
from app.schemas import attendance_schema, attendances_schema
from app.models.attendance import Attendance
from app.models.student import Student
from app.models.activity import Activity
from app.utils.auth_helpers import require_admin, get_user_or_403
from app.services.attendance_service import calculate_attendance_percentage
from app.models.registration import Registration


attendances_bp = Blueprint('attendances', __name__,
                           url_prefix='/api/attendances')


@attendances_bp.route('/check-in', methods=['POST'])
@jwt_required()
@require_admin
def check_in():
    try:
        payload = request.get_json() or {}
        student_id = payload.get('student_id')
        activity_id = payload.get('activity_id')

        student = db.session.get(Student, student_id)
        if not student:
            return jsonify({'message': 'Estudiante no encontrado'}), 404

        activity = db.session.get(Activity, activity_id)
        if not activity:
            return jsonify({'message': 'Actividad no encontrada'}), 404

        if activity.activity_type != 'Magistral':
            return jsonify({'message': 'Solo se permite check-in para conferencias magistrales'}), 400

        attendance = Attendance.query.filter_by(
            student_id=student_id, activity_id=activity_id).first()

        now = datetime.now(timezone.utc)
        if attendance:
            if attendance.check_in_time:
                return jsonify({'message': 'Ya se ha registrado el check-in', 'attendance': attendance_schema.dump(attendance)}), 200
            attendance.check_in_time = now
            attendance.status = 'Parcial'
            db.session.add(attendance)
        else:
            attendance = Attendance()
            attendance.student_id = student_id
            attendance.activity_id = activity_id
            attendance.check_in_time = now
            attendance.status = 'Parcial'
            db.session.add(attendance)

        if activity.activity_type == 'Magistral' and getattr(activity, 'related_activities', None):
            from app.services.attendance_service import create_related_attendances
            try:
                create_related_attendances(student_id, activity_id)
            except Exception:
                db.session.rollback()
                raise

        db.session.commit()

        return jsonify({'message': 'Check-in registrado exitosamente', 'attendance': attendance_schema.dump(attendance)}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error al registrar check-in', 'error': str(e)}), 400


@attendances_bp.route('/check-out', methods=['POST'])
@jwt_required()
@require_admin
def check_out():
    try:
        payload = request.get_json() or {}
        student_id = payload.get('student_id')
        activity_id = payload.get('activity_id')

        if not student_id or not activity_id:
            return jsonify({'message': 'Se requieren student_id y activity_id'}), 400

        attendance = Attendance.query.filter_by(
            student_id=student_id, activity_id=activity_id).first()
        if not attendance:
            return jsonify({'message': 'No se encontró registro de asistencia'}), 404

        if not attendance.check_in_time:
            return jsonify({'message': 'No se ha registrado check-in'}), 400

        attendance.check_out_time = datetime.now(timezone.utc)
        db.session.add(attendance)

        try:
            calculate_attendance_percentage(attendance.id)
            db.session.commit()
            db.session.refresh(attendance)

            if attendance.status == 'Asistió':
                registration = Registration.query.filter_by(
                    student_id=attendance.student_id, activity_id=attendance.activity_id).first()
                if registration:
                    registration.attended = True
                    registration.status = 'Asistió'
                    registration.confirmation_date = db.func.now()
                    db.session.add(registration)
        except Exception as e:
            db.session.rollback()
            return jsonify({'message': 'Error al calcular el porcentaje de asistencia', 'error': str(e)}), 500

        db.session.commit()

        return jsonify({'message': 'Check-out registrado exitosamente', 'attendance': attendance_schema.dump(attendance)}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error al registrar check-out', 'error': str(e)}), 500


@attendances_bp.route('/pause', methods=['POST'])
@jwt_required()
@require_admin
def pause_attendance():
    try:
        data = request.get_json() or {}
        student_id = data.get('student_id')
        activity_id = data.get('activity_id')

        attendance = Attendance.query.filter_by(
            student_id=student_id, activity_id=activity_id).first()
        if not attendance:
            return jsonify({'message': 'No se encontró registro de asistencia'}), 404

        if not attendance.check_in_time:
            return jsonify({'message': 'No se ha registrado check-in'}), 400

        if attendance.check_out_time:
            return jsonify({'message': 'Ya se ha registrado check-out'}), 400

        from app.services.attendance_service import pause_attendance as svc_pause
        attendance = svc_pause(attendance.id)
        db.session.add(attendance)
        db.session.commit()

        return jsonify({'message': 'Asistencia pausada exitosamente', 'attendance': attendance_schema.dump(attendance)}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error al pausar asistencia', 'error': str(e)}), 400


@attendances_bp.route('/resume', methods=['POST'])
@jwt_required()
@require_admin
def resume_attendance():
    try:
        data = request.get_json() or {}
        student_id = data.get('student_id')
        activity_id = data.get('activity_id')

        attendance = Attendance.query.filter_by(
            student_id=student_id, activity_id=activity_id).first()
        if not attendance:
            return jsonify({'message': 'No se encontró registro de asistencia'}), 404

        if not attendance.is_paused:
            return jsonify({'message': 'La asistencia no está pausada'}), 400

        from app.services.attendance_service import resume_attendance as svc_resume
        attendance = svc_resume(attendance.id)
        db.session.add(attendance)
        db.session.commit()

        return jsonify({'message': 'Asistencia reanudada exitosamente', 'attendance': attendance_schema.dump(attendance)}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error al reanudar asistencia', 'error': str(e)}), 400


@attendances_bp.route('/bulk-create', methods=['POST'])
@jwt_required()
@require_admin
def bulk_create_attendances():
    try:
        payload = request.get_json() or {}
        activity_id = payload.get('activity_id')
        student_ids = payload.get('student_ids', [])

        if not activity_id or not student_ids:
            return jsonify({'message': 'Actividad y lista de estudiantes son requeridos'}), 400

        activity = db.session.get(Activity, activity_id)
        if not activity:
            return jsonify({'message': 'Actividad no encontrada'}), 404

        created_attendances = []

        for student_id in student_ids:
            student = db.session.get(Student, student_id)
            if not student:
                continue

            existing_attendance = Attendance.query.filter_by(
                student_id=student_id, activity_id=activity_id).first()
            if not existing_attendance:
                attendance = Attendance()
                attendance.student_id = student_id
                attendance.activity_id = activity_id
                attendance.attendance_percentage = 100.0
                attendance.status = 'Asistió'
                db.session.add(attendance)
                created_attendances.append(attendance)

                registration = Registration.query.filter_by(
                    student_id=student_id, activity_id=activity_id).first()
                if registration:
                    registration.attended = True
                    registration.status = 'Asistió'
                    registration.confirmation_date = db.func.now()
                    db.session.add(registration)

        db.session.commit()

        return jsonify({'message': f'Asistencias creadas exitosamente: {len(created_attendances)}', 'attendances': attendances_schema.dump(created_attendances)}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error al crear asistencias', 'error': str(e)}), 400


@attendances_bp.route('/', methods=['GET'])
@jwt_required()
def get_attendances():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        student_id = request.args.get('student_id', type=int)
        activity_id = request.args.get('activity_id', type=int)
        status = request.args.get('status')
        event_id = request.args.get('event_id', type=int)
        activity_type = request.args.get('activity_type')
        search = request.args.get('search', '').strip()

        user, user_type, err = get_user_or_403()
        if err:
            return err

        if user_type == 'student' and user is not None:
            student_id = user.id

        query = Attendance.query
        if student_id:
            query = query.filter_by(student_id=student_id)
        if activity_id:
            query = query.filter_by(activity_id=activity_id)
        if status:
            query = query.filter_by(status=status)

        # Join with Activity if we need to filter by event_id or activity_type
        if event_id or activity_type:
            query = query.join(Activity)
            if event_id:
                query = query.filter(Activity.event_id == event_id)
            if activity_type:
                query = query.filter(Activity.activity_type == activity_type)

        # Join with Student if we need to search by student fields
        if search:
            query = query.join(Student)
            query = query.filter(
                db.or_(
                    Student.full_name.ilike(f'%{search}%'),
                    Student.control_number.ilike(f'%{search}%')
                )
            )

        query = query.order_by(Attendance.created_at.desc())

        total = query.count()
        items = query.limit(per_page).offset((page - 1) * per_page).all()
        pages = (total + per_page - 1) // per_page if per_page else 1

        # Serializar y adjuntar objetos relacionados (student, activity) para
        # facilitar el consumo en el frontend sin múltiples requests.
        result = []
        for att in items:
            try:
                dumped = attendance_schema.dump(att)
                # Asegurar que `d` es un dict concreto para evitar errores de typing
                d = dict(dumped) if isinstance(dumped, dict) else {}
            except Exception:
                # Fallback: usar to_dict si hay problemas con el schema
                d = getattr(att, 'to_dict', lambda: {})() or {}

            # Adjuntar student y activity anidados cuando estén disponibles
            try:
                if hasattr(att, 'student') and att.student is not None:
                    # to_dict expone full_name y control_number
                    d['student'] = att.student.to_dict()
                    # conveniencia: exponer campos planos que espera el frontend
                    d['student_name'] = att.student.full_name
                    d['student_identifier'] = getattr(
                        att.student, 'control_number', '')
            except Exception:
                pass

            try:
                if hasattr(att, 'activity') and att.activity is not None:
                    d['activity'] = att.activity.to_dict()
                    d['activity_name'] = att.activity.name
                    # intentar añadir nombre de evento si existe la relación
                    if hasattr(att.activity, 'event') and att.activity.event is not None:
                        d['event_name'] = getattr(
                            att.activity.event, 'name', '')
            except Exception:
                pass

            # Intentar adjuntar información de preregistro (registration)
            try:
                # `Registration` fue importado en el módulo
                registration = Registration.query.filter_by(
                    student_id=att.student_id, activity_id=att.activity_id
                ).first()
                if registration:
                    d['registration_id'] = registration.id
                    # Exponer algunos campos útiles del preregistro para el frontend
                    d['registration'] = registration.to_dict()
            except Exception:
                # No romper la respuesta si por alguna razón falla la consulta
                pass

            result.append(d)

        return jsonify({'attendances': result, 'total': total, 'pages': pages, 'current_page': page}), 200

    except Exception as e:
        return jsonify({'message': 'Error al obtener asistencias', 'error': str(e)}), 500


@attendances_bp.route('/<int:attendance_id>', methods=['GET'])
@jwt_required()
def get_attendance(attendance_id):
    try:
        attendance = db.session.get(Attendance, attendance_id)
        if not attendance:
            return jsonify({'message': 'Asistencia no encontrada'}), 404

        user, user_type, err = get_user_or_403()
        if err:
            return err

        if user_type == 'student' and user is not None and attendance.student_id != user.id:
            return jsonify({'message': 'Acceso denegado'}), 403

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

        registration = Registration.query.filter_by(
            student_id=attendance.student_id, activity_id=attendance.activity_id).first()
        if registration:
            registration.attended = False
            registration.confirmation_date = None
            registration.status = 'Registrado'
            db.session.add(registration)

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
    try:
        payload = request.get_json() or {}
        student_id = payload.get('student_id')
        activity_id = payload.get('activity_id')
        mark_present = payload.get('mark_present', False)
        check_in = payload.get('check_in_time')
        check_out = payload.get('check_out_time')

        if not student_id or not activity_id:
            return jsonify({'message': 'student_id y activity_id son requeridos'}), 400

        student = db.session.get(Student, student_id)
        if not student:
            return jsonify({'message': 'Estudiante no encontrado'}), 404

        activity = db.session.get(Activity, activity_id)
        if not activity:
            return jsonify({'message': 'Actividad no encontrada'}), 404

        attendance = Attendance.query.filter_by(
            student_id=student_id, activity_id=activity_id).first()
        now = datetime.now(timezone.utc)
        created = False

        if attendance:
            if check_in:
                try:
                    attendance.check_in_time = parse_datetime_with_timezone(
                        check_in)
                except ValidationError as ve:
                    return jsonify({'message': 'Formato de check_in_time inválido', 'error': str(ve)}), 400
                except Exception:
                    attendance.check_in_time = now
            if check_out:
                try:
                    attendance.check_out_time = parse_datetime_with_timezone(
                        check_out)
                except ValidationError as ve:
                    return jsonify({'message': 'Formato de check_out_time inválido', 'error': str(ve)}), 400
                except Exception:
                    attendance.check_out_time = now
            if mark_present:
                attendance.attendance_percentage = 100.0
                attendance.status = 'Asistió'
                if not attendance.check_in_time:
                    attendance.check_in_time = now
                if not attendance.check_out_time:
                    attendance.check_out_time = now
            db.session.add(attendance)
        else:
            created = True
            if mark_present:
                attendance = Attendance()
                attendance.student_id = student_id
                attendance.activity_id = activity_id
                attendance.attendance_percentage = 100.0
                attendance.status = 'Asistió'
                attendance.check_in_time = None
                attendance.check_out_time = None
                if check_in:
                    try:
                        attendance.check_in_time = parse_datetime_with_timezone(
                            check_in)
                    except ValidationError as ve:
                        return jsonify({'message': 'Formato de check_in_time inválido', 'error': str(ve)}), 400
                    except Exception:
                        attendance.check_in_time = now
                else:
                    attendance.check_in_time = now
                if check_out:
                    try:
                        attendance.check_out_time = parse_datetime_with_timezone(
                            check_out)
                    except ValidationError as ve:
                        return jsonify({'message': 'Formato de check_out_time inválido', 'error': str(ve)}), 400
                    except Exception:
                        attendance.check_out_time = now
                else:
                    attendance.check_out_time = now
                # Asegurar que la nueva asistencia se persiste
                db.session.add(attendance)
            else:
                attendance = Attendance()
                attendance.student_id = student_id
                attendance.activity_id = activity_id
                attendance.check_in_time = None
                attendance.check_out_time = None
                attendance.status = 'Parcial' if check_in and not check_out else 'Ausente'
                if check_in:
                    try:
                        attendance.check_in_time = parse_datetime_with_timezone(
                            check_in)
                    except ValidationError as ve:
                        return jsonify({'message': 'Formato de check_in_time inválido', 'error': str(ve)}), 400
                    except Exception:
                        attendance.check_in_time = now
                if check_out:
                    try:
                        attendance.check_out_time = parse_datetime_with_timezone(
                            check_out)
                    except ValidationError as ve:
                        return jsonify({'message': 'Formato de check_out_time inválido', 'error': str(ve)}), 400
                    except Exception:
                        attendance.check_out_time = now
                db.session.add(attendance)

        if mark_present:
            registration = Registration.query.filter_by(
                student_id=student_id, activity_id=activity_id).first()
            if registration:
                registration.attended = True
                registration.status = 'Asistió'
                registration.confirmation_date = db.func.now()
                db.session.add(registration)

        # Flush to ensure generated fields (id, timestamps) are populated, then commit
        try:
            db.session.flush()
        except Exception:
            # flush may fail in some DB backends; fallback to commit directly
            pass

        db.session.commit()

        try:
            db.session.refresh(attendance)
        except Exception:
            # If refresh fails (detached), ignore; serializer can still read fields
            pass

        status_code = 201 if created else 200
        message = 'Asistencia creada' if created else 'Asistencia actualizada'
        return jsonify({'message': message, 'attendance': attendance_schema.dump(attendance)}), status_code

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error al registrar asistencia', 'error': str(e)}), 500
