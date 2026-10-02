"""Tests de POST /api/admin/impersonate (Fase B2)."""
import base64
import json
import logging

from app.models.student import Student
from flask_jwt_extended import create_access_token


def _jwt_payload(token):
    """Decodifica el payload (sin verificar) de un JWT firmado."""
    part = token.split(".")[1]
    part += "=" * (-len(part) % 4)
    return json.loads(base64.urlsafe_b64decode(part))


def _create_student(db_session, control="IMP001", name="Estudiante Impersonado"):
    student = Student()
    student.control_number = control
    student.full_name = name
    student.career = "ISC"
    db_session.add(student)
    db_session.commit()
    return student


def test_impersonate_requires_auth(client):
    response = client.post("/api/admin/impersonate", json={"student_id": 1})
    assert response.status_code == 401


def test_impersonate_requires_admin(client, app, db_session):
    """Un token de estudiante no puede impersonar (403)."""
    student = _create_student(db_session)
    with app.app_context():
        token = create_access_token(
            identity=str(student.id), additional_claims={"type": "student"}
        )

    response = client.post(
        "/api/admin/impersonate",
        headers={"Authorization": f"Bearer {token}"},
        json={"student_id": student.id},
    )
    assert response.status_code == 403


def test_impersonate_missing_or_invalid_student_id(client, auth_headers):
    response = client.post(
        "/api/admin/impersonate", headers=auth_headers, json={}
    )
    assert response.status_code == 400

    response = client.post(
        "/api/admin/impersonate",
        headers=auth_headers,
        json={"student_id": "no-numerico"},
    )
    assert response.status_code == 400


def test_impersonate_unknown_student_returns_404(client, auth_headers):
    response = client.post(
        "/api/admin/impersonate",
        headers=auth_headers,
        json={"student_id": 999999},
    )
    assert response.status_code == 404


def test_impersonate_returns_token_with_expected_claims(
    client, auth_headers, app, db_session
):
    """200: token corto con claims type/imp/admin_id + datos del estudiante."""
    student = _create_student(db_session)

    response = client.post(
        "/api/admin/impersonate",
        headers=auth_headers,
        json={"student_id": student.id},
    )
    assert response.status_code == 200
    data = response.get_json()

    assert data["expires_in"] == 1800
    assert data["student"]["id"] == student.id
    assert data["student"]["full_name"] == "Estudiante Impersonado"
    assert data["student"]["type"] == "student"
    assert data["admin"]["username"] == "testadmin"

    payload = _jwt_payload(data["access_token"])
    assert payload["type"] == "student"
    assert payload["imp"] is True
    assert payload["admin_id"] is not None
    # TTL exacto: exp - iat == 1800 s
    assert payload["exp"] - payload["iat"] == 1800


def test_impersonation_is_logged(client, auth_headers, app, db_session, caplog):
    student = _create_student(db_session, control="IMPLOG")
    with caplog.at_level(logging.INFO):
        response = client.post(
            "/api/admin/impersonate",
            headers=auth_headers,
            json={"student_id": student.id},
        )
    assert response.status_code == 200
    assert any("IMPERSONATION" in record.getMessage() for record in caplog.records)


def test_impersonated_token_resolves_as_student_end_to_end(
    client, auth_headers, app, db_session
):
    """El token emitido actúa como estudiante en endpoints reales:
    - profile?type=student → 200 con sus datos
    - POST /api/registrations consigo mismo → pasa el chequeo de rol de
      estudiante (sería 403 si se resolviera como admin) y falla después
      por actividad inexistente (404)."""
    student = _create_student(db_session)

    response = client.post(
        "/api/admin/impersonate",
        headers=auth_headers,
        json={"student_id": student.id},
    )
    assert response.status_code == 200
    imp_token = response.get_json()["access_token"]
    headers = {"Authorization": f"Bearer {imp_token}"}

    # 1) perfil de estudiante
    profile = client.get("/api/auth/profile?type=student", headers=headers)
    assert profile.status_code == 200
    assert profile.get_json()["student"]["id"] == student.id

    # 2) prerregistro a sí mismo (pasa rol) → 404 por actividad inexistente
    reg = client.post(
        "/api/registrations/",
        headers=headers,
        json={"student_id": student.id, "activity_id": 999999},
    )
    assert reg.status_code == 404
    assert "Actividad no encontrada" in reg.get_json()["message"]

    # 3) prerregistro a OTRO estudiante → 403 (no puede)
    other = _create_student(db_session, control="IMPOTH", name="Otro")
    reg_other = client.post(
        "/api/registrations/",
        headers=headers,
        json={"student_id": other.id, "activity_id": 999999},
    )
    assert reg_other.status_code == 403
