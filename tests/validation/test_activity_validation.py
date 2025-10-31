import pytest
from datetime import datetime
from marshmallow import ValidationError
from app import db
from app.models.event import Event
from app.services.activity_service import validate_activity_dates


@pytest.fixture
def sample_event():
    return Event(
        name="Evento de Prueba",
        description="Descripción del evento",
        start_date=datetime(2024, 1, 1, 9, 0, 0),
        end_date=datetime(2024, 1, 1, 17, 0, 0),
        is_active=True,
    )


@pytest.fixture
def sample_activity_data(sample_event):
    return {
        "event_id": sample_event.id,
        "department": "ISC",
        "name": "Actividad Válida",
        "start_datetime": datetime(2024, 1, 1, 10, 0, 0),
        "end_datetime": datetime(2024, 1, 1, 11, 0, 0),
        "duration_hours": 1.0,
        "activity_type": "Conferencia",
        "location": "Auditorio A",
        "modality": "Presencial",
    }


def test_validate_activity_dates_valid(app, sample_event, sample_activity_data):
    with app.app_context():
        db.session.add(sample_event)
        db.session.flush()
        sample_activity_data["event_id"] = sample_event.id
        try:
            validate_activity_dates(sample_activity_data)
        except ValidationError as e:
            pytest.fail(f"validate_activity_dates lanzó una excepción inesperada: {e}")
