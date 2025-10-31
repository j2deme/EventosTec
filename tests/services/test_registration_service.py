from datetime import datetime
from app import db
from app.models.activity import Activity
from app.services.registration_service import is_registration_allowed


def test_is_registration_allowed_magistral(app, sample_data):
    with app.app_context():
        activity = Activity(
            event_id=sample_data["event_id"],
            department="TEST",
            name="Magistral sin cupo",
            start_datetime=datetime(2024, 1, 1, 10, 0, 0),
            end_datetime=datetime(2024, 1, 1, 11, 0, 0),
            duration_hours=1.0,
            activity_type="Magistral",
            location="Auditorio",
            modality="Presencial",
            max_capacity=1,
        )
        db.session.add(activity)
        db.session.commit()

        allowed = is_registration_allowed(activity.id)
        assert allowed is True
