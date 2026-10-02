"""Tests del servicio unificado de cálculo de horas (fuente única de verdad).

Cubre la semántica combinada:
- Registration (Confirmado/Asistió) + Attendance (Asistió / walk-ins).
- Dedup por actividad cuando existen ambas fuentes.
- Redondeo a 2 decimales antes de comparar umbrales.
- Desglose por evento y filtros.
"""

from datetime import datetime, timedelta

from app import db
from app.models.activity import Activity
from app.models.attendance import Attendance
from app.models.event import Event
from app.models.registration import Registration
from app.models.student import Student
from app.services.hours_service import (
    CREDIT_MIN_HOURS,
    compute_student_hours,
    meets_credit_threshold,
)


# ---------------------------------------------------------------------------
# helpers de fixtures locales
# ---------------------------------------------------------------------------


def _make_event(name="Evento Horas"):
    event = Event(
        name=name,
        start_date=datetime(2025, 10, 1, 8, 0, 0),
        end_date=datetime(2025, 10, 5, 18, 0, 0),
        is_active=True,
    )
    db.session.add(event)
    db.session.flush()
    return event


def _make_student(control, name, career="Ingeniería en Sistemas", email=None):
    student = Student(
        control_number=control,
        full_name=name,
        career=career,
        email=email or f"{control.lower()}@test.com",
    )
    db.session.add(student)
    db.session.flush()
    return student


def _make_activity(event, hours, name="Actividad"):
    activity = Activity(
        event_id=event.id,
        department="TEST",
        name=name,
        start_datetime=datetime(2025, 10, 1, 10, 0, 0),
        end_datetime=datetime(2025, 10, 1, 10, 0, 0) + timedelta(hours=hours),
        duration_hours=hours,
        activity_type="Taller",
        location="Salón",
        modality="Presencial",
    )
    db.session.add(activity)
    db.session.flush()
    return activity


def _register(student, activity, status):
    reg = Registration(
        student_id=student.id, activity_id=activity.id, status=status
    )
    db.session.add(reg)
    db.session.flush()
    return reg


def _attend(student, activity, status="Asistió"):
    att = Attendance(
        student_id=student.id,
        activity_id=activity.id,
        check_in_time=datetime(2025, 10, 1, 10, 0, 0),
        status=status,
        attendance_percentage=100.0,
    )
    db.session.add(att)
    db.session.flush()
    return att


# ---------------------------------------------------------------------------
# meets_credit_threshold
# ---------------------------------------------------------------------------


def test_meets_credit_threshold_rounding():
    """El umbral se compara sobre el total redondeado a 2 decimales."""
    assert meets_credit_threshold(10.0) is True
    assert meets_credit_threshold(9.999999999) is True  # round -> 10.0
    assert meets_credit_threshold(9.996) is True  # round -> 10.0
    assert meets_credit_threshold(9.994) is False  # round -> 9.99
    assert meets_credit_threshold(9.5) is False
    assert meets_credit_threshold(None) is False
    assert meets_credit_threshold("no-numerico") is False


def test_meets_credit_threshold_custom_threshold():
    assert meets_credit_threshold(5.0, threshold=5.0) is True
    assert meets_credit_threshold(4.99, threshold=5.0) is False


def test_credit_min_hours_constant():
    assert CREDIT_MIN_HOURS == 10.0


# ---------------------------------------------------------------------------
# semántica de conteo
# ---------------------------------------------------------------------------


def test_counts_confirmed_and_asistio_not_registrado(app):
    """Registration: 'Confirmado' y 'Asistió' cuentan; 'Registrado' no."""
    with app.app_context():
        event = _make_event()
        student = _make_student("H001", "Estudiante Uno")
        _register(student, _make_activity(event, 3.0, "A1"), "Confirmado")
        _register(student, _make_activity(event, 5.0, "A2"), "Asistió")
        _register(student, _make_activity(event, 2.0, "A3"), "Registrado")
        db.session.commit()

        rows = compute_student_hours(event_ids=[event.id])
        assert len(rows) == 1
        assert rows[0]["total_hours"] == 8.0
        assert rows[0]["activities_count"] == 2


def test_excludes_cancelled_registrations(app):
    with app.app_context():
        event = _make_event()
        student = _make_student("H002", "Estudiante Dos")
        _register(student, _make_activity(event, 4.0), "Cancelado")
        db.session.commit()

        rows = compute_student_hours(event_ids=[event.id])
        assert rows == []


def test_walkin_attendance_counts_without_registration(app):
    """Un estudiante solo con Attendance (walk-in) cuenta hacia las horas."""
    with app.app_context():
        event = _make_event()
        student = _make_student("H003", "Estudiante Walkin")
        _attend(student, _make_activity(event, 6.0))
        _attend(student, _make_activity(event, 4.0))
        db.session.commit()

        rows = compute_student_hours(event_ids=[event.id])
        assert len(rows) == 1
        assert rows[0]["id"] == student.id
        assert rows[0]["total_hours"] == 10.0
        assert rows[0]["activities_count"] == 2


def test_attendance_not_asistio_status_excluded(app):
    """Attendance en 'Ausente'/'Parcial' no acredita horas."""
    with app.app_context():
        event = _make_event()
        student = _make_student("H004", "Estudiante Cuatro")
        _attend(student, _make_activity(event, 8.0), status="Ausente")
        _attend(student, _make_activity(event, 8.0), status="Parcial")
        db.session.commit()

        rows = compute_student_hours(event_ids=[event.id])
        assert rows == []


def test_dedup_registration_and_attendance_same_activity(app):
    """La misma actividad con Registration y Attendance cuenta UNA sola vez."""
    with app.app_context():
        event = _make_event()
        student = _make_student("H005", "Estudiante Cinco")
        activity = _make_activity(event, 6.0)
        _register(student, activity, "Asistió")
        _attend(student, activity)  # misma actividad: no debe duplicar
        db.session.commit()

        rows = compute_student_hours(event_ids=[event.id])
        assert len(rows) == 1
        assert rows[0]["total_hours"] == 6.0
        assert rows[0]["activities_count"] == 1


def test_float_sum_meets_threshold_after_rounding(app):
    """4.4 + 5.6 (suma con ruido de punto flotante) alcanza el umbral."""
    with app.app_context():
        event = _make_event()
        student = _make_student("H006", "Estudiante Seis")
        _register(student, _make_activity(event, 4.4), "Asistió")
        _register(student, _make_activity(event, 5.6), "Asistió")
        db.session.commit()

        rows = compute_student_hours(event_ids=[event.id], min_hours=CREDIT_MIN_HOURS)
        assert len(rows) == 1
        assert rows[0]["total_hours"] == 10.0
        assert meets_credit_threshold(rows[0]["total_hours"]) is True


# ---------------------------------------------------------------------------
# desglose por evento y filtros
# ---------------------------------------------------------------------------


def test_multi_event_breakdown(app):
    """El total combina eventos y hours_by_event conserva el desglose."""
    with app.app_context():
        ev_a = _make_event("Aniversario 45")
        ev_b = _make_event("Aniversario 46")
        student = _make_student("H007", "Estudiante Siete")
        _register(student, _make_activity(ev_a, 4.0), "Asistió")
        _register(student, _make_activity(ev_b, 6.0), "Asistió")
        db.session.commit()

        # Todos los eventos: total combinado
        rows = compute_student_hours(student_id=student.id)
        assert len(rows) == 1
        assert rows[0]["total_hours"] == 10.0
        assert rows[0]["hours_by_event"] == {ev_a.id: 4.0, ev_b.id: 6.0}
        assert rows[0]["activities_by_event"] == {ev_a.id: 1, ev_b.id: 1}

        # Filtrado por un solo evento: solo sus horas
        rows_a = compute_student_hours(student_id=student.id, event_ids=[ev_a.id])
        assert rows_a[0]["total_hours"] == 4.0
        assert rows_a[0]["hours_by_event"] == {ev_a.id: 4.0}


def test_career_filter_is_case_insensitive_substring(app):
    with app.app_context():
        event = _make_event()
        s1 = _make_student("H008", "Ana", career="Ingeniería en Sistemas Computacionales")
        s2 = _make_student("H009", "Beto", career="Ingeniería Mecánica")
        _register(student=s1, activity=_make_activity(event, 11.0), status="Asistió")
        _register(student=s2, activity=_make_activity(event, 11.0), status="Asistió")
        db.session.commit()

        rows = compute_student_hours(
            event_ids=[event.id], career="sistemas computacionales"
        )
        assert len(rows) == 1
        assert rows[0]["control_number"] == "H008"


def test_search_filter_by_control_or_name(app):
    with app.app_context():
        event = _make_event()
        s1 = _make_student("H010", "Carlos Perez")
        s2 = _make_student("H011", "Maria Lopez")
        _register(s1, _make_activity(event, 2.0), "Asistió")
        _register(s2, _make_activity(event, 3.0), "Asistió")
        db.session.commit()

        by_control = compute_student_hours(event_ids=[event.id], search="h010")
        assert len(by_control) == 1
        assert by_control[0]["control_number"] == "H010"

        by_name = compute_student_hours(event_ids=[event.id], search="lopez")
        assert len(by_name) == 1
        assert by_name[0]["control_number"] == "H011"


def test_min_hours_filter_uses_rounded_total(app):
    with app.app_context():
        event = _make_event()
        s1 = _make_student("H012", "Alumnos Con Horas")
        s2 = _make_student("H013", "Alumnos Sin Horas")
        _register(s1, _make_activity(event, 10.0), "Asistió")
        _register(s2, _make_activity(event, 9.0), "Asistió")
        db.session.commit()

        rows = compute_student_hours(event_ids=[event.id], min_hours=10.0)
        assert len(rows) == 1
        assert rows[0]["control_number"] == "H012"

        # min_hours=0 incluye también a los que tienen participaciones
        all_rows = compute_student_hours(event_ids=[event.id], min_hours=0)
        assert len(all_rows) == 2


def test_results_sorted_by_full_name(app):
    with app.app_context():
        event = _make_event()
        _register(_make_student("H014", "Zeta"), _make_activity(event, 1.0), "Asistió")
        _register(_make_student("H015", "Alfa"), _make_activity(event, 2.0), "Asistió")
        db.session.commit()

        rows = compute_student_hours(event_ids=[event.id])
        names = [r["full_name"] for r in rows]
        assert names == sorted(names)
