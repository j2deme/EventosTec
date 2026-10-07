import json
from datetime import datetime


def test_create_registration(client, auth_headers, sample_data):
    from app import db
    from app.models.activity import Activity

    with client.application.app_context():
        activity = Activity(
            event_id=sample_data["event_id"],
            department="ISC",
            name="Taller de prueba",
            start_datetime=datetime(2024, 1, 1, 10, 0, 0),
            end_datetime=datetime(2024, 1, 1, 11, 0, 0),
            duration_hours=1.0,
            activity_type="Taller",
            location="Laboratorio A",
            modality="Presencial",
            max_capacity=10,
        )
        db.session.add(activity)
        db.session.commit()
        activity_id = activity.id

    registration_data = {
        "student_id": sample_data["student_id"],
        "activity_id": activity_id,
    }

    response = client.post(
        "/api/registrations/", headers=auth_headers, json=registration_data
    )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["message"] == "Preregistro creado exitosamente"


def _create_activity(client, event_id, name):
    from app import db
    from app.models.activity import Activity

    with client.application.app_context():
        activity = Activity(
            event_id=event_id,
            department="ISC",
            name=name,
            start_datetime=datetime(2024, 1, 1, 10, 0, 0),
            end_datetime=datetime(2024, 1, 1, 11, 0, 0),
            duration_hours=1.0,
            activity_type="Taller",
            location="Laboratorio A",
            modality="Presencial",
            max_capacity=10,
        )
        db.session.add(activity)
        db.session.commit()
        return activity.id


def test_get_registrations_includes_attendance(client, auth_headers, sample_data):
    """`GET /api/registrations` expone la asistencia del estudiante.

    El auto-registro no cambia el `status` de la Registration (sigue
    "Confirmado" hasta el checkout), así que sin este campo el portal no
    tendría forma de mostrar que la asistencia ya quedó tomada.
    """
    from app import db
    from app.models.attendance import Attendance
    from app.models.registration import Registration

    checked_in = _create_activity(client, sample_data["event_id"], "Con check-in")
    without_check_in = _create_activity(client, sample_data["event_id"], "Sin check-in")

    with client.application.app_context():
        for activity_id in (checked_in, without_check_in):
            db.session.add(
                Registration(
                    student_id=sample_data["student_id"],
                    activity_id=activity_id,
                    status="Confirmado",
                    attended=activity_id == checked_in,
                )
            )
        db.session.add(
            Attendance(
                student_id=sample_data["student_id"],
                activity_id=checked_in,
                status="Parcial",
                check_in_time=datetime(2024, 1, 1, 9, 30, 0),
            )
        )
        db.session.commit()

    response = client.get(
        f"/api/registrations/?student_id={sample_data['student_id']}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    rows = {
        row["activity_id"]: row for row in json.loads(response.data)["registrations"]
    }

    opened = rows[checked_in]["attendance"]
    assert opened["status"] == "Parcial"
    assert opened["check_in_time"]
    # El status de la Registration NO cambió hasta el cierre
    assert rows[checked_in]["status"] == "Confirmado"
    assert rows[without_check_in]["attendance"] is None
