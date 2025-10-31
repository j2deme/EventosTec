# app/utils/auth_helpers.py
from flask_jwt_extended import get_jwt_identity
from app.models.user import User
from app.models.student import Student
from flask import jsonify
from app import db


def get_current_user():
    """Obtener el usuario actual basado en el token JWT"""
    try:
        user_id = int(get_jwt_identity())

        # Buscar en User (administradores)
        user = db.session.get(User, user_id)
        if user:
            return user, "admin"

        # Buscar en Student (estudiantes)
        student = db.session.get(Student, user_id)
        if student:
            return student, "student"

        return None, None
    except (ValueError, TypeError):
        return None, None


def require_admin(func):
    """Decorador para requerir rol de administrador"""
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        user, user_type = get_current_user()

        if not user:
            return jsonify({"message": "Usuario no encontrado"}), 404

        if user_type != "admin":
            return jsonify(
                {"message": "Acceso denegado. Se requiere rol de administrador."}
            ), 403

        return func(*args, **kwargs)

    return wrapper


def require_student(func):
    """Decorador para requerir rol de estudiante"""
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        user, user_type = get_current_user()

        if not user:
            return jsonify({"message": "Usuario no encontrado"}), 404

        if user_type != "student":
            return jsonify(
                {"message": "Acceso denegado. Se requiere rol de estudiante."}
            ), 403

        return func(*args, **kwargs)

    return wrapper


def get_user_or_403():
    """Obtener usuario actual o retornar error 403"""
    user, user_type = get_current_user()

    if not user:
        return None, None, (jsonify({"message": "Usuario no encontrado"}), 404)

    return user, user_type, None
