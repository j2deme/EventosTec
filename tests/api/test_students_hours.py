"""Tests for student hours tracking endpoints."""

import pytest
from datetime import datetime, timedelta


@pytest.fixture
def sample_event(app):
    """Create a sample event for testing."""
    from app.models.event import Event
    from app import db

    with app.app_context():
        event = Event(
            name="Test Event",
            description="Test event for hours tracking",
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=7),
            is_active=True,
        )
        db.session.add(event)
        db.session.commit()
        event_id = event.id

    return event_id


@pytest.fixture
def sample_student(app):
    """Create a sample student for testing."""
    from app.models.student import Student
    from app import db

    with app.app_context():
        student = Student(
            control_number="TEST001",
            full_name="Test Student",
            career="Test Career",
            email="test@test.com",
        )
        db.session.add(student)
        db.session.commit()
        student_id = student.id

    return student_id


@pytest.fixture
def sample_activity(app, sample_event):
    """Create a sample activity for testing."""
    from app.models.activity import Activity
    from app import db

    with app.app_context():
        activity = Activity(
            event_id=sample_event,
            department="TEST",
            name="Test Activity",
            description="Test activity",
            start_datetime=datetime.now(),
            end_datetime=datetime.now() + timedelta(hours=2),
            duration_hours=2.0,
            activity_type="Conferencia",
            location="Test Location",
            modality="Presencial",
        )
        db.session.add(activity)
        db.session.commit()
        activity_id = activity.id

    return activity_id


@pytest.fixture
def sample_registration(app, sample_student, sample_activity):
    """Create a sample registration with 'Asistió' status."""
    from app.models.registration import Registration
    from app import db

    with app.app_context():
        registration = Registration(
            student_id=sample_student, activity_id=sample_activity, status="Asistió"
        )
        db.session.add(registration)
        db.session.commit()
        registration_id = registration.id

    return registration_id


def test_get_students_with_filters(
    client, sample_event, sample_student, sample_activity, sample_registration
):
    """Test getting students with event filter."""
    # This endpoint doesn't require auth for basic GET
    resp = client.get(f"/api/students/?event_id={sample_event}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "students" in data
    assert len(data["students"]) > 0


def test_get_student_hours_by_event(
    client, sample_student, sample_event, sample_registration
):
    """Test getting student hours grouped by event."""
    resp = client.get(f"/api/students/{sample_student}/hours-by-event")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "events_hours" in data
    assert "student" in data

    # Should have at least one event with hours
    if len(data["events_hours"]) > 0:
        event_hours = data["events_hours"][0]
        assert "event_id" in event_hours
        assert "total_hours" in event_hours
        assert "has_complementary_credit" in event_hours
        assert event_hours["total_hours"] >= 0


def test_get_student_event_details(
    client, sample_student, sample_event, sample_registration
):
    """Test getting detailed student participation in an event."""
    resp = client.get(f"/api/students/{sample_student}/event/{sample_event}/details")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "student" in data
    assert "event" in data
    assert "total_confirmed_hours" in data
    assert "has_complementary_credit" in data
    assert "activities" in data

    # Should have confirmation for hours >= 10
    if data["total_confirmed_hours"] >= 10.0:
        assert data["has_complementary_credit"] is True
    else:
        assert data["has_complementary_credit"] is False


def test_student_hours_only_counts_asistio(app, client, sample_student, sample_event):
    """Test that only 'Asistió' status counts toward hours."""
    from app.models.activity import Activity
    from app.models.registration import Registration
    from app import db

    with app.app_context():
        # Create activities with different statuses
        activities_data = [
            ("Asistió", 5.0),
            ("Confirmado", 3.0),
            ("Registrado", 2.0),
            ("Asistió", 6.0),
        ]

        for status, hours in activities_data:
            activity = Activity(
                event_id=sample_event,
                department="TEST",
                name=f"Activity {status}",
                description="Test",
                start_datetime=datetime.now(),
                end_datetime=datetime.now() + timedelta(hours=hours),
                duration_hours=hours,
                activity_type="Conferencia",
                location="Test",
                modality="Presencial",
            )
            db.session.add(activity)
            db.session.flush()

            registration = Registration(
                student_id=sample_student, activity_id=activity.id, status=status
            )
            db.session.add(registration)

        db.session.commit()

    # Get hours by event
    resp = client.get(f"/api/students/{sample_student}/hours-by-event")
    assert resp.status_code == 200
    data = resp.get_json()

    # Find the test event
    test_event = next(
        (e for e in data["events_hours"] if e["event_id"] == sample_event), None
    )
    assert test_event is not None

    # Should only count 'Asistió' statuses: 5.0 + 6.0 = 11.0 hours
    assert test_event["total_hours"] == 11.0
    assert test_event["has_complementary_credit"] is True


def test_complementary_credit_badge_logic(app, client, sample_student, sample_event):
    """Test that complementary credit badge appears correctly."""
    from app.models.activity import Activity
    from app.models.registration import Registration
    from app import db

    with app.app_context():
        # Create activity with exactly 10 hours
        activity = Activity(
            event_id=sample_event,
            department="TEST",
            name="10 Hour Activity",
            description="Test",
            start_datetime=datetime.now(),
            end_datetime=datetime.now() + timedelta(hours=10),
            duration_hours=10.0,
            activity_type="Curso",
            location="Test",
            modality="Presencial",
        )
        db.session.add(activity)
        db.session.flush()

        registration = Registration(
            student_id=sample_student, activity_id=activity.id, status="Asistió"
        )
        db.session.add(registration)
        db.session.commit()

    resp = client.get(f"/api/students/{sample_student}/hours-by-event")
    assert resp.status_code == 200
    data = resp.get_json()

    test_event = next(
        (e for e in data["events_hours"] if e["event_id"] == sample_event), None
    )
    assert test_event is not None
    assert test_event["total_hours"] >= 10.0
    assert test_event["has_complementary_credit"] is True


def test_get_student_hours_not_found(client):
    """Test getting hours for non-existent student returns 404."""
    resp = client.get("/api/students/99999/hours-by-event")
    assert resp.status_code == 404
    data = resp.get_json()
    assert "message" in data


def test_get_student_event_details_not_found(client, sample_student):
    """Test getting event details for non-existent event returns 404."""
    resp = client.get(f"/api/students/{sample_student}/event/99999/details")
    assert resp.status_code == 404
    data = resp.get_json()
    assert "message" in data


def test_get_complementary_credits_requires_event_id(client, auth_headers):
    """Test that complementary credits endpoint requires event_id."""
    resp = client.get("/api/students/complementary-credits", headers=auth_headers)
    assert resp.status_code == 400
    data = resp.get_json()
    assert "event_id" in data["message"].lower()


def test_get_complementary_credits_filters_by_hours(
    app, client, auth_headers, sample_event
):
    """Test that only students with 10+ hours are returned."""
    from app.models.student import Student
    from app.models.activity import Activity
    from app.models.registration import Registration
    from app import db
    from datetime import datetime, timedelta

    with app.app_context():
        # Create two students
        student1 = Student(
            control_number="TEST100",
            full_name="Student with 10+ hours",
            career="Engineering",
            email="test100@test.com",
        )
        student2 = Student(
            control_number="TEST200",
            full_name="Student with <10 hours",
            career="Engineering",
            email="test200@test.com",
        )
        db.session.add_all([student1, student2])
        db.session.flush()

        # Create activities for student1 (12 hours total)
        activity1 = Activity(
            event_id=sample_event,
            department="TEST",
            name="Activity 1",
            start_datetime=datetime.now(),
            end_datetime=datetime.now() + timedelta(hours=8),
            duration_hours=8.0,
            activity_type="Conferencia",
            location="Test",
            modality="Presencial",
        )
        activity2 = Activity(
            event_id=sample_event,
            department="TEST",
            name="Activity 2",
            start_datetime=datetime.now(),
            end_datetime=datetime.now() + timedelta(hours=4),
            duration_hours=4.0,
            activity_type="Taller",
            location="Test",
            modality="Presencial",
        )
        db.session.add_all([activity1, activity2])
        db.session.flush()

        # Register student1 with both activities (12 hours)
        reg1 = Registration(
            student_id=student1.id, activity_id=activity1.id, status="Asistió"
        )
        reg2 = Registration(
            student_id=student1.id, activity_id=activity2.id, status="Asistió"
        )

        # Create activity for student2 (5 hours only)
        activity3 = Activity(
            event_id=sample_event,
            department="TEST",
            name="Activity 3",
            start_datetime=datetime.now(),
            end_datetime=datetime.now() + timedelta(hours=5),
            duration_hours=5.0,
            activity_type="Conferencia",
            location="Test",
            modality="Presencial",
        )
        db.session.add(activity3)
        db.session.flush()

        reg3 = Registration(
            student_id=student2.id, activity_id=activity3.id, status="Asistió"
        )

        db.session.add_all([reg1, reg2, reg3])
        db.session.commit()

    # Query the endpoint
    resp = client.get(
        f"/api/students/complementary-credits?event_id={sample_event}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()

    # Should only return student1 with 12 hours
    assert "students" in data
    assert len(data["students"]) == 1
    assert data["students"][0]["control_number"] == "TEST100"
    assert data["students"][0]["total_hours"] >= 10.0


def test_export_complementary_credits_generates_excel(
    app,
    client,
    auth_headers,
    sample_event,
    sample_student,
    sample_activity,
    sample_registration,
):
    """Test that Excel export endpoint returns file."""
    resp = client.get(
        f"/api/students/complementary-credits/export?event_id={sample_event}",
        headers=auth_headers,
    )

    # Should return file or empty result depending on data
    # If no students with 10+ hours, it should still work
    assert resp.status_code == 200
    assert (
        resp.content_type
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
