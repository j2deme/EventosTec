import json


def test_create_activity(client, auth_headers, sample_data):
    activity_data = {
        "event_id": sample_data["event_id"],
        "department": "ISC",
        "name": "Conferencia de prueba",
        "description": "Descripción",
        "start_datetime": "2024-01-01T10:00:00-06:00",
        "end_datetime": "2024-01-01T11:00:00-06:00",
        "duration_hours": 1.0,
        "activity_type": "Conferencia",
        "location": "Auditorio A",
        "modality": "Presencial",
        "max_capacity": 50,
    }

    response = client.post("/api/activities/", headers=auth_headers, json=activity_data)

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["activity"]["name"] == "Conferencia de prueba"


def test_create_activity_invalid_event(client, auth_headers):
    activity_data = {
        "event_id": 99999,
        "department": "ISC",
        "name": "Conferencia de prueba",
        "start_datetime": "2024-01-01T10:00:00",
        "end_datetime": "2024-01-01T11:00:00",
        "duration_hours": 1.0,
        "activity_type": "Conferencia",
        "location": "Auditorio A",
        "modality": "Presencial",
    }

    response = client.post("/api/activities/", headers=auth_headers, json=activity_data)

    assert response.status_code == 404


def test_create_activity_generates_public_slug(client, auth_headers, sample_data):
    """Crear una actividad genera automáticamente su public_slug y public_url.

    Los enlaces que comparten los jefes (/public/registrations/<slug>) dependen
    de que toda actividad nueva salga con slug asignado.
    """
    activity_data = {
        "event_id": sample_data["event_id"],
        "department": "ISC",
        "name": "Taller Genera Slug",
        "description": "Para verificar generación de enlace público",
        "start_datetime": "2024-01-01T10:00:00-06:00",
        "end_datetime": "2024-01-01T11:00:00-06:00",
        "duration_hours": 1.0,
        "activity_type": "Taller",
        "location": "Laboratorio 1",
        "modality": "Presencial",
        "max_capacity": 30,
    }

    response = client.post("/api/activities/", headers=auth_headers, json=activity_data)

    assert response.status_code == 201
    data = json.loads(response.data)
    slug = data["activity"].get("public_slug")
    assert slug
    assert slug == "taller-genera-slug"
    assert (
        data["activity"]
        .get("public_url", "")
        .endswith("/public/registrations/taller-genera-slug")
    )
