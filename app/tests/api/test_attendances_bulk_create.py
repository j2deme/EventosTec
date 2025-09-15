import pytest


def test_bulk_create_syncs_registration(client, app, sample_data, auth_headers):
    from app import db
    from app.models.registration import Registration
    from app.models.activity import Activity
    from datetime import datetime, timezone, timedelta

    student_id = sample_data['student_id']
    event_id = sample_data['event_id']

    with app.app_context():
        start = datetime.now(timezone.utc)
        end = start + timedelta(hours=1)
        activity = Activity(name='Actividad prueba', event_id=event_id, start_datetime=start, end_datetime=end,
                            duration_hours=1.0, activity_type='Taller', department='General', location='Sala 1', modality='Presencial')
        db.session.add(activity)
        db.session.commit()
        activity_id = activity.id

        reg = Registration(student_id=student_id,
                           activity_id=activity_id, status='Registrado')
        db.session.add(reg)
        db.session.commit()

    payload = {'activity_id': activity_id, 'student_ids': [student_id]}
    resp = client.post('/api/attendances/bulk-create',
                       json=payload, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.get_json()
    assert 'attendances' in data
    assert len(data['attendances']) >= 1

    with app.app_context():
        updated = db.session.query(Registration).filter_by(
            student_id=student_id, activity_id=activity_id).first()
        assert updated is not None
        assert updated.attended is True
        assert updated.status == 'Asistió'


def test_bulk_create_ignores_missing_students(client, app, sample_data, auth_headers):
    from app import db
    from app.models.activity import Activity
    from datetime import datetime, timezone, timedelta

    event_id = sample_data['event_id']

    with app.app_context():
        start = datetime.now(timezone.utc)
        end = start + timedelta(hours=1)
        activity = Activity(name='Actividad prueba 2', event_id=event_id, start_datetime=start, end_datetime=end,
                            duration_hours=1.0, activity_type='Taller', department='General', location='Sala 1', modality='Presencial')
        db.session.add(activity)
        db.session.commit()
        activity_id = activity.id

    missing_id = 999999
    payload = {'activity_id': activity_id, 'student_ids': [missing_id]}
    resp = client.post('/api/attendances/bulk-create',
                       json=payload, headers=auth_headers)
    assert resp.status_code in (200, 201)
    data = resp.get_json()
    assert 'attendances' in data
    assert len(data['attendances']) == 0
