import pytest
from datetime import datetime, timezone
from app import db
from app.models.activity import Activity
from app.models.attendance import Attendance
from app.services.attendance_service import calculate_attendance_percentage


@pytest.fixture
def setup_attendance_test_data(app, sample_data):
    """Crea un estudiante, una actividad y una asistencia para tests de asistencia."""
    with app.app_context():
        activity = Activity(
            event_id=sample_data["event_id"],
            department="TEST",
            name="Actividad de Prueba para Asistencia",
            description="Descripción de prueba",
            start_datetime=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc),
            duration_hours=1.0,
            activity_type="Magistral",
            location="Auditorio de Prueba",
            modality="Presencial",
        )
        db.session.add(activity)
        db.session.flush()

        attendance = Attendance(
            student_id=sample_data["student_id"], activity_id=activity.id
        )
        db.session.add(attendance)
        db.session.commit()

        return {
            "student_id": sample_data["student_id"],
            "activity_id": activity.id,
            "attendance_id": attendance.id,
        }


def test_calculate_attendance_percentage_full_attendance(
    app, setup_attendance_test_data
):
    with app.app_context():
        attendance_id = setup_attendance_test_data["attendance_id"]

        attendance = db.session.get(Attendance, attendance_id)
        attendance.check_in_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        attendance.check_out_time = datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
        db.session.commit()

        percentage = calculate_attendance_percentage(attendance_id)

        assert percentage == 100.0
        updated_attendance = db.session.get(Attendance, attendance_id)
        assert updated_attendance.attendance_percentage == 100.0
        assert updated_attendance.status == "Asistió"
