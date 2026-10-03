"""Tests para POST /api/auth/change-password (cambio de contraseña de admin)."""

import pytest
from flask_jwt_extended import create_access_token

from app import db
from app.api.auth_bp import reset_change_password_limits
from app.models.user import User

CURRENT_PASSWORD = "CurrentPass123"
NEW_PASSWORD = "NuevaClave456"


@pytest.fixture(autouse=True)
def _reset_limits():
    """Cada test empieza con el rate-limit de cambio de contraseña limpio."""
    reset_change_password_limits()
    yield
    reset_change_password_limits()


@pytest.fixture
def admin(app):
    """Admin de prueba con headers JWT y sus credenciales reales."""
    with app.app_context():
        user = User()
        user.username = "cp_admin"
        user.email = "cp_admin@test.com"
        user.role = "Admin"
        user.set_password(CURRENT_PASSWORD)
        db.session.add(user)
        db.session.commit()
        user_id = user.id

        token = create_access_token(
            identity=str(user.id), additional_claims={"type": "admin"}
        )

    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "username": "cp_admin",
        "user_id": user_id,
    }


def _payload(**overrides):
    body = {
        "current_password": CURRENT_PASSWORD,
        "new_password": NEW_PASSWORD,
        "confirm_password": NEW_PASSWORD,
    }
    body.update(overrides)
    return body


def test_change_password_requires_auth(client, admin):
    response = client.post("/api/auth/change-password", json=_payload())

    assert response.status_code == 401


def test_change_password_forbidden_for_student(client, app, sample_data):
    """Un estudiante autenticado no puede usarlo (403)."""
    with app.app_context():
        token = create_access_token(
            identity=str(sample_data["student_id"]),
            additional_claims={"type": "student"},
        )

    response = client.post(
        "/api/auth/change-password",
        json=_payload(),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_change_password_requires_all_fields(client, admin):
    response = client.post(
        "/api/auth/change-password",
        json={"current_password": CURRENT_PASSWORD, "new_password": NEW_PASSWORD},
        headers=admin["headers"],
    )

    assert response.status_code == 400
    assert response.get_json()["message"] == "Los tres campos son requeridos"


def test_change_password_rejects_non_json_payload(client, admin):
    """Un body que no es objeto JSON no debe reventar (400, no 500)."""
    response = client.post(
        "/api/auth/change-password",
        data='["no es un objeto"]',
        content_type="application/json",
        headers=admin["headers"],
    )

    assert response.status_code == 400


def test_change_password_wrong_current_is_400_not_401(client, admin):
    """Contraseña actual incorrecta -> 400.

    Nunca 401: el interceptor global de fetch (app.js) cierra la sesión y
    redirige al login ante cualquier 401, y aquí la sesión sigue siendo válida.
    """
    response = client.post(
        "/api/auth/change-password",
        json=_payload(current_password="otra-clave"),
        headers=admin["headers"],
    )

    assert response.status_code == 400
    assert response.status_code != 401
    assert response.get_json()["message"] == "La contraseña actual es incorrecta."


def test_change_password_rejects_short_new_password(client, admin):
    response = client.post(
        "/api/auth/change-password",
        json=_payload(new_password="corta", confirm_password="corta"),
        headers=admin["headers"],
    )

    assert response.status_code == 400
    assert "8 caracteres" in response.get_json()["message"]


def test_change_password_rejects_mismatched_confirmation(client, admin):
    response = client.post(
        "/api/auth/change-password",
        json=_payload(new_password=NEW_PASSWORD, confirm_password="Distinta456"),
        headers=admin["headers"],
    )

    assert response.status_code == 400
    assert "confirmación" in response.get_json()["message"]


def test_change_password_rejects_same_password(client, admin):
    response = client.post(
        "/api/auth/change-password",
        json=_payload(new_password=CURRENT_PASSWORD, confirm_password=CURRENT_PASSWORD),
        headers=admin["headers"],
    )

    assert response.status_code == 400
    assert "distinta" in response.get_json()["message"]


def test_change_password_success_updates_hash(client, admin):
    response = client.post(
        "/api/auth/change-password", json=_payload(), headers=admin["headers"]
    )

    assert response.status_code == 200
    assert response.get_json()["message"] == "Contraseña actualizada correctamente."

    user = db.session.get(User, admin["user_id"])
    assert user.check_password(NEW_PASSWORD) is True
    assert user.check_password(CURRENT_PASSWORD) is False


def test_new_password_works_for_login(client, admin):
    """Tras el cambio, la contraseña nueva autentica en /api/auth/login."""
    change = client.post(
        "/api/auth/change-password", json=_payload(), headers=admin["headers"]
    )
    assert change.status_code == 200

    login = client.post(
        "/api/auth/login",
        json={"username": admin["username"], "password": NEW_PASSWORD},
    )

    assert login.status_code == 200
    assert login.get_json()["access_token"]

    old = client.post(
        "/api/auth/login",
        json={"username": admin["username"], "password": CURRENT_PASSWORD},
    )
    assert old.status_code == 401


def test_change_password_rate_limited(client, admin):
    """El 6º intento en la ventana responde 429 (5 intentos / 15 min)."""
    responses = [
        client.post(
            "/api/auth/change-password",
            json=_payload(current_password="clave-mala"),
            headers=admin["headers"],
        )
        for _ in range(6)
    ]

    assert [r.status_code for r in responses[:5]] == [400] * 5
    assert responses[5].status_code == 429
    assert "intentos" in responses[5].get_json()["message"]

    # El usuario nunca llegó a cambiar la contraseña
    user = db.session.get(User, admin["user_id"])
    assert user.check_password(CURRENT_PASSWORD) is True
