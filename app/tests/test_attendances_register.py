import pytest
from app import db
from app.models.attendance import Attendance
from app.models.registration import Registration
from app.models.activity import Activity
from app.models.event import Event
from datetime import datetime, timedelta, timezone


def create_activity_for_event(event_id):
    now = datetime.now(timezone.utc)
    start = now
    end = start + timedelta(hours=1)
    activity = Activity(
        name='Actividad Test',
        event_id=event_id,
        activity_type='Magistral',
        department='Depto',
        start_datetime=start,
        end_datetime=end,
        duration_hours=1.0,
        location='Aula 1',
        modality='Presencial'
    )
    db.session.add(activity)
    db.session.commit()
    return activity


def test_register_attendance_creates_attendance(client, sample_data, auth_headers):
    student_id = sample_data['student_id']
    event_id = sample_data['event_id']
    with client.application.app_context():
        activity = create_activity_for_event(event_id)
        activity_id = activity.id

    payload = {'student_id': student_id,
               'activity_id': activity_id, 'mark_present': True}
    resp = client.post('/api/attendances/register',
                       json=payload, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data['attendance']['student_id'] == student_id
    assert data['attendance']['activity_id'] == activity_id
    assert data['attendance']['attendance_percentage'] == 100.0


def test_register_attendance_syncs_registration(client, sample_data, auth_headers):
    student_id = sample_data['student_id']
    event_id = sample_data['event_id']
    with client.application.app_context():
        activity = create_activity_for_event(event_id)
        activity_id = activity.id
        reg = Registration(student_id=student_id, activity_id=activity_id,
                           status='Registrado', attended=False)
        db.session.add(reg)
        db.session.commit()

    payload = {'student_id': student_id,
               'activity_id': activity_id, 'mark_present': True}
    resp = client.post('/api/attendances/register',
                       json=payload, headers=auth_headers)
    assert resp.status_code == 201
    with client.application.app_context():
        reg2 = db.session.query(Registration).filter_by(
            student_id=student_id, activity_id=activity_id).first()
        assert reg2 is not None
        assert reg2.attended is True
        assert reg2.status == 'Asistió'


def test_register_attendance_idempotent(client, sample_data, auth_headers):
    student_id = sample_data['student_id']
    event_id = sample_data['event_id']
    with client.application.app_context():
        activity = create_activity_for_event(event_id)
        activity_id = activity.id

    payload = {'student_id': student_id,
               'activity_id': activity_id, 'mark_present': True}
    resp1 = client.post('/api/attendances/register',
                        json=payload, headers=auth_headers)
    resp2 = client.post('/api/attendances/register',
                        json=payload, headers=auth_headers)
    assert resp1.status_code == 201
    assert resp2.status_code in (200, 201)
    # Solo debe existir una asistencia para ese par student/activity
    with client.application.app_context():
        atts = db.session.query(Attendance).filter_by(
            student_id=student_id, activity_id=activity_id).all()
        assert len(atts) == 1
