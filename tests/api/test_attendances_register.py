from datetime import datetime, timezone


def test_register_attendance(client, auth_headers, sample_data):
    from app import db
    from app.models.activity import Activity

    with client.application.app_context():
        activity = Activity(
            event_id=sample_data["event_id"],
            department="ISC",
            name="Registro Normal",
            start_datetime=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc),
            duration_hours=1.0,
            activity_type="Taller",
            location="Aula B",
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
        "/api/attendances/register", headers=auth_headers, json=attendance_data
    )
    assert response.status_code == 201
