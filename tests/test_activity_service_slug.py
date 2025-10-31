from unittest.mock import MagicMock
from app.services.activity_service import create_activity, update_activity
from app.models.activity import Activity


def make_activity_payload(name="Test Activity", **kw):
    data = {
        "event_id": 1,
        "department": "TEST",
        "name": name,
        "start_datetime": "2025-01-01T10:00:00",
        "end_datetime": "2025-01-01T12:00:00",
        "duration_hours": 2,
        "activity_type": "Taller",
        "location": "Room",
    }
    data.update(kw)
    return data


def test_create_generates_slug(monkeypatch):
    # Monkeypatch DB session generate_unique_slug uses db.session
    fake_slug = "test-activity"
    monkeypatch.setattr(
        "app.services.activity_service.generate_unique_slug",
        lambda session, model, value, column="public_slug": fake_slug,
    )
    # ensure db.session.add/commit do nothing using a dummy activity object creation
    payload = make_activity_payload()
    act = create_activity(payload)
    assert isinstance(act, Activity)
    assert getattr(act, "public_slug", None) == fake_slug


def test_update_name_without_apply_keeps_manual_slug(monkeypatch):
    # Create fake activity instance and stub db.session.get
    activity = Activity()
    activity.id = 1
    activity.name = "Old Name"
    activity.public_slug = "custom-manual-slug"

    monkeypatch.setattr("app.services.activity_service.db", MagicMock())
    monkeypatch.setattr("app.services.activity_service.db.session", MagicMock())
    monkeypatch.setattr(
        "app.services.activity_service.db.session.get", lambda cls, id: activity
    )

    # Call update_activity with new name but without apply_generated_slug
    updated = update_activity(1, {"name": "New Name"})
    assert updated.public_slug == "custom-manual-slug"


def test_update_name_with_apply_replaces_slug(monkeypatch):
    activity = Activity()
    activity.id = 2
    activity.name = "Old Name"
    activity.public_slug = "old-name"

    monkeypatch.setattr("app.services.activity_service.db", MagicMock())
    monkeypatch.setattr("app.services.activity_service.db.session", MagicMock())
    monkeypatch.setattr(
        "app.services.activity_service.db.session.get", lambda cls, id: activity
    )
    monkeypatch.setattr(
        "app.services.activity_service.generate_unique_slug",
        lambda session, model, value, column="public_slug": "new-name-generated",
    )

    updated = update_activity(2, {"name": "New Name", "apply_generated_slug": True})
    assert updated.public_slug == "new-name-generated"
