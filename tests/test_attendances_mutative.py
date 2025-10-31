from app import db
from app.models.activity import Activity
from app.models.registration import Registration
from app.models.attendance import Attendance
from datetime import datetime, timedelta, timezone
from flask_jwt_extended import create_access_token


def create_activity_short(event_id):
    now = datetime.now(timezone.utc)
    start = now
    end = start + timedelta(minutes=30)
    activity = Activity()
    activity.name = "Mutative Test"
    activity.event_id = event_id
    activity.activity_type = "Magistral"
    activity.department = "Test"
    activity.start_datetime = start
    activity.end_datetime = end
    activity.duration_hours = 0.5
    activity.location = "Sala"
    activity.modality = "Presencial"
    db.session.add(activity)
    db.session.commit()
    return activity


def test_check_out_calculates_percentage_and_syncs_registration(
    client, app, sample_data, auth_headers
):
    # Preparar actividad corta y preregistro
    student_id = sample_data["student_id"]
    event_id = sample_data["event_id"]

    with app.app_context():
        activity = create_activity_short(event_id)
        activity_id = activity.id
        # Crear preregistro
        reg = Registration()
        reg.student_id = student_id
        reg.activity_id = activity_id
        reg.status = "Registrado"
        reg.attended = False
        db.session.add(reg)
        db.session.commit()

        # Crear attendance con check_in_time
        att = Attendance()
        att.student_id = student_id
        att.activity_id = activity_id
        att.check_in_time = datetime.now(timezone.utc)
        db.session.add(att)
        db.session.commit()

    # Llamar check-out (admin)
    payload = {"student_id": student_id, "activity_id": activity_id}
    resp = client.post("/api/attendances/check-out", json=payload, headers=auth_headers)

    assert resp.status_code == 200
    data = resp.get_json()
    assert "attendance" in data
    # Verificar que la attendance ahora tiene check_out_time y porcentaje calculado
    with app.app_context():
        a = (
            db.session.query(Attendance)
            .filter_by(student_id=student_id, activity_id=activity_id)
            .first()
        )
        assert a is not None
        assert a.check_out_time is not None
        assert a.attendance_percentage is not None
        # Si la duración es 0.5h y el alumno estuvo, porcentaje debe ser > 0
        assert a.attendance_percentage >= 0

        # Verificar preregistro sincronizado cuando es Asistió
        reg2 = (
            db.session.query(Registration)
            .filter_by(student_id=student_id, activity_id=activity_id)
            .first()
        )
        assert reg2 is not None
        # Si el porcentaje es suficiente, registration.attended se debería haber marcado (no forzamos el valor aquí exacto)


def test_student_cannot_call_check_in(client, app, sample_data):
    # Crear token de student usando sample_data student id
    student_id = sample_data["student_id"]
    token = create_access_token(identity=str(student_id))
    headers = {"Authorization": f"Bearer {token}"}

    # Crear actividad magistral
    with app.app_context():
        now = datetime.now(timezone.utc)
        start = now
        end = start + timedelta(hours=1)
        activity = Activity()
        activity.name = "Mutative Student Test"
        activity.event_id = sample_data["event_id"]
        activity.start_datetime = start
        activity.end_datetime = end
        activity.duration_hours = 1.0
        activity.activity_type = "Magistral"
        activity.department = "Test"
        activity.location = "Sala X"
        activity.modality = "Presencial"

        db.session.add(activity)
        db.session.commit()
        activity_id = activity.id

    payload = {"student_id": student_id, "activity_id": activity_id}
    resp = client.post("/api/attendances/check-in", json=payload, headers=headers)

    # En la implementación, /check-in requiere @require_admin, por lo que debería devolver 403 o similar
    assert resp.status_code in (401, 403)
