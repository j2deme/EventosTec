"""Clasificación del backfill UTC → hora local de `attendances.created_at`.

`tools/backfill_attendance_created_at_local.py` decide fila por fila si el
timestamp está en hora UTC (hay que restarle el desfase), ya está en hora
local o no hay señal. Estos tests cubren esa decisión sin tocar la BD.
"""

import importlib.util
from datetime import datetime, timedelta
from pathlib import Path

_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "backfill_attendance_created_at_local.py"
)


def _load_tool():
    spec = importlib.util.spec_from_file_location("backfill_attendance_tool", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tool = _load_tool()

CUTOFF = datetime(2026, 10, 8, 12, 0, 0)
OFF = 6  # horas: America/Mexico_City (UTC-6)
# Actividad del mediodía: 10:00 → 14:00 (hora local naive)
WINDOW = (datetime(2026, 10, 7, 10, 0, 0), datetime(2026, 10, 7, 14, 0, 0))


def test_created_plus_offset_is_confirmed_utc():
    """created_at = check_in_time + 6 h → columna en UTC, corregible."""
    check_in = datetime(2026, 10, 7, 13, 19, 0)  # hora local real
    created = check_in + timedelta(hours=OFF)  # lo que dejó db.func.now()

    cls, motivo = tool.classify(created, check_in, OFF, CUTOFF, WINDOW)

    assert cls == "utc_confirmed"
    assert tool.should_fix(cls, tool.DEFAULT_CLASSES) is True
    assert "check_in_time" in motivo


def test_created_minus_offset_is_local():
    """created_at = check_in_time − 6 h → ya está en hora local: no tocar."""
    check_in = datetime(2026, 10, 7, 13, 19, 0)
    created = check_in - timedelta(hours=OFF)

    cls, _ = tool.classify(created, check_in, OFF, CUTOFF, WINDOW)

    assert cls == "local_confirmed"
    assert tool.should_fix(cls, tool.DEFAULT_CLASSES) is False


def test_window_decides_when_check_in_matches_created():
    """Mismo reloj en check_in y created_at: la ventana de la actividad decide."""
    # Check-in real 13:19 local, guardado en UTC (19:19) → fuera de la ventana
    stored_utc = datetime(2026, 10, 7, 19, 19, 0)
    check_in = stored_utc  # filas viejas: ambos en UTC

    cls, _ = tool.classify(stored_utc, check_in, OFF, CUTOFF, WINDOW)
    assert cls == "utc_confirmed"

    # Mismo caso ya en hora local (11:05): dentro de la ventana → no tocar
    stored_local = datetime(2026, 10, 7, 11, 5, 0)
    cls, _ = tool.classify(stored_local, stored_local, OFF, CUTOFF, WINDOW)
    assert cls == "local_confirmed"


def test_window_without_check_in_still_decides():
    """Sin check_in_time la ventana de la actividad sigue decidiendo."""
    cls, _ = tool.classify(datetime(2026, 10, 7, 19, 19, 0), None, OFF, CUTOFF, WINDOW)
    assert cls == "utc_confirmed"

    cls, _ = tool.classify(datetime(2026, 10, 7, 11, 5, 0), None, OFF, CUTOFF, WINDOW)
    assert cls == "local_confirmed"


def test_no_signal_is_ambiguous_and_fixed_by_default():
    """Sin señal: se corrige por defecto (la columna solo se escribió en UTC)."""
    cls, motivo = tool.classify(datetime(2026, 10, 6, 8, 0, 0), None, OFF, CUTOFF, None)

    assert cls == "ambiguous"
    assert "ventana" in motivo
    assert tool.should_fix(cls, tool.DEFAULT_CLASSES) is True
    assert tool.should_fix(cls, tool.STRICT_CLASSES) is False


def test_long_activity_is_ambiguous():
    """Actividad muy larga: ambas interpretaciones caben → ambigua."""
    long_activity = (datetime(2026, 10, 7, 6, 0, 0), datetime(2026, 10, 7, 20, 0, 0))
    created = datetime(2026, 10, 7, 15, 0, 0)

    cls, motivo = tool.classify(created, created, OFF, CUTOFF, long_activity)

    assert cls == "ambiguous"
    assert "ambas interpretaciones" in motivo


def test_rows_after_cutoff_are_left_untouched():
    """Lo escrito después del corte no se toca, ni aunque sea ambiguo."""
    created = datetime(2026, 10, 9, 9, 0, 0)

    cls, _ = tool.classify(created, created, OFF, CUTOFF, WINDOW)

    assert cls == "post_cutoff"
    assert tool.should_fix(cls, tool.DEFAULT_CLASSES) is False


def test_offset_is_computed_from_app_timezone():
    """El desfase se calcula con la zona de la app, no está hardcodeado."""
    naive_utc = datetime(2026, 10, 7, 19, 19, 0)
    assert tool.local_offset_hours(naive_utc, "America/Mexico_City") == 6
    assert tool.local_offset_hours(naive_utc, "UTC") == 0
