# app/tests/test_activity_validation.py
import pytest
from datetime import datetime
from app import db
from app.models.event import Event
from app.models.activity import Activity
from app.services.activity_service import (
    validate_activity_dates,
    create_activity,
    update_activity,
)
from marshmallow import ValidationError


@pytest.fixture
def sample_event():
    """Crea un evento de prueba con fechas definidas."""
    return Event(
        name="Evento de Prueba",
        description="Descripción del evento",
        start_date=datetime(2024, 1, 1, 9, 0, 0),
        end_date=datetime(2024, 1, 1, 17, 0, 0),
        is_active=True,
    )


@pytest.fixture
def sample_activity_data(sample_event):
    """Devuelve datos de actividad válidos relacionados con el evento de prueba."""
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


# --- TESTS PARA validate_activity_dates ---


def test_validate_activity_dates_valid(app, sample_event, sample_activity_data):
    """Test: Debería pasar la validación si las fechas están dentro del rango del evento."""
    with app.app_context():
        # Añadir evento a la sesión
        db.session.add(sample_event)
        db.session.flush()  # Obtener el ID sin hacer commit

        # Actualizar el event_id en los datos de la actividad
        sample_activity_data["event_id"] = sample_event.id

        # La validación debería pasar sin lanzar excepción
        try:
            validate_activity_dates(sample_activity_data)
        except ValidationError as e:
            pytest.fail(f"validate_activity_dates lanzó una excepción inesperada: {e}")


def test_validate_activity_dates_start_before_event(
    app, sample_event, sample_activity_data
):
    """Test: Debería fallar si la fecha de inicio de la actividad es anterior a la del evento."""
    with app.app_context():
        db.session.add(sample_event)
        db.session.flush()
        sample_activity_data["event_id"] = sample_event.id

        # Modificar la fecha de inicio para que sea antes del evento
        sample_activity_data["start_datetime"] = datetime(2023, 12, 31, 10, 0, 0)

        with pytest.raises(ValidationError) as exc_info:
            validate_activity_dates(sample_activity_data)

        # Mensaje actual indica que debe estar dentro del rango del evento
        assert (
            "La fecha de inicio de la actividad debe estar dentro del rango del evento"
            in str(exc_info.value)
        )


def test_validate_activity_dates_end_after_event(
    app, sample_event, sample_activity_data
):
    """Test: Debería fallar si la fecha de fin de la actividad es posterior a la del evento."""
    with app.app_context():
        db.session.add(sample_event)
        db.session.flush()
        sample_activity_data["event_id"] = sample_event.id

        # Modificar la fecha de fin para que sea después del evento
        sample_activity_data["end_datetime"] = datetime(2024, 1, 2, 10, 0, 0)

        with pytest.raises(ValidationError) as exc_info:
            validate_activity_dates(sample_activity_data)

    # Mensaje actual indica que debe estar dentro del rango del evento
    assert (
        "La fecha de fin de la actividad debe estar dentro del rango del evento"
        in str(exc_info.value)
    )


def test_validate_activity_dates_start_after_end(
    app, sample_event, sample_activity_data
):
    """Test: Debería fallar si la fecha de inicio es posterior a la de fin."""
    with app.app_context():
        db.session.add(sample_event)
        db.session.flush()
        sample_activity_data["event_id"] = sample_event.id

        # Intercambiar fechas para que start > end
        sample_activity_data["start_datetime"], sample_activity_data["end_datetime"] = (
            sample_activity_data["end_datetime"],
            sample_activity_data["start_datetime"],
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_activity_dates(sample_activity_data)

    # Mensaje actual indica que la fecha de inicio no puede ser posterior a la de fin
    assert "La fecha de inicio no puede ser posterior a la fecha de fin" in str(
        exc_info.value
    )


def test_validate_activity_dates_event_not_found(app, sample_activity_data):
    """Test: Debería fallar si el evento no existe."""
    with app.app_context():
        # Usar un ID de evento que no existe
        sample_activity_data["event_id"] = 99999

        with pytest.raises(ValidationError) as exc_info:
            validate_activity_dates(sample_activity_data)

    assert "Evento no encontrado" in str(exc_info.value)
    # Field name puede ser '_schema' dependiendo de la implementación
    assert exc_info.value.field_name in ("event_id", "_schema")


# --- TESTS PARA create_activity ---


def test_create_activity_valid(app, sample_event, sample_activity_data):
    """Test: Debería crear una actividad si las fechas son válidas."""
    with app.app_context():
        db.session.add(sample_event)
        db.session.commit()  # Commit para que el evento tenga ID
        sample_activity_data["event_id"] = sample_event.id

        activity = create_activity(sample_activity_data)

        assert activity is not None
        assert activity.id is not None
        assert activity.name == "Actividad Válida"


def test_create_activity_invalid_dates(app, sample_event, sample_activity_data):
    """Test: Debería fallar al crear una actividad con fechas fuera del rango del evento."""
    with app.app_context():
        db.session.add(sample_event)
        db.session.commit()
        sample_activity_data["event_id"] = sample_event.id

        # Fecha de inicio antes del evento
        sample_activity_data["start_datetime"] = datetime(2023, 12, 31, 10, 0, 0)

        with pytest.raises(ValidationError):
            create_activity(sample_activity_data)

        # Verificar que no se haya creado en la base de datos
        assert db.session.query(Activity).count() == 0


# --- TESTS PARA update_activity ---


def test_update_activity_valid_dates(app, sample_event, sample_activity_data):
    """Test: Debería permitir actualizar una actividad con nuevas fechas válidas."""
    with app.app_context():
        # Crear evento y actividad
        db.session.add(sample_event)
        db.session.commit()

        sample_activity_data["event_id"] = sample_event.id
        activity = create_activity(sample_activity_data)

        # Datos de actualización con fechas válidas
        update_data = {
            "name": "Actividad Actualizada",
            "start_datetime": datetime(2024, 1, 1, 12, 0, 0),
            "end_datetime": datetime(2024, 1, 1, 13, 0, 0),
        }

        updated_activity = update_activity(activity.id, update_data)

        assert updated_activity.name == "Actividad Actualizada"
        # Puede que la app guarde timezone UTC; normalizar para comparar
        saved = updated_activity.start_datetime
        if saved.tzinfo is None:
            # convertir expected a naive
            assert saved == update_data["start_datetime"].replace(tzinfo=None)
        else:
            assert saved == update_data["start_datetime"].replace(tzinfo=saved.tzinfo)


def test_update_activity_invalid_dates(app, sample_event, sample_activity_data):
    """Test: Debería fallar al actualizar una actividad con fechas fuera del rango del evento."""
    with app.app_context():
        db.session.add(sample_event)
        db.session.commit()

        sample_activity_data["event_id"] = sample_event.id
        activity = create_activity(sample_activity_data)

        # Intentar actualizar con una fecha de fin después del evento
        update_data = {"end_datetime": datetime(2024, 1, 2, 10, 0, 0)}

        with pytest.raises(ValidationError):
            update_activity(activity.id, update_data)

        # Verificar que la actividad original no haya cambiado
        db.session.refresh(activity)
        saved = activity.end_datetime
        expected = sample_activity_data["end_datetime"]
        if saved.tzinfo is None and getattr(expected, "tzinfo", None) is not None:
            # comparar como naive
            assert saved == expected.replace(tzinfo=None)
        else:
            assert saved == expected


def test_update_activity_change_event_invalid_dates(
    app, sample_event, sample_activity_data
):
    """Test: Debería fallar al cambiar el evento y las nuevas fechas no encajan."""
    with app.app_context():
        # Crear dos eventos
        event_a = Event(
            name="Evento A",
            start_date=datetime(2024, 1, 1, 9, 0, 0),
            end_date=datetime(2024, 1, 1, 12, 0, 0),
            is_active=True,
        )
        event_b = Event(
            name="Evento B",
            start_date=datetime(2024, 1, 2, 9, 0, 0),
            end_date=datetime(2024, 1, 2, 12, 0, 0),
            is_active=True,
        )
        db.session.add_all([event_a, event_b])
        db.session.commit()

        # Crear actividad en el evento A
        sample_activity_data["event_id"] = event_a.id
        activity = create_activity(sample_activity_data)

        # Intentar moverla al evento B, pero con fechas del evento A (que no encajan en B)
        update_data = {
            "event_id": event_b.id,
            # start_datetime y end_datetime siguen siendo del 1 de enero, no del 2
        }

        with pytest.raises(ValidationError):
            update_activity(activity.id, update_data)
