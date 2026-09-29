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


def test_register_checkout_recalculates_percentage_and_status(
    client, auth_headers, sample_data
):
    """El checkout vía /register recalcula porcentaje y status.

    Regresión del bug: una asistencia creada como 'Parcial' (p. ej. self
    check-in) quedaba en 'Parcial'/0% para siempre al hacer checkout.
    """
    from app import db
    from app.models.activity import Activity
    from app.models.attendance import Attendance

    with client.application.app_context():
        activity = Activity(
            event_id=sample_data["event_id"],
            department="ISC",
            name="Checkout Recalcula",
            start_datetime=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc),
            duration_hours=1.0,
            activity_type="Taller",
            location="Aula B",
            modality="Presencial",
        )
        db.session.add(activity)
        db.session.commit()

        # Asistencia estilo self check-in: 'Parcial' 0% con check-in
        attendance = Attendance(
            student_id=sample_data["student_id"],
            activity_id=activity.id,
            check_in_time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            status="Parcial",
            attendance_percentage=0.0,
        )
        db.session.add(attendance)
        db.session.commit()
        activity_id = activity.id
        attendance_id = attendance.id

    response = client.post(
        "/api/attendances/register",
        headers=auth_headers,
        json={
            "student_id": sample_data["student_id"],
            "activity_id": activity_id,
            "check_out_time": "2024-01-01T13:00:00+00:00",
        },
    )

    assert response.status_code == 200

    with client.application.app_context():
        att = db.session.get(Attendance, attendance_id)
        assert att.check_out_time is not None
        # Presencia durante toda la actividad -> >= 80% -> 'Asistió'
        assert att.attendance_percentage >= 80
        assert att.status == "Asistió"


def test_register_checkout_unwinds_open_pause(client, auth_headers, sample_data):
    """El checkout vía /register cierra una pausa abierta antes de calcular."""
    from app import db
    from app.models.activity import Activity
    from app.models.attendance import Attendance

    with client.application.app_context():
        activity = Activity(
            event_id=sample_data["event_id"],
            department="ISC",
            name="Checkout Pausa Abierta",
            start_datetime=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc),
            duration_hours=1.0,
            activity_type="Taller",
            location="Aula B",
            modality="Presencial",
        )
        db.session.add(activity)
        db.session.commit()

        attendance = Attendance(
            student_id=sample_data["student_id"],
            activity_id=activity.id,
            check_in_time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            pause_time=datetime(2024, 1, 1, 12, 10, 0, tzinfo=timezone.utc),
            is_paused=True,
            status="Parcial",
            attendance_percentage=0.0,
        )
        db.session.add(attendance)
        db.session.commit()
        activity_id = activity.id
        attendance_id = attendance.id

    response = client.post(
        "/api/attendances/register",
        headers=auth_headers,
        json={
            "student_id": sample_data["student_id"],
            "activity_id": activity_id,
            "check_out_time": "2024-01-01T13:00:00+00:00",
        },
    )

    assert response.status_code == 200

    with client.application.app_context():
        att = db.session.get(Attendance, attendance_id)
        assert att.is_paused is False
        assert att.resume_time is not None
        assert att.attendance_percentage >= 80
        assert att.status == "Asistió"
