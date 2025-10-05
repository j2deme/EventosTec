from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
import requests
from app import db
from app.schemas import student_schema, students_schema
from app.models.student import Student
from app.utils.auth_helpers import require_admin

students_bp = Blueprint('students', __name__, url_prefix='/api/students')


@students_bp.route('/search', methods=['GET'])
def search_students():
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return jsonify([])
    results = Student.query.filter(
        Student.full_name.ilike(f'%{q}%')).limit(10).all()
    return jsonify([
        {'id': s.id, 'full_name': s.full_name, 'control_number': s.control_number}
        for s in results
    ])

# Listar estudiantes (con búsqueda)


@students_bp.route('/', methods=['GET'])
def get_students():
    try:
        # Parámetros de búsqueda y paginación
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        search = request.args.get('search', '')
        
        # Nuevos filtros
        event_id = request.args.get('event_id', type=int)
        activity_id = request.args.get('activity_id', type=int)
        career = request.args.get('career', '')

        query = Student.query

        # Filtro por evento o actividad (require joins)
        if event_id or activity_id:
            from app.models.registration import Registration
            from app.models.activity import Activity
            
            query = query.join(Registration, Registration.student_id == Student.id)
            query = query.join(Activity, Activity.id == Registration.activity_id)
            
            if event_id:
                query = query.filter(Activity.event_id == event_id)
            
            if activity_id:
                query = query.filter(Activity.id == activity_id)
            
            # Eliminar duplicados cuando hay joins
            query = query.distinct()

        # Filtro por carrera
        if career:
            query = query.filter(Student.career.ilike(f"%{career}%"))

        # Búsqueda general
        if search:
            search_filter = f"%{search}%"
            query = query.filter(
                db.or_(
                    Student.control_number.ilike(search_filter),
                    Student.full_name.ilike(search_filter),
                    Student.career.ilike(search_filter)
                )
            )

        # Ordenar por nombre
        query = query.order_by(Student.full_name)

        students = query.paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify({
            'students': students_schema.dump(students.items),
            'total': students.total,
            'pages': students.pages,
            'current_page': page
        }), 200

    except Exception as e:
        return jsonify({'message': 'Error al obtener estudiantes', 'error': str(e)}), 500

# Obtener estudiante por ID


@students_bp.route('/<int:student_id>', methods=['GET'])
def get_student(student_id):
    try:
        student = db.session.get(Student, student_id)
        if not student:
            return jsonify({'message': 'Estudiante no encontrado'}), 404

        return jsonify({'student': student_schema.dump(student)}), 200

    except Exception as e:
        return jsonify({'message': 'Error al obtener estudiante', 'error': str(e)}), 500

# Buscar estudiante en sistema externo


@students_bp.route('/external-search', methods=['GET'])
@jwt_required()
def search_external_student():
    try:
        control_number = request.args.get('control_number')
        if not control_number:
            return jsonify({'message': 'Número de control es requerido'}), 400

        # Consultar sistema externo
        external_api_url = f"http://apps.tecvalles.mx:8091/api/estudiantes?search={control_number}"

        try:
            response = requests.get(external_api_url, timeout=10)
            if response.status_code == 200:
                return jsonify({'student': response.json()}), 200
            else:
                return jsonify({'message': 'Estudiante no encontrado en sistema externo'}), 404
        except requests.exceptions.RequestException:
            return jsonify({'message': 'Error de conexión con sistema externo'}), 503

    except Exception as e:
        return jsonify({'message': 'Error en búsqueda externa', 'error': str(e)}), 500

# Importar estudiante desde sistema externo


@students_bp.route('/import-external/<control_number>', methods=['POST'])
@jwt_required()
@require_admin
def import_external_student(control_number):
    try:
        # Consultar sistema externo
        external_api_url = f"http://apps.tecvalles.mx:8091/api/estudiantes?search={control_number}"

        try:
            response = requests.get(external_api_url, timeout=10)
            if response.status_code == 200:
                external_data = response.json()

                if external_data and len(external_data) > 0:
                    student_info = external_data[0]

                    # Verificar si ya existe
                    student = Student.query.filter_by(
                        control_number=control_number).first()
                    if not student:
                        # Crear nuevo estudiante
                        student = Student()
                        student.control_number = control_number
                        student.full_name = student_info.get('nombre', '')
                        student.career = student_info.get('carrera', '')
                        student.email = student_info.get('email', '')
                        db.session.add(student)
                        db.session.commit()

                        return jsonify({
                            'message': 'Estudiante importado exitosamente',
                            'student': student_schema.dump(student)
                        }), 201
                    else:
                        return jsonify({
                            'message': 'Estudiante ya existe en el sistema',
                            'student': student_schema.dump(student)
                        }), 200
                else:
                    return jsonify({'message': 'Estudiante no encontrado en sistema externo'}), 404
            else:
                return jsonify({'message': 'Error al consultar sistema externo'}), 503
        except requests.exceptions.RequestException:
            return jsonify({'message': 'Error de conexión con sistema externo'}), 503

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error al importar estudiante', 'error': str(e)}), 500


# Endpoint proxy para validación externa usada por el modal de Walk-in (no requiere auth)
@students_bp.route('/validate', methods=['GET'])
def validate_student_proxy():
    """Proxy público que consulta el servicio externo de validación de estudiantes.

    Query params:
      - control_number (or username)

    Returns standardized JSON: { student: { control_number, full_name, career, email } }
    or 404 if not found, 503 on external errors.
    """
    control = request.args.get(
        'control_number') or request.args.get('username')
    if not control:
        return jsonify({'message': 'control_number es requerido'}), 400

    external_api = f"http://apps.tecvalles.mx:8091/api/validate/student?username={control}"
    try:
        resp = requests.get(external_api, timeout=8)
    except requests.exceptions.RequestException:
        return jsonify({'message': 'Error conectando al servicio externo'}), 503

    if resp.status_code == 200:
        try:
            data = resp.json()
        except Exception:
            return jsonify({'message': 'Respuesta externa inválida'}), 502

        if not isinstance(data, dict):
            return jsonify({'message': 'Respuesta externa inválida'}), 502

        # Some external services wrap payload in { success: true, data: { ... } }
        if isinstance(data, dict) and 'data' in data and isinstance(data.get('data'), dict):
            data = data.get('data')

        # Work with a local dict reference to satisfy static analysis
        d = data if isinstance(data, dict) else {}

        # Normalize keys if possible; career may be an object
        career = d.get('career') or d.get('carrera') or {}
        career_name = None
        if isinstance(career, dict):
            career_name = career.get('name') or career.get('nombre') or None
        else:
            career_name = career

        student = {
            'control_number': d.get('username') or d.get('control_number') or control,
            'full_name': d.get('name') or d.get('full_name') or d.get('nombre'),
            'career': career_name,
            'email': d.get('email') or ''
        }
        return jsonify({'student': student}), 200
    elif resp.status_code == 404:
        return jsonify({'message': 'Estudiante no encontrado'}), 404
    else:
        return jsonify({'message': 'Error desde servicio externo'}), 503

# Obtener actividades de un estudiante


@students_bp.route('/<int:student_id>/activities', methods=['GET'])
def get_student_activities(student_id):
    try:
        student = db.session.get(Student, student_id)
        if not student:
            return jsonify({'message': 'Estudiante no encontrado'}), 404

        # Obtener actividades a través de asistencias y preregistros
        from app.models.attendance import Attendance
        from app.models.registration import Registration
        from app.models.activity import Activity

        # Actividades con asistencia
        attendance_activities = Activity.query.join(Attendance).filter(
            Attendance.student_id == student_id
        ).all()

        # Actividades con preregistro
        registration_activities = Activity.query.join(Registration).filter(
            Registration.student_id == student_id
        ).all()

        # Combinar y eliminar duplicados
        all_activities = list(
            set(attendance_activities + registration_activities))

        from app.schemas import activities_schema
        return jsonify({
            'activities': activities_schema.dump(all_activities)
        }), 200

    except Exception as e:
        return jsonify({'message': 'Error al obtener actividades del estudiante', 'error': str(e)}), 500


# Obtener horas acumuladas por evento de un estudiante
@students_bp.route('/<int:student_id>/hours-by-event', methods=['GET'])
def get_student_hours_by_event(student_id):
    """
    Calcula las horas confirmadas de un estudiante agrupadas por evento.
    Solo cuenta registros con status='Asistió'.
    """
    try:
        student = db.session.get(Student, student_id)
        if not student:
            return jsonify({'message': 'Estudiante no encontrado'}), 404

        from app.models.registration import Registration
        from app.models.activity import Activity
        from app.models.event import Event
        from sqlalchemy import func

        # Query: agrupar por evento, sumar horas de actividades donde status='Asistió'
        results = db.session.query(
            Event.id.label('event_id'),
            Event.name.label('event_name'),
            Event.start_date.label('event_start_date'),
            Event.end_date.label('event_end_date'),
            func.sum(Activity.duration_hours).label('total_hours'),
            func.count(Activity.id).label('activities_count')
        ).join(
            Activity, Activity.event_id == Event.id
        ).join(
            Registration, Registration.activity_id == Activity.id
        ).filter(
            Registration.student_id == student_id,
            Registration.status == 'Asistió'
        ).group_by(
            Event.id, Event.name, Event.start_date, Event.end_date
        ).order_by(
            Event.start_date.desc()
        ).all()

        events_hours = []
        for row in results:
            total_hours = float(row.total_hours or 0)
            has_credit = total_hours >= 10.0
            
            events_hours.append({
                'event_id': row.event_id,
                'event_name': row.event_name,
                'event_start_date': row.event_start_date.isoformat() if row.event_start_date else None,
                'event_end_date': row.event_end_date.isoformat() if row.event_end_date else None,
                'total_hours': total_hours,
                'activities_count': row.activities_count,
                'has_complementary_credit': has_credit
            })

        return jsonify({
            'student': student_schema.dump(student),
            'events_hours': events_hours
        }), 200

    except Exception as e:
        return jsonify({'message': 'Error al calcular horas por evento', 'error': str(e)}), 500


# Obtener detalle de participación de un estudiante en un evento específico
@students_bp.route('/<int:student_id>/event/<int:event_id>/details', methods=['GET'])
def get_student_event_details(student_id, event_id):
    """
    Obtiene el detalle cronológico de participación del estudiante en un evento.
    Incluye todas las actividades registradas y su status.
    """
    try:
        student = db.session.get(Student, student_id)
        if not student:
            return jsonify({'message': 'Estudiante no encontrado'}), 404

        from app.models.event import Event
        event = db.session.get(Event, event_id)
        if not event:
            return jsonify({'message': 'Evento no encontrado'}), 404

        from app.models.registration import Registration
        from app.models.activity import Activity

        # Obtener todas las registraciones del estudiante para este evento
        registrations = db.session.query(Registration).join(
            Activity, Activity.id == Registration.activity_id
        ).filter(
            Registration.student_id == student_id,
            Activity.event_id == event_id
        ).order_by(
            Activity.start_datetime.asc()
        ).all()

        activities_detail = []
        total_confirmed_hours = 0.0

        for reg in registrations:
            activity = reg.activity
            hours = float(activity.duration_hours or 0)
            
            if reg.status == 'Asistió':
                total_confirmed_hours += hours

            activities_detail.append({
                'registration_id': reg.id,
                'activity_id': activity.id,
                'activity_name': activity.name,
                'activity_type': activity.activity_type,
                'start_datetime': activity.start_datetime.isoformat() if activity.start_datetime else None,
                'end_datetime': activity.end_datetime.isoformat() if activity.end_datetime else None,
                'duration_hours': hours,
                'location': activity.location,
                'status': reg.status,
                'registration_date': reg.registration_date.isoformat() if reg.registration_date else None,
                'confirmation_date': reg.confirmation_date.isoformat() if reg.confirmation_date else None,
            })

        has_credit = total_confirmed_hours >= 10.0

        return jsonify({
            'student': student_schema.dump(student),
            'event': {
                'id': event.id,
                'name': event.name,
                'start_date': event.start_date.isoformat() if event.start_date else None,
                'end_date': event.end_date.isoformat() if event.end_date else None,
            },
            'total_confirmed_hours': total_confirmed_hours,
            'has_complementary_credit': has_credit,
            'activities': activities_detail
        }), 200

    except Exception as e:
        return jsonify({'message': 'Error al obtener detalle del evento', 'error': str(e)}), 500
