import json
from datetime import datetime, timezone


def test_check_in_magistral(client, auth_headers, sample_data):
    """Test de check-in para conferencia magistral"""
    from app import db
    from app.models.activity import Activity

    with client.application.app_context():
        activity = Activity(
            event_id=sample_data["event_id"],
            department="ISC",
            name="Conferencia Magistral",
            start_datetime=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc),
            duration_hours=1.0,
            activity_type="Magistral",
            location="Auditorio Principal",
            modality="Presencial",
        )
        db.session.add(activity)
        db.session.commit()
        activity_id = activity.id

    attendance_data = {
        "student_id": sample_data["student_id"],
        "activity_id": activity_id,
    }

    response = client.post(
        "/api/attendances/check-in", headers=auth_headers, json=attendance_data
    )
    assert response.status_code == 201
    data = json.loads(response.data)
    assert "attendance" in data
    assert data["attendance"]["status"] == "Parcial"


def test_check_in_non_magistral(client, auth_headers, sample_data):
    """Test de check-in para actividad no magistral (debería fallar)"""
    from app import db
    from app.models.activity import Activity

    with client.application.app_context():
        activity = Activity(
            event_id=sample_data["event_id"],
            department="ISC",
            name="Taller Normal",
            start_datetime=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc),
            duration_hours=1.0,
            activity_type="Taller",
            location="Laboratorio A",
            modality="Presencial",
        )
        db.session.add(activity)
        db.session.commit()
        activity_id = activity.id

    attendance_data = {
        "student_id": sample_data["student_id"],
        "activity_id": activity_id,
    }

    response = client.post(
        "/api/attendances/check-in", headers=auth_headers, json=attendance_data
    )
    assert response.status_code == 400
