import json
import pytest
from datetime import datetime, timezone, timedelta

from app import db
from app.models.activity import Activity
from app.models.attendance import Attendance
from app.models.student import Student
from app.services.attendance_service import calculate_attendance_percentage


def test_check_out_without_check_in_endpoint(client, auth_headers, sample_data, app):
    """Intentar hacer check-out cuando no hay check-in registrado (debe devolver 400)."""
    with app.app_context():
        # Crear actividad magistral
        activity = Activity(
            event_id=sample_data['event_id'],
            department='TEST',
            name='Magistral Edge',
            start_datetime=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc),
            duration_hours=1.0,
            activity_type='Magistral',
            location='Aula',
            modality='Presencial'
        )
    db.session.add(activity)
    db.session.commit()
    activity_id = activity.id

    # Crear attendance sin check_in_time
    attendance = Attendance(student_id=sample_data['student_id'], activity_id=activity_id)
    db.session.add(attendance)
    db.session.commit()

    # Llamar al endpoint de check-out
    res = client.post('/api/attendances/check-out', headers=auth_headers, json={
        'student_id': sample_data['student_id'],
        'activity_id': activity_id
    })

    assert res.status_code == 400
    data = json.loads(res.data)
    assert 'No se ha registrado check-in' in data.get('message', '')


def test_double_check_in_endpoint(client, auth_headers, sample_data, app):
    """Intentar check-in dos veces debería devolver el existente (200) y no crear otro."""
    with app.app_context():
        activity = Activity(
            event_id=sample_data['event_id'],
            department='TEST',
            name='Magistral Doble',
            start_datetime=datetime(2024, 1, 2, 10, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2024, 1, 2, 11, 0, 0, tzinfo=timezone.utc),
            duration_hours=1.0,
            activity_type='Magistral',
            location='Aula',
            modality='Presencial'
        )
        db.session.add(activity)
        db.session.commit()
        activity_id = activity.id

        # Crear attendance con check_in_time ya establecido
        attendance = Attendance(
            student_id=sample_data['student_id'],
            activity_id=activity_id,
            check_in_time=datetime.now(timezone.utc),
            status='Parcial'
        )
        db.session.add(attendance)
        db.session.commit()

    res = client.post('/api/attendances/check-in', headers=auth_headers, json={
        'student_id': sample_data['student_id'],
        'activity_id': activity_id
    })

    assert res.status_code == 200
    data = json.loads(res.data)
    assert 'Ya se ha registrado el check-in' in data.get('message', '') or 'attendance' in data


def test_pause_without_check_in_endpoint(client, auth_headers, sample_data, app):
    """Pausar sin haber hecho check-in debe devolver 400."""
    with app.app_context():
        activity = Activity(
            event_id=sample_data['event_id'],
            department='TEST',
            name='Pause Edge',
            start_datetime=datetime(2024, 1, 3, 10, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2024, 1, 3, 11, 0, 0, tzinfo=timezone.utc),
            duration_hours=1.0,
            activity_type='Magistral',
            location='Aula',
            modality='Presencial'
        )
    db.session.add(activity)
    db.session.commit()
    activity_id = activity.id

    attendance = Attendance(student_id=sample_data['student_id'], activity_id=activity_id)
    db.session.add(attendance)
    db.session.commit()

    res = client.post('/api/attendances/pause', headers=auth_headers, json={
        'student_id': sample_data['student_id'],
        'activity_id': activity_id
    })

    assert res.status_code == 400
    data = json.loads(res.data)
    assert 'No se ha registrado check-in' in data.get('message', '')


def test_resume_without_pause_endpoint(client, auth_headers, sample_data, app):
    """Intentar reanudar una asistencia que no está pausada debe retornar 400 en el endpoint."""
    with app.app_context():
        activity = Activity(
            event_id=sample_data['event_id'],
            department='TEST',
            name='Resume Edge',
            start_datetime=datetime(2024, 1, 4, 10, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2024, 1, 4, 11, 0, 0, tzinfo=timezone.utc),
            duration_hours=1.0,
            activity_type='Magistral',
            location='Aula',
            modality='Presencial'
        )
        db.session.add(activity)
        db.session.commit()
        activity_id = activity.id

        attendance = Attendance(
            student_id=sample_data['student_id'],
            activity_id=activity_id,
            check_in_time=datetime.now(timezone.utc),
            is_paused=False
        )
        db.session.add(attendance)
        db.session.commit()

    res = client.post('/api/attendances/resume', headers=auth_headers, json={
        'student_id': sample_data['student_id'],
        'activity_id': activity_id
    })

    assert res.status_code == 400
    data = json.loads(res.data)
    assert 'La asistencia no está pausada' in data.get('message', '')


def test_bulk_create_skips_existing(client, auth_headers, sample_data, app):
    """bulk-create no debe duplicar asistencias ya existentes."""
    with app.app_context():
        # Crear actividad y dos estudiantes
        activity = Activity(
            event_id=sample_data['event_id'],
            department='TEST',
            name='Bulk Edge',
            start_datetime=datetime(2024, 1, 5, 10, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2024, 1, 5, 12, 0, 0, tzinfo=timezone.utc),
            duration_hours=2.0,
            activity_type='Taller',
            location='Aula',
            modality='Presencial'
        )
    db.session.add(activity)
    db.session.flush()
    activity_id = activity.id

    # Estudiante existente viene en sample_data
    existing_student_id = sample_data['student_id']

    # Crear otro estudiante
    new_student = Student(full_name='Edge Case', control_number='EC123')
    db.session.add(new_student)
    db.session.commit()

    # Crear asistencia ya existente para el estudiante existente
    existing_att = Attendance(student_id=existing_student_id, activity_id=activity_id,
                  attendance_percentage=100.0, status='Asistió')
    db.session.add(existing_att)
    db.session.commit()

    # Llamar bulk-create con ambos IDs
    res = client.post('/api/attendances/bulk-create', headers=auth_headers, json={
        'activity_id': activity_id,
        'student_ids': [existing_student_id, new_student.id]
    })

    assert res.status_code == 201
    data = json.loads(res.data)
    # Debe crear solo 1 nueva asistencia (para new_student)
    assert 'attendances' in data
    returned = data['attendances']
    assert all(a['activity_id'] == activity_id for a in returned)
    ids = [a.get('student_id') for a in returned]
    assert new_student.id in ids
    assert existing_student_id not in ids


def test_percentage_pause_longer_than_duration_service(app, sample_data):
    """Si la pausa excede la duración, el porcentaje debe ser 0 y estado 'Ausente'."""
    with app.app_context():
        # Actividad corta de 15 minutos
        activity = Activity(
            event_id=sample_data['event_id'],
            department='TEST',
            name='Short Activity',
            start_datetime=datetime(2024, 1, 6, 10, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2024, 1, 6, 10, 15, 0, tzinfo=timezone.utc),
            duration_hours=0.25,
            activity_type='Magistral',
            location='Aula',
            modality='Presencial'
        )
        db.session.add(activity)
        db.session.flush()

        # Crear attendance con check-in/out y una pausa muy larga
        attendance = Attendance(
            student_id=sample_data['student_id'],
            activity_id=activity.id,
            check_in_time=datetime(2024, 1, 6, 10, 0, 0, tzinfo=timezone.utc),
            pause_time=datetime(2024, 1, 6, 10, 1, 0, tzinfo=timezone.utc),
            resume_time=datetime(2024, 1, 6, 11, 0, 0, tzinfo=timezone.utc),  # Pausa de ~59 min
            check_out_time=datetime(2024, 1, 6, 10, 15, 0, tzinfo=timezone.utc)
        )
        db.session.add(attendance)
        db.session.commit()

        pct = calculate_attendance_percentage(attendance.id)

        assert pct == 0.0 or round(pct, 2) == 0.0
        updated = db.session.get(Attendance, attendance.id)
        assert updated.attendance_percentage == 0.0
        assert updated.status == 'Ausente'
