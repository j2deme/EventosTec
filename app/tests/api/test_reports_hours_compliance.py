import pytest
from datetime import datetime, timedelta
from app import db
from app.models.event import Event
from app.models.activity import Activity
from app.models.student import Student
from app.models.registration import Registration


@pytest.fixture
def sample_event_with_activities(app):
    """Create event with activities and students with confirmed participations."""
    with app.app_context():
        # Create event
        event = Event(
            name='Test Event 2024',
            description='Test event for hours compliance',
            start_date=datetime(2024, 10, 1, 8, 0, 0),
            end_date=datetime(2024, 10, 5, 18, 0, 0),
            is_active=True
        )
        db.session.add(event)
        db.session.flush()

        # Create activities
        activity1 = Activity(
            event_id=event.id,
            department='ISC',
            name='Workshop Python',
            description='Python workshop',
            start_datetime=datetime(2024, 10, 1, 9, 0, 0),
            end_datetime=datetime(2024, 10, 1, 12, 0, 0),
            duration_hours=3.0,
            activity_type='Taller',
            location='Lab 1',
            modality='Presencial'
        )
        db.session.add(activity1)

        activity2 = Activity(
            event_id=event.id,
            department='ISC',
            name='Conference AI',
            description='AI conference',
            start_datetime=datetime(2024, 10, 2, 10, 0, 0),
            end_datetime=datetime(2024, 10, 2, 18, 0, 0),
            duration_hours=8.0,
            activity_type='Conferencia',
            location='Auditorium',
            modality='Presencial'
        )
        db.session.add(activity2)

        activity3 = Activity(
            event_id=event.id,
            department='IM',
            name='Robotics Demo',
            description='Robotics demonstration',
            start_datetime=datetime(2024, 10, 3, 14, 0, 0),
            end_datetime=datetime(2024, 10, 3, 16, 0, 0),
            duration_hours=2.0,
            activity_type='Taller',
            location='Lab 2',
            modality='Presencial'
        )
        db.session.add(activity3)
        db.session.flush()

        # Create students
        student1 = Student(
            control_number='18001234',
            full_name='Ana García López',
            career='Ingeniería en Sistemas Computacionales',
            email='ana.garcia@example.com'
        )
        db.session.add(student1)

        student2 = Student(
            control_number='19005678',
            full_name='Carlos Martínez Ruiz',
            career='Ingeniería Mecánica',
            email='carlos.martinez@example.com'
        )
        db.session.add(student2)

        student3 = Student(
            control_number='20009012',
            full_name='María Fernández Torres',
            career='Ingeniería en Sistemas Computacionales',
            email='maria.fernandez@example.com'
        )
        db.session.add(student3)
        db.session.flush()

        # Create confirmed registrations
        # Student 1: 11 hours (3 + 8) - eligible for credit
        reg1_1 = Registration(
            student_id=student1.id,
            activity_id=activity1.id,
            status='Confirmado',
            confirmation_date=datetime(2024, 10, 1, 12, 0, 0)
        )
        db.session.add(reg1_1)

        reg1_2 = Registration(
            student_id=student1.id,
            activity_id=activity2.id,
            status='Asistió',
            confirmation_date=datetime(2024, 10, 2, 18, 0, 0)
        )
        db.session.add(reg1_2)

        # Student 2: 10 hours (8 + 2) - exactly at threshold
        reg2_1 = Registration(
            student_id=student2.id,
            activity_id=activity2.id,
            status='Confirmado',
            confirmation_date=datetime(2024, 10, 2, 18, 0, 0)
        )
        db.session.add(reg2_1)

        reg2_2 = Registration(
            student_id=student2.id,
            activity_id=activity3.id,
            status='Asistió',
            confirmation_date=datetime(2024, 10, 3, 16, 0, 0)
        )
        db.session.add(reg2_2)

        # Student 3: 3 hours (only activity1) - not eligible
        reg3_1 = Registration(
            student_id=student3.id,
            activity_id=activity1.id,
            status='Confirmado',
            confirmation_date=datetime(2024, 10, 1, 12, 0, 0)
        )
        db.session.add(reg3_1)

        # Add a cancelled registration that should not count
        reg3_2 = Registration(
            student_id=student3.id,
            activity_id=activity2.id,
            status='Cancelado',
        )
        db.session.add(reg3_2)

        db.session.commit()

        return {
            'event_id': event.id,
            'student1_id': student1.id,
            'student2_id': student2.id,
            'student3_id': student3.id,
            'activity1_id': activity1.id,
            'activity2_id': activity2.id,
            'activity3_id': activity3.id,
        }


def test_hours_compliance_report_all_students(client, auth_headers, sample_event_with_activities):
    """Test hours compliance report returns all students."""
    event_id = sample_event_with_activities['event_id']
    
    response = client.get(
        f'/api/reports/hours_compliance?event_id={event_id}',
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json
    assert 'students' in data
    assert len(data['students']) == 3  # All 3 students with confirmed registrations
    
    # Check student data structure
    student = data['students'][0]
    assert 'id' in student
    assert 'control_number' in student
    assert 'full_name' in student
    assert 'career' in student
    assert 'total_hours' in student


def test_hours_compliance_report_min_hours_filter(client, auth_headers, sample_event_with_activities):
    """Test filtering by minimum hours (10+)."""
    event_id = sample_event_with_activities['event_id']
    
    response = client.get(
        f'/api/reports/hours_compliance?event_id={event_id}&min_hours=10',
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json
    assert len(data['students']) == 2  # Only students with 10+ hours
    
    # Verify hours
    for student in data['students']:
        assert student['total_hours'] >= 10


def test_hours_compliance_report_career_filter(client, auth_headers, sample_event_with_activities):
    """Test filtering by career."""
    event_id = sample_event_with_activities['event_id']
    
    response = client.get(
        f'/api/reports/hours_compliance?event_id={event_id}&career=Ingeniería en Sistemas Computacionales',
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json
    assert len(data['students']) == 2  # Ana and María
    
    for student in data['students']:
        assert student['career'] == 'Ingeniería en Sistemas Computacionales'


def test_hours_compliance_report_search_control_number(client, auth_headers, sample_event_with_activities):
    """Test searching by control number."""
    event_id = sample_event_with_activities['event_id']
    
    response = client.get(
        f'/api/reports/hours_compliance?event_id={event_id}&search=18001234',
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json
    assert len(data['students']) == 1
    assert data['students'][0]['control_number'] == '18001234'


def test_hours_compliance_report_search_name(client, auth_headers, sample_event_with_activities):
    """Test searching by student name."""
    event_id = sample_event_with_activities['event_id']
    
    response = client.get(
        f'/api/reports/hours_compliance?event_id={event_id}&search=Carlos',
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json
    assert len(data['students']) == 1
    assert 'Carlos' in data['students'][0]['full_name']


def test_hours_compliance_report_missing_event_id(client, auth_headers):
    """Test error when event_id is missing."""
    response = client.get(
        '/api/reports/hours_compliance',
        headers=auth_headers
    )
    
    assert response.status_code == 400
    assert 'requerido' in response.json['message']


def test_hours_compliance_report_invalid_event_id(client, auth_headers):
    """Test error when event doesn't exist."""
    response = client.get(
        '/api/reports/hours_compliance?event_id=99999',
        headers=auth_headers
    )
    
    assert response.status_code == 404
    assert 'no encontrado' in response.json['message']


def test_hours_compliance_excel_generation(client, auth_headers, sample_event_with_activities):
    """Test Excel file generation."""
    event_id = sample_event_with_activities['event_id']
    
    response = client.get(
        f'/api/reports/hours_compliance_excel?event_id={event_id}',
        headers=auth_headers
    )
    
    assert response.status_code == 200
    assert response.content_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    
    # Check Content-Disposition header
    assert 'attachment' in response.headers.get('Content-Disposition', '')
    assert '.xlsx' in response.headers.get('Content-Disposition', '')


def test_student_participations_details(client, auth_headers, sample_event_with_activities):
    """Test student participation details endpoint."""
    event_id = sample_event_with_activities['event_id']
    student1_id = sample_event_with_activities['student1_id']
    
    response = client.get(
        f'/api/reports/student_participations/{student1_id}?event_id={event_id}',
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json
    
    # Check student info
    assert 'student' in data
    assert data['student']['id'] == student1_id
    
    # Check participations
    assert 'participations' in data
    assert len(data['participations']) == 2  # Student 1 has 2 confirmed participations
    
    # Verify chronological order (should be sorted by start_datetime)
    part1 = data['participations'][0]
    part2 = data['participations'][1]
    assert part1['start_datetime'] < part2['start_datetime']
    
    # Verify structure
    assert 'name' in part1
    assert 'duration_hours' in part1
    assert 'activity_type' in part1
    assert 'status' in part1


def test_student_participations_missing_event_id(client, auth_headers, sample_event_with_activities):
    """Test error when event_id is missing in participations endpoint."""
    student1_id = sample_event_with_activities['student1_id']
    
    response = client.get(
        f'/api/reports/student_participations/{student1_id}',
        headers=auth_headers
    )
    
    assert response.status_code == 400


def test_student_participations_invalid_student(client, auth_headers, sample_event_with_activities):
    """Test error when student doesn't exist."""
    event_id = sample_event_with_activities['event_id']
    
    response = client.get(
        f'/api/reports/student_participations/99999?event_id={event_id}',
        headers=auth_headers
    )
    
    assert response.status_code == 404


def test_hours_compliance_excludes_cancelled_registrations(client, auth_headers, sample_event_with_activities):
    """Test that cancelled registrations are not counted."""
    event_id = sample_event_with_activities['event_id']
    student3_id = sample_event_with_activities['student3_id']
    
    response = client.get(
        f'/api/reports/hours_compliance?event_id={event_id}',
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json
    
    # Find student 3
    student3 = next((s for s in data['students'] if s['id'] == student3_id), None)
    assert student3 is not None
    
    # Should only have 3 hours (activity1), not 11 (activity1 + cancelled activity2)
    assert student3['total_hours'] == 3.0


def test_hours_compliance_report_unauthorized(client, sample_event_with_activities):
    """Test that endpoint requires authentication."""
    event_id = sample_event_with_activities['event_id']
    
    response = client.get(
        f'/api/reports/hours_compliance?event_id={event_id}'
    )
    
    # Should require JWT token
    assert response.status_code == 401
