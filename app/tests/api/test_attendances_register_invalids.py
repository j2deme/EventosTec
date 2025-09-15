import json
import pytest
from datetime import datetime, timezone, timedelta


def test_register_invalid_student(client, auth_headers):
    payload = {"student_id": 9999999, "activity_id": 1, "mark_present": True}
    res = client.post('/api/attendances/register', data=json.dumps(payload),
                      headers=auth_headers, content_type='application/json')
    assert res.status_code == 404


def test_register_invalid_activity(client, auth_headers):
    payload = {"student_id": 1, "activity_id": 9999999, "mark_present": True}
    res = client.post('/api/attendances/register', data=json.dumps(payload),
                      headers=auth_headers, content_type='application/json')
    assert res.status_code == 404


def test_register_missing_fields(client, auth_headers):
    payload = {"student_id": 1}
    res = client.post('/api/attendances/register', data=json.dumps(payload),
                      headers=auth_headers, content_type='application/json')
    assert res.status_code == 400


def test_register_malformed_dates(app, client, auth_headers, sample_data):
    from app import db
    from app.models.activity import Activity

    with app.app_context():
        event_id = sample_data['event_id']
        now = datetime.now(timezone.utc)
        act = Activity(
            event_id=event_id,
            department='DEP',
            name='Actividad prueba',
            start_datetime=now,
            end_datetime=now + timedelta(hours=1),
            duration_hours=1.0,
            activity_type='Taller',
            location='Aula 1',
            modality='Presencial'
        )
        db.session.add(act)
        db.session.commit()
        activity_id = act.id
        student_id = sample_data['student_id']

    payload = {"student_id": student_id,
               "activity_id": activity_id, "check_in_time": "not-a-date"}
    res = client.post('/api/attendances/register', data=json.dumps(payload),
                      headers=auth_headers, content_type='application/json')
    assert res.status_code == 400
