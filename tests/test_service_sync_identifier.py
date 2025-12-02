import pytest
from datetime import datetime, timezone

from app.services.attendance_service import sync_related_attendances_from_source


def test_sync_includes_student_identifier(app):
    """Verifica que el servicio de sincronización incluya student_identifier en details."""
    from app import db
    from app.models.activity import Activity
    from app.models.attendance import Attendance
    from app.models.student import Student

    with app.app_context():
        # Crear actividad fuente A
        a = Activity()
        a.name = "Actividad A"
        a.activity_type = "Magistral"
        a.department = "General"
        a.duration_hours = 1
        a.event_id = 1
        a.start_datetime = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        a.end_datetime = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        a.location = "Sala 1"
        a.modality = "Presencial"
        db.session.add(a)

        # Actividad receptora B (apunta a A)
        b = Activity()
        b.name = "Actividad B"
        b.activity_type = "Magistral"
        b.department = "General"
        b.duration_hours = 1
        b.event_id = 1
        b.start_datetime = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        b.end_datetime = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        b.location = "Sala 1"
        b.modality = "Presencial"
        db.session.add(b)
        db.session.commit()

        # Relacionar B -> A (B apunta a A)
        b.related_activities.append(a)
        db.session.add(b)
        db.session.commit()

        # Crear estudiante con número de control
        s = Student()
        s.full_name = "Test Student"
        s.control_number = "20123456"
        db.session.add(s)
        db.session.commit()

        # Crear asistencia en A para el estudiante
        att = Attendance()
        att.student_id = s.id
        att.activity_id = a.id
        att.check_in_time = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        att.check_out_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        db.session.add(att)
        db.session.commit()

        # Ejecutar dry_run del servicio (llamando con source_activity_id = A.id)
        summary = sync_related_attendances_from_source(a.id, dry_run=True)

        assert isinstance(summary, dict)
        assert "details" in summary
        assert len(summary["details"]) >= 1
        # Buscar el detalle correspondiente al estudiante creado
        found = None
        for d in summary["details"]:
            if int(d.get("student_id")) == int(s.id):
                found = d
                break
        assert found is not None, (
            "Detalle del estudiante no encontrado en summary.details"
        )
        # Verificar que student_identifier esté presente y sea igual al control_number
        assert "student_identifier" in found
        assert found["student_identifier"] == "20123456"
