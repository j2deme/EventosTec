import json
from datetime import datetime, timezone

from app import db
from app.models.activity import Activity
from app.models.attendance import Attendance
from app.services.attendance_service import calculate_attendance_percentage


def test_pause_without_check_in_endpoint(client, auth_headers, sample_data, app):
    """Pausar sin haber hecho check-in debe devolver 400."""
    with app.app_context():
        activity = Activity(
            event_id=sample_data["event_id"],
            department="TEST",
            name="Pause Edge",
            start_datetime=datetime(2024, 1, 3, 10, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2024, 1, 3, 11, 0, 0, tzinfo=timezone.utc),
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
        "/api/attendances/pause",
        headers=auth_headers,
        json={"student_id": sample_data["student_id"], "activity_id": activity_id},
    )

    assert res.status_code == 400
    data = json.loads(res.data)
    assert "No se ha registrado check-in" in data.get("message", "")


def test_resume_without_pause_endpoint(client, auth_headers, sample_data, app):
    """Intentar reanudar una asistencia que no está pausada debe retornar 400 en el endpoint."""
    with app.app_context():
        activity = Activity(
            event_id=sample_data["event_id"],
            department="TEST",
            name="Resume Edge",
            start_datetime=datetime(2024, 1, 4, 10, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2024, 1, 4, 11, 0, 0, tzinfo=timezone.utc),
            duration_hours=1.0,
            activity_type="Magistral",
            location="Aula",
            modality="Presencial",
        )
        db.session.add(activity)
        db.session.commit()
        activity_id = activity.id

        attendance = Attendance(
            student_id=sample_data["student_id"],
            activity_id=activity_id,
            check_in_time=datetime.now(timezone.utc),
            is_paused=False,
        )
        db.session.add(attendance)
        db.session.commit()

    res = client.post(
        "/api/attendances/resume",
        headers=auth_headers,
        json={"student_id": sample_data["student_id"], "activity_id": activity_id},
    )

    assert res.status_code == 400
    data = json.loads(res.data)
    assert "La asistencia no está pausada" in data.get("message", "")


def test_percentage_pause_longer_than_duration_service(app, sample_data):
    """Si la pausa excede la duración, el porcentaje debe ser 0 y estado 'Ausente'."""
    with app.app_context():
        # Actividad corta de 15 minutos
        activity = Activity(
            event_id=sample_data["event_id"],
            department="TEST",
            name="Short Activity",
            start_datetime=datetime(2024, 1, 6, 10, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2024, 1, 6, 10, 15, 0, tzinfo=timezone.utc),
            duration_hours=0.25,
            activity_type="Magistral",
            location="Aula",
            modality="Presencial",
        )
        db.session.add(activity)
        db.session.flush()

        # Crear attendance con check-in/out y una pausa muy larga
        attendance = Attendance(
            student_id=sample_data["student_id"],
            activity_id=activity.id,
            check_in_time=datetime(2024, 1, 6, 10, 0, 0, tzinfo=timezone.utc),
            pause_time=datetime(2024, 1, 6, 10, 1, 0, tzinfo=timezone.utc),
            resume_time=datetime(
                2024, 1, 6, 11, 0, 0, tzinfo=timezone.utc
            ),  # Pausa de ~59 min
            check_out_time=datetime(2024, 1, 6, 10, 15, 0, tzinfo=timezone.utc),
        )
        db.session.add(attendance)
        db.session.commit()

        pct = calculate_attendance_percentage(attendance.id)

        assert pct == 0.0 or round(pct, 2) == 0.0
        updated = db.session.get(Attendance, attendance.id)
        assert updated.attendance_percentage == 0.0
        assert updated.status == "Ausente"
