from app import db
from app.models.activity import Activity
from app.models.attendance import Attendance
from app.models.registration import Registration
from datetime import datetime


def test_register_creates_related_attendances(app, client, auth_headers, sample_data):
    """Al crear/ marcar presente una asistencia para la actividad A, debe crearse también para la actividad B relacionada."""
    with app.app_context():
        # Crear dos actividades A y B bajo el mismo evento
        event_id = sample_data["event_id"]
        student_id = sample_data["student_id"]

        activity_a = Activity()
        activity_a.event_id = event_id
        activity_a.department = "DEP"
        activity_a.name = "Actividad A"
        activity_a.start_datetime = datetime(2025, 1, 1, 10, 0, 0)
        activity_a.end_datetime = datetime(2025, 1, 1, 12, 0, 0)
        activity_a.duration_hours = 2
        activity_a.activity_type = "Magistral"
        activity_a.location = "Sala 1"
        activity_a.modality = "Presencial"
        db.session.add(activity_a)

        activity_b = Activity()
        activity_b.event_id = event_id
        activity_b.department = "DEP"
        activity_b.name = "Actividad B"
        activity_b.start_datetime = datetime(2025, 1, 1, 10, 0, 0)
        activity_b.end_datetime = datetime(2025, 1, 1, 12, 0, 0)
        activity_b.duration_hours = 2
        activity_b.activity_type = "Magistral"
        activity_b.location = "Sala 2"
        activity_b.modality = "Presencial"
        db.session.add(activity_b)

        db.session.commit()

        # Vincular B como related_activity de A
        activity_a.related_activities.append(activity_b)
        db.session.add(activity_a)
        db.session.commit()

        # Asegurarnos que no hay asistencias previas para B
        assert (
            Attendance.query.filter_by(
                student_id=student_id, activity_id=activity_b.id
            ).first()
            is None
        )

        # Guardar los IDs antes de salir del contexto para evitar DetachedInstanceError
        activity_a_id = activity_a.id
        activity_b_id = activity_b.id

    # Llamar al endpoint para registrar asistencia en A (mark_present=True)
    payload = {
        "student_id": student_id,
        "activity_id": activity_a_id,
        "mark_present": True,
    }
    res = client.post("/api/attendances/register", json=payload, headers=auth_headers)
    assert res.status_code in (200, 201)

    with app.app_context():
        # Comprobar que la asistencia para B ahora existe y está marcada como Asistió
        att_b = Attendance.query.filter_by(
            student_id=student_id, activity_id=activity_b_id
        ).first()
        assert att_b is not None
        assert att_b.status == "Asistió" or att_b.attendance_percentage == 100.0

        # Si hay preregistro para B, debe haberse marcado como asistido
        reg_b = Registration.query.filter_by(
            student_id=student_id, activity_id=activity_b_id
        ).first()
        if reg_b:
            assert reg_b.status == "Asistió"
