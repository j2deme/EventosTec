from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
import requests
from app import db
from app.schemas import student_schema, students_schema
from app.models.student import Student

students_bp = Blueprint('students', __name__, url_prefix='/api/students')

# Listar estudiantes (con búsqueda)


@students_bp.route('/', methods=['GET'])
def get_students():
    try:
        # Parámetros de búsqueda y paginación
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        search = request.args.get('search', '')

        query = Student.query

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
        student = Student.query.get(student_id)
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
                        student = Student(
                            control_number=control_number,
                            full_name=student_info.get('nombre', ''),
                            career=student_info.get('carrera', ''),
                            email=student_info.get('email', '')
                        )
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

# Obtener actividades de un estudiante


@students_bp.route('/<int:student_id>/activities', methods=['GET'])
def get_student_activities(student_id):
    try:
        student = Student.query.get(student_id)
        if not student:
            return jsonify({'message': 'Estudiante no encontrado'}), 404

        # Obtener actividades a través de asistencias y preregistros
        from app.models.attendance import Attendance
        from app.models.registration import Registration
        from app.models.activity import Activity

        # Actividades con asistencia
        attendance_activities = db.session.query(Activity).join(Attendance).filter(
            Attendance.student_id == student_id
        ).all()

        # Actividades con preregistro
        registration_activities = db.session.query(Activity).join(Registration).filter(
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
