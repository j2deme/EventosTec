"""Tests de GET /api/events/<id>/calendar (vista calendario del admin)."""

import json
from datetime import datetime

from app.models.event import Event
from app.models.activity import Activity
from app.models.student import Student
from app.models.registration import Registration


def _make_event(db_session, start, end, name="Evento Calendario"):
    event = Event(name=name, start_date=start, end_date=end, is_active=True)
    db_session.add(event)
    db_session.commit()
    return event


def _make_activity(db_session, event_id, name, start, end, **kw):
    activity = Activity(
        event_id=event_id,
        department=kw.pop("department", "ISC"),
        name=name,
        start_datetime=start,
        end_datetime=end,
        duration_hours=kw.pop("duration_hours", 1.0),
        activity_type=kw.pop("activity_type", "Taller"),
        location=kw.pop("location", "Salón 1"),
        modality=kw.pop("modality", "Presencial"),
        **kw,
    )
    db_session.add(activity)
    db_session.commit()
    return activity


def test_calendar_requires_auth(client):
    """Sin token JWT → 401."""
    response = client.get("/api/events/1/calendar")
    assert response.status_code == 401


def test_calendar_unknown_event_returns_404(client, auth_headers):
    response = client.get("/api/events/999999/calendar", headers=auth_headers)
    assert response.status_code == 404


def test_calendar_days_and_activities(client, auth_headers, db_session):
    """Ventana de 3 días: solo días CON actividades; horas locales de pared."""
    event = _make_event(
        db_session,
        datetime(2026, 10, 6, 9, 0),
        datetime(2026, 10, 8, 17, 0),
    )
    _make_activity(
        db_session,
        event.id,
        "Introducción al Uso de AutoCAD",
        datetime(2026, 10, 7, 13, 0),
        datetime(2026, 10, 7, 14, 0),
        activity_type="Curso",
    )
    _make_activity(
        db_session,
        event.id,
        "Maniobras Básicas en Campo C",
        datetime(2026, 10, 7, 9, 0),
        datetime(2026, 10, 7, 10, 0),
    )
    _make_activity(
        db_session,
        event.id,
        "Posterior a la ventana",
        datetime(2026, 10, 20, 8, 0),
        datetime(2026, 10, 20, 9, 0),
    )

    response = client.get(f"/api/events/{event.id}/calendar", headers=auth_headers)
    assert response.status_code == 200
    data = json.loads(response.data)

    # Evento y días
    assert data["event"]["id"] == event.id
    assert data["event"]["start_date"] == "2026-10-06"
    assert data["event"]["end_date"] == "2026-10-08"
    # Solo el día 2026-10-07 tiene actividades: 10-06 y 10-08 (vacíos) se
    # omiten del grid; 10-20 queda fuera de la ventana y no genera columna
    assert data["days"] == ["2026-10-07"]

    # Actividades: todas incluidas, ordenadas por hora de inicio
    assert data["total_activities"] == 3
    assert [a["name"] for a in data["activities"]] == [
        "Maniobras Básicas en Campo C",
        "Introducción al Uso de AutoCAD",
        "Posterior a la ventana",
    ]

    by_name = {a["name"]: a for a in data["activities"]}
    autocad = by_name["Introducción al Uso de AutoCAD"]
    # Hora local de pared (sin conversión tz): 13:00-14:00 en la BD, 13:00 en la UI
    assert autocad["day"] == "2026-10-07"
    assert autocad["starts_at"] == "13:00"
    assert autocad["ends_at"] == "14:00"
    assert autocad["registered_count"] == 0
    # Sesión única (actividad de un solo día): 1/1
    assert autocad["session_index"] == 1
    assert autocad["session_total"] == 1

    # La actividad fuera de la ventana conserva su fecha real (la UI la lista
    # en el bloque de "fuera de ventana")
    assert by_name["Posterior a la ventana"]["day"] == "2026-10-20"


def test_calendar_registered_count_uses_registrado_status(
    client, auth_headers, db_session
):
    """registered_count usa la misma semántica de cupo que is_registration_allowed:
    solo cuenta status == 'Registrado' (un 'Cancelado' no ocupa cupo)."""
    event = _make_event(
        db_session,
        datetime(2026, 10, 6, 9, 0),
        datetime(2026, 10, 6, 17, 0),
    )
    activity = _make_activity(
        db_session,
        event.id,
        "Taller con cupo",
        datetime(2026, 10, 6, 10, 0),
        datetime(2026, 10, 6, 12, 0),
        max_capacity=30,
    )

    s1 = Student(control_number="CAL001", full_name="Estudiante Uno")
    s2 = Student(control_number="CAL002", full_name="Estudiante Dos")
    db_session.add_all([s1, s2])
    db_session.commit()

    db_session.add_all(
        [
            Registration(
                student_id=s1.id, activity_id=activity.id, status="Registrado"
            ),
            Registration(student_id=s2.id, activity_id=activity.id, status="Cancelado"),
        ]
    )
    db_session.commit()

    response = client.get(f"/api/events/{event.id}/calendar", headers=auth_headers)
    assert response.status_code == 200
    data = json.loads(response.data)

    assert len(data["activities"]) == 1
    assert data["activities"][0]["registered_count"] == 1
    assert data["activities"][0]["max_capacity"] == 30


def test_calendar_without_activities(client, auth_headers, db_session):
    """Evento sin actividades: no hay días con actividades (days == [])."""
    event = _make_event(
        db_session,
        datetime(2026, 10, 6, 9, 0),
        datetime(2026, 10, 7, 17, 0),
    )

    response = client.get(f"/api/events/{event.id}/calendar", headers=auth_headers)
    assert response.status_code == 200
    data = json.loads(response.data)

    assert data["days"] == []
    assert data["activities"] == []
    assert data["total_activities"] == 0
    # El rango del evento sigue disponible para el encabezado
    assert data["event"]["start_date"] == "2026-10-06"
    assert data["event"]["end_date"] == "2026-10-07"


def test_calendar_multi_day_activity_expands_sessions(client, auth_headers, db_session):
    """Actividad multídía → una entrada por día (sesión) con el mismo
    horario fijo; `days` incluye todos los días ocupados; `total_activities`
    cuenta actividades únicas, no sesiones."""
    event = _make_event(
        db_session,
        datetime(2026, 10, 5, 9, 0),
        datetime(2026, 10, 9, 17, 0),
        name="Evento multisesión",
    )
    # Multidía: 7 oct 08:00 → 9 oct 16:00 (una sesión diaria 08:00-16:00)
    multi = _make_activity(
        db_session,
        event.id,
        "Hackathon 3 días",
        datetime(2026, 10, 7, 8, 0),
        datetime(2026, 10, 9, 16, 0),
    )
    # Día intermedio sin más actividades: sigue existiendo por la sesión
    _make_activity(
        db_session,
        event.id,
        "Charla única",
        datetime(2026, 10, 7, 10, 0),
        datetime(2026, 10, 7, 11, 0),
    )

    response = client.get(f"/api/events/{event.id}/calendar", headers=auth_headers)
    assert response.status_code == 200
    data = json.loads(response.data)

    # Días vacíos (10-05, 10-06) omitidos: solo quedan los días con sesiones
    assert data["days"] == ["2026-10-07", "2026-10-08", "2026-10-09"]

    # Actividad única contada una vez (no 3 sesiones)
    assert data["total_activities"] == 2
    assert len(data["activities"]) == 4  # 3 sesiones + 1 charla

    sessions = [a for a in data["activities"] if a["id"] == multi.id]
    assert [s["day"] for s in sessions] == ["2026-10-07", "2026-10-08", "2026-10-09"]
    # Mismo horario fijo en cada sesión (estrategia de la vista student)
    assert all(s["starts_at"] == "08:00" for s in sessions)
    assert all(s["ends_at"] == "16:00" for s in sessions)
    # Índices de sesión 1..n y metadatos heredados de la actividad
    assert [s["session_index"] for s in sessions] == [1, 2, 3]
    assert all(s["session_total"] == 3 for s in sessions)
    assert all(s["location"] == "Salón 1" for s in sessions)
    # La charla única también expone 1/1
    charla = next(a for a in data["activities"] if a["name"] == "Charla única")
    assert charla["session_index"] == 1
    assert charla["session_total"] == 1
