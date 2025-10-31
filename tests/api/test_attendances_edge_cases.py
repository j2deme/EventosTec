import json
from datetime import datetime, timezone

from app import db
from app.models.activity import Activity
from app.models.attendance import Attendance


def test_check_out_without_check_in_endpoint(client, auth_headers, sample_data, app):
    with app.app_context():
        activity = Activity(
            event_id=sample_data["event_id"],
            department="TEST",
            name="Magistral Edge",
            start_datetime=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc),
            duration_hours=1.0,
            activity_type="Magistral",
            location="Aula",
            modality="Presencial",
        )
        db.session.add(activity)
        db.session.commit()
        activity_id = activity.id

        attendance = Attendance(
            student_id=sample_data["student_id"], activity_id=activity_id
        )
        db.session.add(attendance)
        db.session.commit()

    res = client.post(
        "/api/attendances/check-out",
        headers=auth_headers,
        json={"student_id": sample_data["student_id"], "activity_id": activity_id},
    )

    assert res.status_code == 400
    data = json.loads(res.data)
    assert "No se ha registrado check-in" in data.get("message", "")
