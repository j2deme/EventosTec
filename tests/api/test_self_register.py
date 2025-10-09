import pytest
from datetime import datetime, timedelta, timezone
from app import db
from app.models.activity import Activity
from app.models.student import Student
from app.models.attendance import Attendance
from app.models.registration import Registration
from app.utils.token_utils import generate_activity_token


@pytest.fixture
def activity_naive(db_session):
    # create activity with naive start_datetime (no tzinfo)
    a = Activity(
        event_id=1,
        department='DEP',
        name='Test Activity Naive',
        start_datetime=datetime.utcnow().replace(tzinfo=None),
        end_datetime=(datetime.utcnow() + timedelta(hours=1)
                      ).replace(tzinfo=None),
        duration_hours=1.0,
        activity_type='Magistral',
        location='Room',
    )
    db_session.add(a)
    db_session.commit()
    return a


@pytest.fixture
def student_payload():
    return {'control_number': 'TEST1234', 'password': 'secret'}


def test_self_register_creates_attendance(client, db_session, activity_naive, monkeypatch, student_payload):
    # prepare token and mock external auth endpoint
    token = generate_activity_token(activity_naive.id)

    # mock the internal student-login call to return success with student info
    def fake_post(url, json, timeout):
        class R:
            status_code = 200

            def json(self):
                return {'student': {'full_name': 'Test Student', 'email': 't@example.com'}}

        return R()

    monkeypatch.setattr('requests.post', fake_post)

    resp = client.post('/api/registrations/self', json={
        'control_number': student_payload['control_number'],
        'password': student_payload['password'],
        'activity_token': token,
    })

    assert resp.status_code == 201
    data = resp.get_json()
    assert data['message'] == 'Asistencia registrada'

    # check attendance in DB
    att = Attendance.query.filter_by(
        student_id=data['attendance']['student_id']).first()
    assert att is not None


def test_self_register_blocks_duplicate(client, db_session, activity_naive, monkeypatch, student_payload):
    # create an existing student and attendance
    s = Student(
        control_number=student_payload['control_number'], full_name='Existing')
    db_session.add(s)
    db_session.commit()

    att = Attendance(student_id=s.id, activity_id=activity_naive.id,
                     check_in_time=datetime.now(timezone.utc), status='Parcial')
    db_session.add(att)
    db_session.commit()

    token = generate_activity_token(activity_naive.id)

    def fake_post(url, json, timeout):
        class R:
            status_code = 200

            def json(self):
                return {'student': {'full_name': 'Existing', 'email': 'ex@example.com'}}

        return R()

    monkeypatch.setattr('requests.post', fake_post)

    resp = client.post('/api/registrations/self', json={
        'control_number': student_payload['control_number'],
        'password': student_payload['password'],
        'activity_token': token,
    })

    assert resp.status_code == 409


def test_self_register_cutoff_respected(client, db_session, monkeypatch, student_payload):
    # create activity with start long in the past (so cutoff passed)
    a = Activity(
        event_id=2,
        department='DEP',
        name='Old Activity',
        start_datetime=(datetime.utcnow() - timedelta(hours=2)
                        ).replace(tzinfo=None),
        end_datetime=(datetime.utcnow() - timedelta(hours=1)
                      ).replace(tzinfo=None),
        duration_hours=1.0,
        activity_type='Magistral',
        location='Room',
    )
    db_session.add(a)
    db_session.commit()

    token = generate_activity_token(a.id)

    def fake_post(url, json, timeout):
        class R:
            status_code = 200

            def json(self):
                return {'student': {'full_name': 'Old Student', 'email': 'old@example.com'}}

        return R()

    monkeypatch.setattr('requests.post', fake_post)

    resp = client.post('/api/registrations/self', json={
        'control_number': student_payload['control_number'],
        'password': student_payload['password'],
        'activity_token': token,
    })

    assert resp.status_code == 400
    data = resp.get_json()
    assert 'terminado' in data['message'].lower()
