from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
import requests
from app import db
from app.schemas import user_login_schema, user_schema
from app.models.user import User
from app.models.student import Student

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# Login para administradores


@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        # Validar datos de entrada
        data = user_login_schema.load(request.get_json())

        # Buscar usuario administrador
        user = db.session.query(User).filter_by(
            username=data['username'], is_active=True).first()

        # Validar contraseña
        if user and user.check_password(data['password']):
            # Generar token JWT
            access_token = create_access_token(
                identity={'id': user.id, 'type': 'admin'})
            return jsonify({
                'access_token': access_token,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.role
                }
            }), 200

        return jsonify({'message': 'Credenciales inválidas'}), 401

    except Exception as e:
        return jsonify({'message': 'Error en el login', 'error': str(e)}), 400

# Login para estudiantes (validación contra sistema externo)


@auth_bp.route('/student-login', methods=['POST'])
def student_login():
    try:
        data = request.get_json()
        control_number = data.get('control_number')
        password = data.get('password')

        if not control_number or not password:
            return jsonify({'message': 'Número de control y contraseña son requeridos'}), 400

        # Validar contra sistema externo
        external_api_url = f"http://apps.tecvalles.mx:8091/api/estudiantes?search={control_number}"

        try:
            # Primero verificar que el estudiante exista
            student_response = requests.get(external_api_url, timeout=10)
            if student_response.status_code != 200:
                return jsonify({'message': 'Error al conectar con sistema externo'}), 503

            student_data = student_response.json()

            # Aquí iría la lógica para validar la contraseña
            # Por ahora simulamos la validación (en producción conectarías con el sistema real)
            # validate_response = requests.post("http://apps.tecvalles.mx:8091/api/validate",
            #                                  json={'control_number': control_number, 'password': password})

            # Simulación: asumimos que es válido si el estudiante existe
            if student_data and len(student_data) > 0:
                # Asumimos que viene en formato array
                student_info = student_data[0]

                # Crear o actualizar estudiante en nuestra base de datos
                student = db.session.query(Student).filter_by(
                    control_number=control_number).first()
                if not student:
                    student = Student(
                        control_number=control_number,
                        full_name=student_info.get('nombre', ''),
                        career=student_info.get('carrera', ''),
                        email=student_info.get('email', '')
                    )
                    db.session.add(student)
                else:
                    # Actualizar información si es necesario
                    student.full_name = student_info.get(
                        'nombre', student.full_name)
                    student.career = student_info.get(
                        'carrera', student.career)
                    student.email = student_info.get('email', student.email)

                db.session.commit()

                # Generar token para estudiante
                access_token = create_access_token(
                    identity={'id': student.id,
                              'control_number': control_number, 'type': 'student'}
                )

                return jsonify({
                    'access_token': access_token,
                    'student': {
                        'id': student.id,
                        'control_number': student.control_number,
                        'full_name': student.full_name,
                        'career': student.career,
                        'email': student.email
                    }
                }), 200
            else:
                return jsonify({'message': 'Estudiante no encontrado'}), 404

        except requests.exceptions.RequestException:
            return jsonify({'message': 'Error de conexión con sistema externo'}), 503

    except Exception as e:
        return jsonify({'message': 'Error en el login de estudiante', 'error': str(e)}), 400

# Perfil del usuario actual


@auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def profile():
    try:
        user_id = int(get_jwt_identity())

        # Primero buscar en User (admin)
        user = db.session.get(User, user_id)
        if user:
            return jsonify({
                'user': {
                    **user.to_dict(),
                    'type': 'admin'
                }
            }), 200

        # Si no es admin, buscar en Student
        student = db.session.get(Student, user_id)
        if student:
            return jsonify({
                'student': {
                    **student.to_dict(),
                    'type': 'student'
                }
            }), 200

        return jsonify({'message': 'Usuario no encontrado'}), 404

        elif current_user['type'] == 'student':
            student = Student.query.get(current_user['id'])
            if student:
                return jsonify({'student': student.to_dict()}), 200
            else:
                return jsonify({'message': 'Estudiante no encontrado'}), 404

        return jsonify({'message': 'Tipo de usuario no válido'}), 400

    except Exception as e:
        return jsonify({'message': 'Error al obtener perfil', 'error': str(e)}), 400

# Logout


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    # En JWT el logout es del lado del cliente (eliminar token)
    # Aquí podrías implementar blacklisting si es necesario
    return jsonify({'message': 'Sesión cerrada correctamente'}), 200
