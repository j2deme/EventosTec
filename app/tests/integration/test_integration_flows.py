import pytest
from datetime import datetime
from app import db
from app.models.activity import Activity
from app.models.attendance import Attendance
from app.services.attendance_service import pause_attendance, resume_attendance, calculate_attendance_percentage


def test_full_attendance_flow_with_pause(app, sample_data):
    with app.app_context():
        activity = Activity(
            event_id=sample_data['event_id'],
            department='TEST',
            name='Flujo completo con pausa',
            start_datetime=datetime(2024, 1, 1, 10, 0, 0),
            end_datetime=datetime(2024, 1, 1, 11, 0, 0),
            duration_hours=1.0,
            activity_type='Magistral',
            location='Auditorio Test',
            modality='Presencial'
        )
        db.session.add(activity)
        db.session.commit()

        student_id = sample_data['student_id']
        activity_id = activity.id

        attendance = Attendance(
            student_id=student_id,
            activity_id=activity_id,
            check_in_time=datetime(2024, 1, 1, 10, 0, 0)
        )
        db.session.add(attendance)
        db.session.commit()

        attendance = pause_attendance(attendance.id)
        assert attendance.is_paused is True

        attendance = resume_attendance(attendance.id)
        assert attendance.is_paused is False

        attendance.check_out_time = datetime(2024, 1, 1, 11, 0, 0)
        db.session.commit()

        percentage = calculate_attendance_percentage(attendance.id)
        assert percentage is not None
        assert attendance.status in ['Asistió', 'Parcial']
