"""Tests for attendances endpoint filtering functionality."""

import pytest
from app import create_app, db
from app.models.student import Student
from app.models.event import Event
from app.models.activity import Activity
from app.models.attendance import Attendance
from app.models.user import User
from flask_jwt_extended import create_access_token


@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create a test client for the Flask application."""
    return app.test_client()


@pytest.fixture
def admin_user(app):
    """Create an admin user for testing."""
    user = User()
    user.username = "testadmin"
    user.email = "admin@test.com"
    user.role = "Admin"
    user.set_password("testpassword")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def auth_headers(app, admin_user):
    """Create authorization headers for admin user."""
    with app.app_context():
        access_token = create_access_token(identity=str(admin_user.id))
        return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def sample_data(app):
    """Create sample data for testing filters."""
    from datetime import datetime

    # Create events
    event1 = Event()
    event1.name = "Event 1"
    event1.description = "Test event 1"
    event1.start_date = datetime(2024, 1, 1, 9, 0, 0)
    event1.end_date = datetime(2024, 1, 1, 17, 0, 0)

    event2 = Event()
    event2.name = "Event 2"
    event2.description = "Test event 2"
    event2.start_date = datetime(2024, 1, 2, 9, 0, 0)
    event2.end_date = datetime(2024, 1, 2, 17, 0, 0)

    db.session.add_all([event1, event2])
    db.session.flush()

    # Create activities
    activity1 = Activity()
    activity1.name = "Workshop 1"
    activity1.event_id = event1.id
    activity1.activity_type = "Taller"
    activity1.department = "TI"
    activity1.start_datetime = datetime(2024, 1, 1, 10, 0, 0)
    activity1.end_datetime = datetime(2024, 1, 1, 12, 0, 0)
    activity1.duration_hours = 2.0
    activity1.location = "Aula 101"
    activity1.modality = "Presencial"

    activity2 = Activity()
    activity2.name = "Conference 1"
    activity2.event_id = event1.id
    activity2.activity_type = "Conferencia"
    activity2.department = "TI"
    activity2.start_datetime = datetime(2024, 1, 1, 14, 0, 0)
    activity2.end_datetime = datetime(2024, 1, 1, 16, 0, 0)
    activity2.duration_hours = 2.0
    activity2.location = "Auditorio"
    activity2.modality = "Presencial"

    activity3 = Activity()
    activity3.name = "Workshop 2"
    activity3.event_id = event2.id
    activity3.activity_type = "Taller"
    activity3.department = "TI"
    activity3.start_datetime = datetime(2024, 1, 2, 10, 0, 0)
    activity3.end_datetime = datetime(2024, 1, 2, 12, 0, 0)
    activity3.duration_hours = 2.0
    activity3.location = "Aula 102"
    activity3.modality = "Presencial"

    db.session.add_all([activity1, activity2, activity3])
    db.session.flush()

    # Create student
    student = Student()
    student.full_name = "Test Student"
    student.control_number = "12345"
    student.email = "student@test.com"

    db.session.add(student)
    db.session.flush()

    # Create attendances
    attendance1 = Attendance()
    attendance1.student_id = student.id
    attendance1.activity_id = activity1.id
    attendance1.status = "Asistió"

    attendance2 = Attendance()
    attendance2.student_id = student.id
    attendance2.activity_id = activity2.id
    attendance2.status = "Asistió"

    attendance3 = Attendance()
    attendance3.student_id = student.id
    attendance3.activity_id = activity3.id
    attendance3.status = "Parcial"

    db.session.add_all([attendance1, attendance2, attendance3])
    db.session.commit()

    return {
        "events": [event1, event2],
        "activities": [activity1, activity2, activity3],
        "student": student,
        "attendances": [attendance1, attendance2, attendance3],
    }


def test_filter_by_event_id(client, auth_headers, sample_data):
    """Test filtering attendances by event_id."""
    event1_id = sample_data["events"][0].id

    response = client.get(
        f"/api/attendances/?event_id={event1_id}", headers=auth_headers
    )

    assert response.status_code == 200
    data = response.get_json()

    # Should return 2 attendances (workshop and conference from event 1)
    assert len(data["attendances"]) == 2

    # Verify all attendances belong to activities from event 1
    for attendance in data["attendances"]:
        assert attendance["activity"]["event_id"] == event1_id


def test_filter_by_activity_type(client, auth_headers, sample_data):
    """Test filtering attendances by activity_type."""
    response = client.get(
        "/api/attendances/?activity_type=Taller", headers=auth_headers
    )

    assert response.status_code == 200
    data = response.get_json()

    # Should return 2 attendances (both workshops)
    assert len(data["attendances"]) == 2

    # Verify all attendances belong to workshop activities
    for attendance in data["attendances"]:
        assert attendance["activity"]["activity_type"] == "Taller"


def test_filter_by_event_id_and_activity_type(client, auth_headers, sample_data):
    """Test filtering attendances by both event_id and activity_type."""
    event1_id = sample_data["events"][0].id

    response = client.get(
        f"/api/attendances/?event_id={event1_id}&activity_type=Taller",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.get_json()

    # Should return 1 attendance (workshop from event 1)
    assert len(data["attendances"]) == 1

    attendance = data["attendances"][0]
    assert attendance["activity"]["event_id"] == event1_id
    assert attendance["activity"]["activity_type"] == "Taller"


def test_filter_by_search(client, auth_headers, sample_data):
    """Test filtering attendances by search text."""
    response = client.get("/api/attendances/?search=Test Student", headers=auth_headers)

    assert response.status_code == 200
    data = response.get_json()

    # Should return all 3 attendances for the student
    assert len(data["attendances"]) == 3


def test_filter_by_search_control_number(client, auth_headers, sample_data):
    """Test filtering attendances by student control number."""
    response = client.get("/api/attendances/?search=12345", headers=auth_headers)

    assert response.status_code == 200
    data = response.get_json()

    # Should return all 3 attendances for the student
    assert len(data["attendances"]) == 3


def test_combined_filters(client, auth_headers, sample_data):
    """Test combining multiple filters."""
    event1_id = sample_data["events"][0].id

    response = client.get(
        f"/api/attendances/?event_id={event1_id}&activity_type=Taller&search=Test",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.get_json()

    # Should return 1 attendance
    assert len(data["attendances"]) == 1

    attendance = data["attendances"][0]
    assert attendance["activity"]["event_id"] == event1_id
    assert attendance["activity"]["activity_type"] == "Taller"
    assert "Test Student" in attendance["student_name"]


def test_filters_with_no_results(client, auth_headers, sample_data):
    """Test filters that return no results."""
    # Non-existent event_id
    response = client.get("/api/attendances/?event_id=99999", headers=auth_headers)

    assert response.status_code == 200
    data = response.get_json()
    assert len(data["attendances"]) == 0


def test_legacy_filters_still_work(client, auth_headers, sample_data):
    """Test that existing filters (activity_id, status) still work."""
    activity_id = sample_data["activities"][0].id

    response = client.get(
        f"/api/attendances/?activity_id={activity_id}", headers=auth_headers
    )

    assert response.status_code == 200
    data = response.get_json()

    # Should return 1 attendance
    assert len(data["attendances"]) == 1
    assert data["attendances"][0]["activity_id"] == activity_id

    # Test status filter
    response = client.get("/api/attendances/?status=Asistió", headers=auth_headers)

    assert response.status_code == 200
    data = response.get_json()

    # Should return 2 attendances with "Asistió" status
    assert len(data["attendances"]) == 2
    for attendance in data["attendances"]:
        assert attendance["status"] == "Asistió"
