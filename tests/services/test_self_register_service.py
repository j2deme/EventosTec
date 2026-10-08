"""Ventana de auto-registro (self check-in): cálculo y estados."""

from datetime import datetime, timedelta, timezone

from app.services.self_register_service import (
    CLOSED,
    NOT_OPEN,
    OPEN,
    self_register_state,
    self_register_window,
    window_message,
)


class _FakeActivity:
    """Mínimo interlocutor: el servicio lee ``start_datetime`` (y, si existe,
    ``duration_hours`` para acotar la tolerancia a 20% de la duración)."""

    def __init__(self, start_datetime, duration_hours=None):
        self.start_datetime = start_datetime
        self.duration_hours = duration_hours


def _activity_start(delta: timedelta) -> _FakeActivity:
    return _FakeActivity(datetime.now(timezone.utc) + delta)


def test_window_reads_configured_minutes(app, monkeypatch):
    """Los dos settings (antes/después del inicio) gobiernan la ventana."""
    monkeypatch.setenv("APP_PUBLIC_SELF_REGISTER_OPEN_MINUTES_BEFORE_START", "45")
    monkeypatch.setenv("APP_PUBLIC_SELF_REGISTER_CLOSE_MINUTES_AFTER_START", "10")

    start = datetime(2026, 10, 5, 7, 0, tzinfo=timezone.utc)
    opens, closes = self_register_window(_FakeActivity(start))

    assert opens == start - timedelta(minutes=45)
    assert closes == start + timedelta(minutes=10)


def test_window_defaults_without_settings(app):
    start = datetime(2026, 10, 5, 7, 0, tzinfo=timezone.utc)
    opens, closes = self_register_window(_FakeActivity(start))

    assert opens == start - timedelta(minutes=30)
    assert closes == start + timedelta(minutes=15)


def test_window_closes_at_twenty_percent_of_a_short_activity(app):
    """Tolerancia = min(setting, 20% de la duración): 60 min -> 12, 4 h -> 15."""
    start = datetime(2026, 10, 5, 7, 0, tzinfo=timezone.utc)

    _opens, closes = self_register_window(_FakeActivity(start, duration_hours=1.0))
    assert closes == start + timedelta(minutes=12)

    _opens, closes = self_register_window(_FakeActivity(start, duration_hours=4.0))
    assert closes == start + timedelta(minutes=15)


def test_state_open_inside_window(app):
    # empieza en 5 min -> la ventana (abre -30 / cierra +15) ya está abierta
    state, opens_at, closes_at = self_register_state(
        _activity_start(timedelta(minutes=5))
    )

    assert state == OPEN
    assert opens_at is not None and closes_at is not None


def test_state_not_open_before_the_window(app):
    state, _opens_at, _closes_at = self_register_state(
        _activity_start(timedelta(hours=2))
    )

    assert state == NOT_OPEN


def test_state_closed_after_the_window(app):
    state, _opens_at, _closes_at = self_register_state(
        _activity_start(timedelta(hours=-3))
    )

    assert state == CLOSED


def test_activity_without_start_is_always_open(app):
    state, opens_at, closes_at = self_register_state(_FakeActivity(None))

    assert state == OPEN
    assert opens_at is None and closes_at is None


def test_messages_differ_between_states(app):
    future = datetime.now(timezone.utc) + timedelta(hours=2)
    past = datetime.now(timezone.utc) - timedelta(hours=2)

    not_open_msg = window_message(NOT_OPEN, future, future + timedelta(minutes=20))
    closed_msg = window_message(CLOSED, past - timedelta(minutes=30), past)
    open_msg = window_message(OPEN, None, None)

    assert open_msg is None
    assert not_open_msg is not None and "aún no abre" in not_open_msg
    assert closed_msg is not None and "terminó" in closed_msg
    # Copy visible para el estudiante: el módulo se llama "auto-registro".
    assert "auto-registro" in not_open_msg
    assert "auto-registro" in closed_msg
