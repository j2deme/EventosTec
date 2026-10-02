"""Tests del claim `type` en los JWT (desambiguación User vs Student).

- Tokens nuevos (login / student-login) traen `type` = "admin" | "student".
- `get_current_user()` da prioridad al claim; los tokens legacy sin claim
  conservan el orden histórico (User primero, luego Student).
- Escenario de colisión: una PK en `users` y la misma PK en `students`.
"""
import base64
import json

from app import db
from app.models.user import User
from app.models.student import Student
from flask_jwt_extended import create_access_token


def _jwt_payload(token):
    """Decodifica el payload (sin verificar) de un JWT firmado."""
    part = token.split(".")[1]
    part += "=" * (-len(part) % 4)
    return json.loads(base64.urlsafe_b64decode(part))


def _create_admin(username="claimadmin", password="pw-claim-1"):
    user = User()
    user.username = username
    user.email = f"{username}@test.com"
    user.role = "Admin"
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def _create_collision(app):
    """Crea un User y un Student que comparten la misma PK numérica."""
    with app.app_context():
        user = _create_admin()
        student = Student()
        student.control_number = "CLM001"
        student.full_name = "Estudiante Colisión"
        db.session.add(student)
        db.session.commit()
        assert user.id == student.id  # misma PK en tablas distintas
        return user.id, student.id


def test_admin_login_embeds_type_claim(client, app):
    """POST /api/auth/login emite un token con claim type=admin."""
    with app.app_context():
        _create_admin(username="loginadmin", password="secret123")

    response = client.post(
        "/api/auth/login",
        json={"username": "loginadmin", "password": "secret123"},
    )
    assert response.status_code == 200
    payload = _jwt_payload(response.get_json()["access_token"])
    assert payload["type"] == "admin"


def test_student_login_embeds_type_claim(client, app, monkeypatch):
    """POST /api/auth/student-login emite un token con claim type=student.

    El API externo se mockea: este test no hace llamadas de red.
    """

    class _FakeResp:
        status_code = 200

        def json(self):
            return {
                "success": True,
                "data": {
                    "name": "Alumna Prueba",
                    "career": {"name": "ISC"},
                    "email": "alumna@test.mx",
                },
            }

    import app.api.auth_bp as auth_bp_module

    monkeypatch.setattr(auth_bp_module.requests, "post", lambda *a, **k: _FakeResp())

    response = client.post(
        "/api/auth/student-login",
        json={"control_number": "CLM999", "password": "x"},
    )
    assert response.status_code == 200
    payload = _jwt_payload(response.get_json()["access_token"])
    assert payload["type"] == "student"


def _post_registration(client, token, student_id=999999, activity_id=999999):
    """POST /api/registrations con student_id distinto al del JWT.

    El chequeo de rol ocurre ANTES de tocar la BD:
    - resuelto como student → 403 (no puede preregistrar a otros)
    - resuelto como admin   → pasa el rol y responde 404 (ids inexistentes)
    """
    return client.post(
        "/api/registrations/",
        headers={"Authorization": f"Bearer {token}"},
        json={"student_id": student_id, "activity_id": activity_id},
    )


def test_claim_student_wins_when_ids_collide(client, app):
    """Con colisión de PKs, el claim type=student resuelve como estudiante."""
    user_id, student_id = _create_collision(app)
    with app.app_context():
        token = create_access_token(
            identity=str(student_id), additional_claims={"type": "student"}
        )

    response = _post_registration(client, token)
    assert response.status_code == 403


def test_claim_admin_resolves_user_when_ids_collide(client, app):
    """Con la misma colisión, el claim type=admin resuelve como admin (User)."""
    user_id, student_id = _create_collision(app)
    with app.app_context():
        token = create_access_token(
            identity=str(user_id), additional_claims={"type": "admin"}
        )

    response = _post_registration(client, token)
    # No 403: el rol admin pasa el chequeo y luego falla por ids inexistentes
    assert response.status_code == 404


def test_legacy_token_without_claim_keeps_user_first_order(client, app):
    """Token sin claim (emigra en ≤1 h) conserva el orden histórico: User primero."""
    user_id, student_id = _create_collision(app)
    with app.app_context():
        token = create_access_token(identity=str(user_id))  # sin claim

    response = _post_registration(client, token)
    # User id=1 existe → resuelto como admin → 404, jamás 403
    assert response.status_code == 404


def test_claim_admin_does_not_fall_through_to_student(client, app):
    """type=admin con una PK que solo existe en `students` NO cae en Student."""
    with app.app_context():
        # Sin crear ningún User: la PK del estudiante NO existe en users
        student = Student()
        student.control_number = "CLM002"
        student.full_name = "Estudiante Sin User"
        db.session.add(student)
        db.session.commit()
        solo_student_id = student.id  # existe en students, no en users

        token = create_access_token(
            identity=str(solo_student_id), additional_claims={"type": "admin"}
        )

    response = _post_registration(client, token)
    # El claim manda: no hay User con esa PK → usuario no encontrado (404),
    # no el 403 que daría si se resolviera como Student.
    assert response.status_code == 404
    assert "Usuario no encontrado" in response.get_json()["message"]
