"""Fórmula del % de asistencia: tolerancia de llegada, pausas y desborde.

Matriz de escenarios de negocio (documentada en
``docs/ATTENDANCE_PERCENTAGE.md``):

- A puntual y completo -> 100%.
- B llega dentro de la tolerancia y se queda hasta el final -> 100%.
- C la pausa resta, aunque el evento se desborde.
- D desfase compensado (llega tarde y el evento termina desfasado) -> 100%.
- E el perdón es incondicional (no exige llegar hasta el final).
- F sin regresiones: un puntual que se va antes acredita lo mismo que antes.
- G pausa >= duración -> 0% (Ausente), no la rescata ni el desborde.
"""

from datetime import datetime, timedelta

import pytest

from app import db
from app.models.activity import Activity
from app.models.attendance import Attendance
from app.services.attendance_service import (
    _arrival_utc,
    _ensure_utc,
    compute_attendance_metrics,
    resume_attendance,
)
from app.services.self_register_service import (
    arrival_tolerance_minutes,
    self_register_window,
)
from app.services.settings_manager import SettingsManager

# Conferencia de 60 min: 10:00 -> 11:00 (naive = wall time local, como la BD)
START = datetime(2024, 1, 1, 10, 0, 0)
END = datetime(2024, 1, 1, 11, 0, 0)


@pytest.fixture(autouse=True)
def _clean_settings_cache():
    """La caché de ``SettingsManager`` es de clase y sobrevive entre tests."""
    SettingsManager._cache.clear()
    yield
    SettingsManager._cache.clear()


@pytest.fixture
def conference(app, sample_data, activity_factory):
    """Conferencia de 60 min + una asistencia todavía sin check-in."""
    activity = activity_factory(
        name="Conferencia 60 min",
        start_datetime=START,
        end_datetime=END,
        duration_hours=1.0,
    )
    attendance = Attendance(
        student_id=sample_data["student_id"], activity_id=activity.id
    )
    db.session.add(attendance)
    db.session.commit()
    return {"activity_id": activity.id, "attendance_id": attendance.id}


def _mark(conference, arrival, leave=None, pause=None):
    """Asigna llegada (y salida / pausa opcional) y devuelve ``(fila, actividad)``.

    Tras el commit todo queda expirado y se relee **naive** desde la BD, que es
    la forma en que vive en producción (evita mezclar objetos aware recién
    creados con otros ya leídos).
    """
    attendance = db.session.get(Attendance, conference["attendance_id"])
    attendance.check_in_time = arrival
    if pause is not None:
        attendance.pause_time, attendance.resume_time = pause
    if leave is not None:
        attendance.check_out_time = leave
    db.session.commit()
    return (
        db.session.get(Attendance, conference["attendance_id"]),
        db.session.get(Activity, conference["activity_id"]),
    )


def _metrics(attendance, activity):
    return compute_attendance_metrics(attendance, activity)


# --- Tolerancia de llegada (puerta == perdón) -------------------------------


def test_tolerance_is_twenty_percent_of_duration(app, activity_factory):
    """min(configurado, 20% de la duración): 60 min -> 12, 30 min -> 6."""
    assert (
        arrival_tolerance_minutes(
            activity_factory(
                start_datetime=START,
                end_datetime=END,
                duration_hours=1.0,
            )
        )
        == 12
    )
    assert (
        arrival_tolerance_minutes(
            activity_factory(
                start_datetime=START,
                end_datetime=START + timedelta(minutes=30),
                duration_hours=0.5,
            )
        )
        == 6
    )


def test_tolerance_falls_back_to_setting_without_duration(app):
    """Sin duración conocida manda el setting (default 15)."""

    class _SinDuracion:
        start_datetime = START

    assert arrival_tolerance_minutes(_SinDuracion()) == 15
    assert arrival_tolerance_minutes(None) == 15


def test_tolerance_is_still_capped_by_the_setting(app, activity_factory, monkeypatch):
    """El setting sigue siendo un tope: 4 h no amplía la tolerancia a 48 min."""
    monkeypatch.setenv("APP_PUBLIC_SELF_REGISTER_CLOSE_MINUTES_AFTER_START", "10")
    largo = activity_factory(
        start_datetime=START,
        end_datetime=START + timedelta(hours=4),
        duration_hours=4.0,
    )
    assert arrival_tolerance_minutes(largo) == 10


def test_window_and_percentage_share_the_same_tolerance(
    app, conference, activity_factory
):
    """La puerta del auto-registro cierra exactamente donde empieza el perdón."""
    activity = db.session.get(Activity, conference["activity_id"])
    abre, cierra = self_register_window(activity)
    # abre = inicio - 30, cierra = inicio + 12 (tolerancia de la conferencia)
    assert cierra - abre == timedelta(minutes=42)
    assert cierra - _ensure_utc(START) == timedelta(minutes=12)


# --- Matriz de escenarios ---------------------------------------------------


def test_a_llega_antes_y_se_hasta_el_final(app, conference):
    """A: 100%."""
    attendance, activity = _mark(conference, START, END)
    assert _metrics(attendance, activity) == (100.0, "Asistió")


def test_b_llega_dentro_de_la_tolerancia(app, conference):
    """B: llega +12 (dentro de la tolerancia de 12 min) y se queda -> 100%."""
    attendance, activity = _mark(conference, START + timedelta(minutes=12), END)
    assert _metrics(attendance, activity) == (100.0, "Asistió")


def test_b_fuera_de_la_tolerancia_sigue_contando_el_retraso(app, conference):
    """+30 min: sólo se perdonan los primeros 12 -> 42/60 = 70% (Parcial)."""
    attendance, activity = _mark(conference, START + timedelta(minutes=30), END)
    assert _metrics(attendance, activity) == (70.0, "Parcial")


def test_d_desfase_compensado(app, conference):
    """D: llega +10 y el evento termina +10 -> presencia 50 + perdón 10 = 100%."""
    attendance, activity = _mark(
        conference, START + timedelta(minutes=10), END + timedelta(minutes=10)
    )
    assert _metrics(attendance, activity) == (100.0, "Asistió")


def test_e_perdon_incondicional_con_salida_temprana(app, conference):
    """E: perdón incondicional: no exige haber llegado hasta el final."""
    attendance, activity = _mark(
        conference, START + timedelta(minutes=12), END - timedelta(minutes=5)
    )
    # presencia 43 + perdón 12 = 55/60 = 91.67%
    assert _metrics(attendance, activity) == (91.67, "Asistió")


def test_f_sin_regresiones_para_el_puntual(app, conference):
    """F: el que llega a tiempo y se va antes acredita lo mismo que siempre."""
    attendance, activity = _mark(conference, START, END - timedelta(minutes=5))
    assert _metrics(attendance, activity) == (91.67, "Asistió")


def test_c_la_pausa_resta_aunque_el_evento_se_desborde(app, conference):
    """C: pausa de 20 min y check-out 20 min tarde -> 40/60 = 66.67%."""
    attendance, activity = _mark(
        conference,
        START,
        END + timedelta(minutes=20),
        pause=(START + timedelta(minutes=20), START + timedelta(minutes=40)),
    )
    assert _metrics(attendance, activity) == (66.67, "Parcial")


def test_c_llegada_tarde_y_pausa_solo_perdona_el_retraso(app, conference):
    """C': +10 de llegada y 20 de pausa -> (50 - 20 + 10) = 40/60 = 66.67%."""
    attendance, activity = _mark(
        conference,
        START + timedelta(minutes=10),
        END,
        pause=(START + timedelta(minutes=20), START + timedelta(minutes=40)),
    )
    assert _metrics(attendance, activity) == (66.67, "Parcial")


def test_g_pausa_igual_a_la_duración_es_ausente(app, conference):
    """G: pausa >= duración -> 0% aunque la presencia llegue al final."""
    attendance, activity = _mark(conference, START, END, pause=(START, END))
    assert _metrics(attendance, activity) == (0.0, "Ausente")


def test_el_credito_nunca_supera_el_100_por_ciento(app, activity_factory):
    """El tope evita que presencia + perdón se desborde de la duración."""
    activity = activity_factory(
        start_datetime=START, end_datetime=END, duration_hours=1.0
    )
    attendance = Attendance(
        check_in_time=START,  # presencia completa...
        check_out_time=END,
        arrival_time=START + timedelta(minutes=12),  # ...pero llegó tarde
    )
    assert _metrics(attendance, activity) == (100.0, "Asistió")


# --- arrival_time -----------------------------------------------------------


def test_arrival_time_freezes_on_first_check_in(app, conference):
    """La llegada se congela al primer check-in y se lee desde la BD."""
    attendance, _ = _mark(conference, START + timedelta(minutes=7), END)
    assert attendance.arrival_time == START + timedelta(minutes=7)
    assert attendance.arrival_time == attendance.check_in_time


def test_arrival_time_survives_a_pause_fold(app, conference):
    """``resume_attendance`` desplaza el check-in; la llegada no se mueve."""
    attendance, activity = _mark(
        conference,
        START,
        END,
        pause=(START + timedelta(minutes=30), None),
    )
    attendance.is_paused = True
    db.session.commit()

    resume_attendance(conference["attendance_id"])
    db.session.commit()

    attendance = db.session.get(Attendance, conference["attendance_id"])
    # El check-in quedó plegado 30 min (por eso ya no sirve para medir atraso)
    assert attendance.check_in_time == START + timedelta(minutes=30)
    assert attendance.arrival_time == START
    # Con check-in plegado y llegada real, la presencia sigue en 30 min
    activity = db.session.get(Activity, conference["activity_id"])
    assert _metrics(attendance, activity) == (50.0, "Parcial")


def test_arrival_time_falls_back_to_the_earliest_evidence(app, activity_factory):
    """Filas viejas (sin ``arrival_time``): min(created_at, check_in_time)."""
    activity = activity_factory(
        start_datetime=START, end_datetime=END, duration_hours=1.0
    )
    attendance = Attendance(
        check_in_time=START + timedelta(minutes=30),  # plegado por pausas
        check_out_time=END,
        arrival_time=None,
        created_at=START,
    )
    assert _arrival_utc(attendance) == _ensure_utc(START)
    # Sin llegada tardía no hay perdón: 30/60 = 50%
    assert _metrics(attendance, activity) == (50.0, "Parcial")
