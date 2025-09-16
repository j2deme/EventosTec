from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
import requests
from app import db
from app.schemas import user_login_schema
from app.models.user import User
from app.models.student import Student

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# Login para administradores


@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        # Validar datos de entrada
        payload = request.get_json() or {}
        data = user_login_schema.load(payload)

        # Comprobar que el payload tenga los campos esperados
        username = data.get('username') if isinstance(data, dict) else None
        password = data.get('password') if isinstance(data, dict) else None
        if not username or not password:
            return jsonify({'message': 'username y password son requeridos'}), 400

        # Buscar usuario administrador
        user = User.query.filter_by(username=username, is_active=True).first()

        # Validar contraseña
        if user and user.check_password(password):
            # Generar token JWT
            access_token = create_access_token(identity=str(user.id))
            return jsonify({
                'access_token': access_token,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.role,
                    'type': 'admin'
                }
            }), 200

        return jsonify({'message': 'Credenciales inválidas'}), 401

    except Exception as e:
        return jsonify({'message': 'Error en el login', 'error': str(e)}), 400

# Login para estudiantes (validación contra sistema externo)


@auth_bp.route('/student-login', methods=['POST'])
def student_login():
    try:
        data = request.get_json() or {}
        control_number = data.get('control_number')
        password = data.get('password')

        if not control_number or not password:
            return jsonify({'message': 'Número de control y contraseña son requeridos'}), 400

        external_api_url = "http://apps.tecvalles.mx:8091/api/validate/student"

        try:
            # Enviar credenciales al sistema externo
            external_response = requests.post(
                external_api_url,
                json={
                    'username': control_number,  # Asumiendo que username es el número de control
                    'password': password
                },
                timeout=10
            )

            if external_response.status_code == 200:
                external_data = external_response.json()

                # Verificar que la respuesta sea exitosa
                if external_data.get('success') and external_data.get('data'):
                    student_info = external_data['data']

                    # Crear o actualizar estudiante en nuestra base de datos
                    student = Student.query.filter_by(
                        control_number=control_number).first()

                    if not student:
                        # Crear nuevo estudiante con todos los datos disponibles
                        # Usar asignaciones explícitas para evitar constructor kwargs
                        student = Student()
                        student.control_number = control_number
                        student.full_name = student_info.get('name', '') or ''
                        student.career = student_info.get('career', {}).get(
                            'name', '') if student_info.get('career') else ''
                        student.email = student_info.get('email', '') or ''
                        db.session.add(student)
                    else:
                        # Actualizar información si es necesario
                        student.full_name = student_info.get(
                            'name', student.full_name)
                        if student_info.get('career'):
                            student.career = student_info['career'].get(
                                'name', student.career)
                        student.email = student_info.get(
                            'email', student.email)

                    db.session.commit()

                    # Generar token para estudiante
                    access_token = create_access_token(
                        identity=str(student.id))
                    return jsonify({
                        'access_token': access_token,
                        'student': {
                            'id': student.id,
                            'control_number': student.control_number,
                            'full_name': student.full_name,
                            'career': student.career,
                            'email': student.email,
                            'type': 'student'
                        }
                    }), 200
                else:
                    return jsonify({'message': 'Credenciales inválidas'}), 401
            else:
                # Manejar diferentes códigos de error del sistema externo
                if external_response.status_code == 401:
                    return jsonify({'message': 'Credenciales inválidas'}), 401
                else:
                    return jsonify({'message': 'Error en la validación con sistema externo'}), 503

        except requests.exceptions.RequestException as e:
            return jsonify({'message': 'Error de conexión con sistema externo', 'error': str(e)}), 503
        except Exception as e:
            db.session.rollback()
            return jsonify({'message': 'Error en el login de estudiante', 'error': str(e)}), 400

    except Exception as e:
        return jsonify({'message': 'Error en el login de estudiante', 'error': str(e)}), 400

# Perfil del usuario actual


@auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def profile():
    try:
        user_id = int(get_jwt_identity())

        user_type = request.args.get('type')

        if user_type == 'student':
            # Buscar específicamente en Student
            student = db.session.get(Student, user_id)
            if student:
                return jsonify({
                    'student': {
                        **student.to_dict(),
                        'type': 'student'
                    }
                }), 200
            else:
                return jsonify({'message': 'Estudiante no encontrado'}), 404

        else:
            # Buscar específicamente en User
            user = db.session.get(User, user_id)
            if user:
                return jsonify({
                    'user': {
                        **user.to_dict(),
                        'type': 'admin'
                    }
                }), 200
            else:
                return jsonify({'message': 'Administrador no encontrado'}), 404

    except Exception as e:
        return jsonify({'message': 'Error al obtener perfil', 'error': str(e)}), 400

# Logout


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    # En JWT el logout es del lado del cliente (eliminar token)
    return jsonify({'message': 'Sesión cerrada correctamente'}), 200
