"""Tests de la convención de escritura en BD: ``db_wall_local`` / ``db_now_local``.

Las columnas ``datetime`` de MySQL guardan el **wall time local** de la app y
al leerlas se interpretan como hora local (``safe_iso`` /
``localize_naive_datetime``). Guardar ``datetime.now(timezone.utc)`` (o
``db.func.now()`` con el servidor en UTC) dejaba en la columna una hora 6 h
posterior: la ventana de presencia salía invertida y el porcentaje de
asistencia salía 0 %.
"""

from datetime import datetime, timedelta, timezone

from app.utils.datetime_utils import (
    db_now_local,
    db_wall_local,
    localize_naive_datetime,
)

APP_TZ = "America/Mexico_City"
# Mexico City no aplica DST desde 2022: UTC-6 todo el año.
UTC_MINUS_6 = timezone(timedelta(hours=-6))


def test_naive_datetime_is_kept_as_is():
    """Un naive ya está en hora local (convención de la BD): no se mueve."""
    naive = datetime(2025, 10, 7, 15, 19, 55)

    stored = db_wall_local(naive, APP_TZ)

    assert stored == naive
    assert stored.tzinfo is None


def test_aware_utc_is_stored_as_local_wall_time():
    aware = datetime(2025, 10, 7, 15, 19, 55, tzinfo=timezone.utc)

    stored = db_wall_local(aware, APP_TZ)

    assert stored.tzinfo is None
    # 15:19 UTC = 09:19 hora de México: es la hora real en la que ocurrió
    assert stored == datetime(2025, 10, 7, 9, 19, 55)


def test_aware_offset_payload_keeps_its_wall_time():
    """Un payload con -06:00 ya trae la hora local del cliente."""
    aware = datetime(2025, 10, 7, 9, 19, 55, tzinfo=UTC_MINUS_6)

    assert db_wall_local(aware, APP_TZ) == datetime(2025, 10, 7, 9, 19, 55)


def test_write_then_read_recovers_the_original_instant():
    """Escribir con ``db_wall_local`` y leer como local devuelve el instante."""
    aware = datetime(2025, 10, 7, 15, 19, 55, tzinfo=timezone.utc)

    stored = db_wall_local(aware, APP_TZ)
    read_back = localize_naive_datetime(stored, APP_TZ)

    assert read_back == aware


def test_non_datetime_values_pass_through():
    assert db_wall_local(None, APP_TZ) is None
    assert db_wall_local("2025-10-07 10:00:00", APP_TZ) == "2025-10-07 10:00:00"
    assert db_wall_local(42, APP_TZ) == 42


def test_db_now_local_is_naive_and_close_to_now():
    stored = db_now_local(APP_TZ)

    assert isinstance(stored, datetime)
    assert stored.tzinfo is None

    recovered = localize_naive_datetime(stored, APP_TZ)
    drift = abs((datetime.now(timezone.utc) - recovered).total_seconds())
    assert drift < 60
