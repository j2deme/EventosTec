"""Regresión: `GET /api/registrations` con `search` + otros filtros.

`filter_by()` resolvía `student_id`/`activity_id`/`status` en el namespace de
la entidad raíz, que `search` desalinea al unir `activities`/`students` con
aliases (InvalidRequestError: "Entity namespace ... has no property"): el
listado devolvía 500 tanto en el portal del estudiante como en el admin
cualquier vez que la búsqueda venía acompañada de otro filtro.
"""

import json
from datetime import datetime


def test_search_with_filters_returns_200(client, auth_headers, sample_data):
    from app import db
    from app.models.activity import Activity
    from app.models.registration import Registration

    with client.application.app_context():
        activity = Activity(
            event_id=sample_data["event_id"],
            department="ISC",
            name="Charla de prueba",
            start_datetime=datetime(2024, 3, 10, 9, 0),
            end_datetime=datetime(2024, 3, 10, 10, 0),
            duration_hours=1.0,
            activity_type="Magistral",
            location="Aula 1",
            modality="Presencial",
            max_capacity=10,
        )
        db.session.add(activity)
        db.session.flush()
        db.session.add(
            Registration(
                student_id=sample_data["student_id"],
                activity_id=activity.id,
                status="Confirmado",
            )
        )
        db.session.commit()
        activity_id = activity.id

    student_id = sample_data["student_id"]
    cases = [
        f"student_id={student_id}&search=Charla",
        f"student_id={student_id}&search=Charla&status=Confirmado",
        f"activity_id={activity_id}&search=Charla",
        f"event_id={sample_data['event_id']}&search=Charla",
    ]
    for query in cases:
        response = client.get(
            f"/api/registrations/?per_page=50&{query}", headers=auth_headers
        )
        assert response.status_code == 200, f"{query} -> {response.data}"

    # La búsqueda siguió surtiendo efecto (no se quedó vacía ni sin filtrar)
    response = client.get(
        f"/api/registrations/?per_page=50&student_id={student_id}&search=Charla",
        headers=auth_headers,
    )
    rows = json.loads(response.data)["registrations"]
    assert [row["activity"]["name"] for row in rows] == ["Charla de prueba"]
