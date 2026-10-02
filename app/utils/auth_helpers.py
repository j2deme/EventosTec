# app/utils/auth_helpers.py
from flask_jwt_extended import get_jwt, get_jwt_identity
from app.models.user import User
from app.models.student import Student
from flask import jsonify
from app import db


def get_current_user():
    """Obtener el usuario actual basado en el token JWT.

    Los tokens nuevos traen el claim ``type`` ("admin"/"student"), que
    desambigua la identidad numérica: User y Student comparten espacio de
    ids (una PK 1 en `users` y otra PK 1 en `students` son distintas
    entidades), así que el orden de búsqueda por sí solo no basta.

    Los tokens emitidos antes del cambio no traen el claim y conservan el
    comportamiento histórico: se busca primero en User y, si no existe, en
    Student (backward-compatible: los tokens caducan en 1 hora).
    """
    try:
        user_id = int(get_jwt_identity())
    except (ValueError, TypeError):
        return None, None

    try:
        token_type = (get_jwt() or {}).get("type")
    except Exception:
        # Sin contexto JWT activo (u otro error de decodificación):
        # degradar al comportamiento histórico.
        token_type = None

    try:
        if token_type == "admin":
            user = db.session.get(User, user_id)
            return (user, "admin") if user else (None, None)

        if token_type == "student":
            student = db.session.get(Student, user_id)
            return (student, "student") if student else (None, None)

        # Token legacy sin claim: orden histórico (User primero).
        user = db.session.get(User, user_id)
        if user:
            return user, "admin"

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
