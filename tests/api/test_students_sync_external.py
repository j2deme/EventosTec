"""Tests para POST /api/students/sync-external (upsert desde sistema externo)."""

import requests
from flask_jwt_extended import create_access_token

from app.models.student import Student


def test_sync_external_requires_auth(client):
    """Sin token la sincronización responde 401."""
    response = client.post("/api/students/sync-external", json={})

    assert response.status_code == 401


def test_sync_external_requires_admin(client, app, sample_data):
    """Un estudiante autenticado no puede sincronizar (403)."""
    with app.app_context():
        token = create_access_token(identity=str(sample_data["student_id"]))

    response = client.post(
        "/api/students/sync-external",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_sync_external_creates_updates_and_skips(
    client, app, auth_headers, sample_data, mocker
):
    """Crea nuevos, actualiza existentes y omite registros sin número de control."""
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {
            "username": "20249999",
            "nombre": "Nuevo Estudiante",
            "carrera": "ISC",
            "email": "nuevo@example.com",
        },
        {
            "control_number": "12345678",
            "nombre": "Juan Pérez Actualizado",
            "carrera": "Mecatrónica",
            "email": "juan@example.com",
        },
        {"nombre": "Registro sin control"},
    ]
    mocker.patch("requests.get", return_value=mock_response)

    response = client.post("/api/students/sync-external", json={}, headers=auth_headers)

    assert response.status_code == 200
    data = response.get_json()
    assert data["created"] == 1
    assert data["updated"] == 1
    assert data["skipped"] == 1
    assert data["total_received"] == 3

    with app.app_context():
        nuevo = Student.query.filter_by(control_number="20249999").first()
        assert nuevo is not None
        assert nuevo.full_name == "Nuevo Estudiante"

        actualizado = Student.query.filter_by(control_number="12345678").first()
        assert actualizado is not None
        assert actualizado.full_name == "Juan Pérez Actualizado"
        assert actualizado.career == "Mecatrónica"


def test_sync_external_follows_pagination(
    client, app, auth_headers, sample_data, mocker
):
    """Soporta envolvente paginada estilo Laravel (next_page_url)."""
    page1 = mocker.Mock()
    page1.status_code = 200
    page1.json.return_value = {
        "data": [
            {
                "username": "20241111",
                "nombre": "Página Uno",
                "carrera": "ISC",
                "email": "",
            }
        ],
        "next_page_url": "http://apps.tecvalles.mx:8091/api/estudiantes?page=2",
    }
    page2 = mocker.Mock()
    page2.status_code = 200
    page2.json.return_value = {
        "data": [
            {
                "username": "20242222",
                "nombre": "Página Dos",
                "carrera": "ISC",
                "email": "",
            }
        ],
        "next_page_url": None,
    }
    mocker.patch("requests.get", side_effect=[page1, page2])

    response = client.post("/api/students/sync-external", json={}, headers=auth_headers)

    assert response.status_code == 200
    data = response.get_json()
    assert data["created"] == 2
    assert data["total_received"] == 2

    with app.app_context():
        assert Student.query.filter_by(control_number="20241111").first() is not None
        assert Student.query.filter_by(control_number="20242222").first() is not None


def test_sync_external_connection_error_returns_503(client, auth_headers, mocker):
    """Errores de red contra el servicio externo responden 503."""
    mocker.patch(
        "requests.get", side_effect=requests.exceptions.ConnectionError("down")
    )

    response = client.post("/api/students/sync-external", json={}, headers=auth_headers)

    assert response.status_code == 503


def test_sync_external_http_error_returns_503(client, auth_headers, mocker):
    """Respuesta HTTP distinta de 200 desde el servicio externo responde 503."""
    mock_response = mocker.Mock()
    mock_response.status_code = 500
    mocker.patch("requests.get", return_value=mock_response)

    response = client.post("/api/students/sync-external", json={}, headers=auth_headers)

    assert response.status_code == 503
