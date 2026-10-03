from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from datetime import datetime, timezone
import requests
from app import db
from app.schemas import user_login_schema
from app.models.user import User
from app.models.student import Student
from app.models.revoked_token import RevokedToken
from app.services.password_recovery_service import request_recovery

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# Login para administradores


@auth_bp.route("/login", methods=["POST"])
def login():
    try:
        # Validar datos de entrada
        payload = request.get_json() or {}
        data = user_login_schema.load(payload)

        # Comprobar que el payload tenga los campos esperados
        username = data.get("username") if isinstance(data, dict) else None
        password = data.get("password") if isinstance(data, dict) else None
        if not username or not password:
            return jsonify({"message": "username y password son requeridos"}), 400

        # Buscar usuario administrador
        user = User.query.filter_by(username=username, is_active=True).first()

        # Validar contraseña
        if user and user.check_password(password):
            # Generar token JWT (claim 'type' desambigua User vs Student en
            # get_current_user; ver app/utils/auth_helpers.py)
            access_token = create_access_token(
                identity=str(user.id), additional_claims={"type": "admin"}
            )
            return jsonify(
                {
                    "access_token": access_token,
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "role": user.role,
                        "type": "admin",
                    },
                }
            ), 200

        return jsonify({"message": "Credenciales inválidas"}), 401

    except Exception as e:
        current_app.logger.exception("Error in /api/auth/login")
        return jsonify({"message": "Error en el login", "error": str(e)}), 400


# Login para estudiantes (validación contra sistema externo)


@auth_bp.route("/student-login", methods=["POST"])
def student_login():
    try:
        data = request.get_json() or {}
        control_number = data.get("control_number")
        password = data.get("password")

        if not control_number or not password:
            return jsonify(
                {"message": "Número de control y contraseña son requeridos"}
            ), 400

        external_api_url = "http://apps.tecvalles.mx:8091/api/validate/student"

        try:
            # Enviar credenciales al sistema externo
            external_response = requests.post(
                external_api_url,
                json={
                    "username": control_number,  # Asumiendo que username es el número de control
                    "password": password,
                },
                timeout=10,
            )

            if external_response.status_code == 200:
                external_data = external_response.json()

                # Verificar que la respuesta sea exitosa
                if external_data.get("success") and external_data.get("data"):
                    student_info = external_data["data"]

                    # Crear o actualizar estudiante en nuestra base de datos
                    student = Student.query.filter_by(
                        control_number=control_number
                    ).first()

                    if not student:
                        # Crear nuevo estudiante con todos los datos disponibles
                        # Usar asignaciones explícitas para evitar constructor kwargs
                        student = Student()
                        student.control_number = control_number
                        student.full_name = student_info.get("name", "") or ""
                        student.career = (
                            student_info.get("career", {}).get("name", "")
                            if student_info.get("career")
                            else ""
                        )
                        student.email = student_info.get("email", "") or ""
                        db.session.add(student)
                    else:
                        # Actualizar información si es necesario
                        student.full_name = student_info.get("name", student.full_name)
                        if student_info.get("career"):
                            student.career = student_info["career"].get(
                                "name", student.career
                            )
                        student.email = student_info.get("email", student.email)

                    db.session.commit()

                    # Generar token para estudiante (claim 'type' para
                    # desambiguar frente a User en get_current_user)
                    access_token = create_access_token(
                        identity=str(student.id), additional_claims={"type": "student"}
                    )
                    return jsonify(
                        {
                            "access_token": access_token,
                            "student": {
                                "id": student.id,
                                "control_number": student.control_number,
                                "full_name": student.full_name,
                                "career": student.career,
                                "email": student.email,
                                "type": "student",
                            },
                        }
                    ), 200
                else:
                    return jsonify({"message": "Credenciales inválidas"}), 401
            else:
                # Manejar diferentes códigos de error del sistema externo
                if external_response.status_code == 401:
                    return jsonify({"message": "Credenciales inválidas"}), 401
                else:
                    return jsonify(
                        {"message": "Error en la validación con sistema externo"}
                    ), 503

        except requests.exceptions.RequestException as e:
            return jsonify(
                {"message": "Error de conexión con sistema externo", "error": str(e)}
            ), 503
        except Exception as e:
            db.session.rollback()
            current_app.logger.exception("Error in /api/auth/student-login")
            return jsonify(
                {"message": "Error en el login de estudiante", "error": str(e)}
            ), 400

    except Exception as e:
        current_app.logger.exception("Unhandled error in /api/auth/student-login outer")
        return jsonify(
            {"message": "Error en el login de estudiante", "error": str(e)}
        ), 400


# Solicitud de recuperación de contraseña (fuente de verdad: plataforma MAB)


def _client_ip() -> str:
    """IP del visitante, considerando proxies inversos si reportan X-Forwarded-For."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        # Primera IP de la cadena: la que agregó el proxy más cercano.
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    """Pide enviar por correo el enlace de recuperación de un estudiante.

    Body: ``{ "control_number": "25690999" }``.

    Proxy del ``POST /api/password/forgot`` de la plataforma MAB (8091), que es
    la fuente de verdad de las credenciales de los estudiantes. Respuestas:
    200 (mensaje genérico, no revela si el número existe), 400 (datos
    inválidos), 429 (rate-limit local o de 8091) y 503 (8091 no disponible).
    """
    try:
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            payload = {}
        status, body = request_recovery(payload.get("control_number"), _client_ip())
        return jsonify(body), status
    except Exception:
        current_app.logger.exception("Error in /api/auth/forgot-password")
        return jsonify({"message": "Error al solicitar la recuperación"}), 500


# Perfil del usuario actual


@auth_bp.route("/profile", methods=["GET"])
@jwt_required()
def profile():
    try:
        user_id = int(get_jwt_identity())

        user_type = request.args.get("type")

        if user_type == "student":
            # Buscar específicamente en Student
            student = db.session.get(Student, user_id)
            if student:
                return jsonify(
                    {"student": {**student.to_dict(), "type": "student"}}
                ), 200
            else:
                return jsonify({"message": "Estudiante no encontrado"}), 404

        else:
            # Buscar específicamente en User
            user = db.session.get(User, user_id)
            if user:
                return jsonify({"user": {**user.to_dict(), "type": "admin"}}), 200
            else:
                return jsonify({"message": "Administrador no encontrado"}), 404

    except Exception as e:
        return jsonify({"message": "Error al obtener perfil", "error": str(e)}), 400


# Logout


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    """Revoca el token actual registrando su `jti` en la blocklist.

    Cualquier request posterior con este mismo token responde 401 hasta que
    venza; las filas de tokens ya vencidos se purgan oportunamente.
    """
    try:
        jwt_data = get_jwt()
        jti = jwt_data.get("jti")
        exp = jwt_data.get("exp")

        if jti and not RevokedToken.query.filter_by(jti=jti).first():
            expires_at = (
                datetime.fromtimestamp(exp, tz=timezone.utc).replace(tzinfo=None)
                if exp
                else datetime.now(timezone.utc).replace(tzinfo=None)
            )
            db.session.add(RevokedToken(jti=jti, expires_at=expires_at))

        # Purga oportunista: un token vencido ya es inválido por `exp`, su fila
        # en la blocklist deja de aportar y solo crecería la tabla.
        RevokedToken.query.filter(
            RevokedToken.expires_at < datetime.now(timezone.utc).replace(tzinfo=None)
        ).delete(synchronize_session=False)

        db.session.commit()
        return jsonify({"message": "Sesión cerrada correctamente"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Error al cerrar sesión", "error": str(e)}), 500
