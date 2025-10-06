import pytest
from datetime import datetime, timedelta, timezone
from app import db
from app.models.event import Event
from app.models.activity import Activity
from app.models.student import Student
from app.models.attendance import Attendance
from app.utils.token_utils import generate_activity_token


def test_self_register_within_window(client, mocker):
    """Test that self-registration works when within the allowed time window (before start and up to 20 minutes after)"""
    with client.application.app_context():
        # Create event
        event = Event(
            name='Test Event',
            description='Test event for self-registration',
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc) + timedelta(days=1),
            is_active=True
        )
        db.session.add(event)
        db.session.commit()

        # Create activity that starts in 1 hour (students should be able to register before it starts)
        activity = Activity(
            event_id=event.id,
            department='ISC',
            name='Test Activity',
            start_datetime=datetime.now(timezone.utc) + timedelta(hours=1),
            end_datetime=datetime.now(timezone.utc) + timedelta(hours=2),
            duration_hours=1.0,
            activity_type='Conferencia',
            location='Sala A',
            modality='Presencial'
        )
        db.session.add(activity)
        db.session.commit()

        activity_id = activity.id
        activity_token = generate_activity_token(activity_id)

    # Mock the external authentication API
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'success': True,
        'student': {
            'full_name': 'Test Student',
            'email': 'test@example.com'
        }
    }
    mocker.patch('requests.post', return_value=mock_response)

    # Test self-registration
    response = client.post('/api/registrations/self', json={
        'activity_token': activity_token,
        'control_number': 'L12345678',
        'password': 'testpass'
    })

    assert response.status_code == 201
    data = response.get_json()
    assert data['message'] == 'Asistencia registrada'
    assert 'attendance' in data


def test_self_register_after_cutoff(client, mocker):
    """Test that self-registration is denied after the 20-minute cutoff"""
    with client.application.app_context():
        # Create event
        event = Event(
            name='Test Event',
            description='Test event for self-registration',
            start_date=datetime.now(timezone.utc) - timedelta(hours=1),
            end_date=datetime.now(timezone.utc) + timedelta(days=1),
            is_active=True
        )
        db.session.add(event)
        db.session.commit()

        # Create activity that started 25 minutes ago (past the cutoff)
        activity = Activity(
            event_id=event.id,
            department='ISC',
            name='Test Activity Past Cutoff',
            start_datetime=datetime.now(timezone.utc) - timedelta(minutes=25),
            end_datetime=datetime.now(timezone.utc) + timedelta(hours=1),
            duration_hours=1.5,
            activity_type='Conferencia',
            location='Sala B',
            modality='Presencial'
        )
        db.session.add(activity)
        db.session.commit()

        activity_id = activity.id
        activity_token = generate_activity_token(activity_id)

    # Mock the external authentication API
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'success': True,
        'student': {
            'full_name': 'Test Student',
            'email': 'test@example.com'
        }
    }
    mocker.patch('requests.post', return_value=mock_response)

    # Test self-registration should be denied
    response = client.post('/api/registrations/self', json={
        'activity_token': activity_token,
        'control_number': 'L12345678',
        'password': 'testpass'
    })

    assert response.status_code == 400
    data = response.get_json()
    assert 'ventana de registro' in data['message'].lower()


def test_self_register_timezone_aware_comparison(client, mocker):
    """Test that timezone-aware datetime comparison works correctly"""
    with client.application.app_context():
        # Create event
        event = Event(
            name='Test Event',
            description='Test event for self-registration',
            start_date=datetime.now(timezone.utc) - timedelta(hours=1),
            end_date=datetime.now(timezone.utc) + timedelta(days=1),
            is_active=True
        )
        db.session.add(event)
        db.session.commit()

        # Create activity that started 10 minutes ago (within the cutoff)
        # This is the critical test: start_datetime is timezone-aware
        # and we're comparing it with now which should also be timezone-aware
        activity = Activity(
            event_id=event.id,
            department='ISC',
            name='Test Activity Within Window',
            start_datetime=datetime.now(timezone.utc) - timedelta(minutes=10),
            end_datetime=datetime.now(timezone.utc) + timedelta(hours=1),
            duration_hours=1.2,
            activity_type='Conferencia',
            location='Sala C',
            modality='Presencial'
        )
        db.session.add(activity)
        db.session.commit()

        activity_id = activity.id
        activity_token = generate_activity_token(activity_id)

    # Mock the external authentication API
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'success': True,
        'student': {
            'full_name': 'Test Student',
            'email': 'test@example.com'
        }
    }
    mocker.patch('requests.post', return_value=mock_response)

    # Test self-registration should succeed (within 20-minute window)
    response = client.post('/api/registrations/self', json={
        'activity_token': activity_token,
        'control_number': 'L12345678',
        'password': 'testpass'
    })

    # This should succeed without raising TypeError about comparing naive and aware datetimes
    assert response.status_code == 201
    data = response.get_json()
    assert data['message'] == 'Asistencia registrada'


def test_self_register_duplicate_attendance(client, mocker):
    """Test that duplicate attendance registrations are prevented"""
    with client.application.app_context():
        # Create event
        event = Event(
            name='Test Event',
            description='Test event for self-registration',
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc) + timedelta(days=1),
            is_active=True
        )
        db.session.add(event)
        db.session.commit()

        # Create activity
        activity = Activity(
            event_id=event.id,
            department='ISC',
            name='Test Activity',
            start_datetime=datetime.now(timezone.utc) + timedelta(hours=1),
            end_datetime=datetime.now(timezone.utc) + timedelta(hours=2),
            duration_hours=1.0,
            activity_type='Conferencia',
            location='Sala D',
            modality='Presencial'
        )
        db.session.add(activity)
        db.session.commit()

        # Create student
        student = Student(
            control_number='L12345678',
            full_name='Test Student',
            email='test@example.com'
        )
        db.session.add(student)
        db.session.commit()

        # Create existing attendance
        attendance = Attendance(
            student_id=student.id,
            activity_id=activity.id,
            check_in_time=datetime.now(timezone.utc),
            status='Parcial'
        )
        db.session.add(attendance)
        db.session.commit()

        activity_id = activity.id
        activity_token = generate_activity_token(activity_id)

    # Mock the external authentication API
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'success': True,
        'student': {
            'full_name': 'Test Student',
            'email': 'test@example.com'
        }
    }
    mocker.patch('requests.post', return_value=mock_response)

    # Test duplicate self-registration should be denied
    response = client.post('/api/registrations/self', json={
        'activity_token': activity_token,
        'control_number': 'L12345678',
        'password': 'testpass'
    })

    assert response.status_code == 409
    data = response.get_json()
    assert 'Ya existe un registro de asistencia' in data['message']
