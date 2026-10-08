"""Tests de los overrides manuales de crédito complementario (credit_overrides).

Cubre el CRUD de overrides y su efecto en GET /api/students/complementary-credits
(exclusión/inclusión forzada de la lista).
"""

from datetime import datetime, timedelta

from app import db
from app.models.activity import Activity
from app.models.event import Event
from app.models.registration import Registration
from app.models.student import Student


# ---------------------------------------------------------------------------
# helpers locales
# ---------------------------------------------------------------------------


def _create_event(app, name="Evento Override"):
    with app.app_context():
        event = Event(
            name=name,
            description="Test overrides",
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=7),
            is_active=True,
        )
        db.session.add(event)
        db.session.commit()
        return event.id


def _create_student(app, control, name, career="Ingeniería en Sistemas"):
    with app.app_context():
        student = Student(
            control_number=control,
            full_name=name,
            career=career,
            email=f"{control.lower()}@test.com",
        )
        db.session.add(student)
        db.session.commit()
        return student.id


def _add_participation(app, student_id, event_id, hours, name="Act Override"):
    with app.app_context():
        activity = Activity(
            event_id=event_id,
            department="TEST",
            name=name,
            description="Test",
            start_datetime=datetime.now(),
            end_datetime=datetime.now() + timedelta(hours=hours),
            duration_hours=hours,
            activity_type="Conferencia",
            location="Test",
            modality="Presencial",
        )
        db.session.add(activity)
        db.session.flush()
        db.session.add(
            Registration(
                student_id=student_id, activity_id=activity.id, status="Asistió"
            )
        )
        db.session.commit()
        return activity.id


def _post_override(client, auth_headers, payload):
    return client.post(
        "/api/students/credit-overrides",
        json=payload,
        headers=auth_headers,
    )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def test_list_credit_overrides_empty(client, auth_headers):
    resp = client.get("/api/students/credit-overrides", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["overrides"] == []
    assert data["total"] == 0


def test_upsert_update_and_delete_override(app, client, auth_headers):
    student_id = _create_student(app, "OV001", "Alumno Override")

    # Crear
    resp = _post_override(
        client,
        auth_headers,
        {"student_id": student_id, "decision": "include", "reason": "Verificado"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["override"]["decision"] == "include"

    # Actualizar (upsert: sigue habiendo una sola fila)
    resp = _post_override(
        client, auth_headers, {"student_id": student_id, "decision": "exclude"}
    )
    assert resp.status_code == 200
    assert resp.get_json()["override"]["decision"] == "exclude"

    # Listar: una sola fila, decision actualizado, reason limpiado
    resp = client.get("/api/students/credit-overrides", headers=auth_headers)
    data = resp.get_json()
    assert data["total"] == 1
    assert data["overrides"][0]["student_id"] == student_id
    assert data["overrides"][0]["decision"] == "exclude"
    assert data["overrides"][0]["reason"] is None
    assert data["overrides"][0]["control_number"] == "OV001"
    assert data["overrides"][0]["full_name"] == "Alumno Override"

    # Eliminar
    resp = client.delete(
        f"/api/students/credit-overrides/{student_id}", headers=auth_headers
    )
    assert resp.status_code == 200

    resp = client.get("/api/students/credit-overrides", headers=auth_headers)
    assert resp.get_json()["total"] == 0

    # Eliminar de nuevo → 404
    resp = client.delete(
        f"/api/students/credit-overrides/{student_id}", headers=auth_headers
    )
    assert resp.status_code == 404


def test_upsert_override_validations(app, client, auth_headers):
    student_id = _create_student(app, "OV002", "Alumno Validado")

    # student_id ausente
    resp = _post_override(client, auth_headers, {"decision": "include"})
    assert resp.status_code == 400
    assert "student_id" in resp.get_json()["message"]

    # student_id no numérico
    resp = _post_override(
        client, auth_headers, {"student_id": "abc", "decision": "include"}
    )
    assert resp.status_code == 400

    # decisión inválida
    resp = _post_override(
        client, auth_headers, {"student_id": student_id, "decision": "maybe"}
    )
    assert resp.status_code == 400
    assert "include" in resp.get_json()["message"]

    # estudiante inexistente
    resp = _post_override(
        client, auth_headers, {"student_id": 99999, "decision": "include"}
    )
    assert resp.status_code == 404

    # reason demasiado largo
    resp = _post_override(
        client,
        auth_headers,
        {"student_id": student_id, "decision": "include", "reason": "x" * 256},
    )
    assert resp.status_code == 400

    # Nada quedó guardado
    resp = client.get("/api/students/credit-overrides", headers=auth_headers)
    assert resp.get_json()["total"] == 0


def test_credit_overrides_require_auth(client):
    resp = client.get("/api/students/credit-overrides")
    assert resp.status_code == 401

    resp = client.post("/api/students/credit-overrides", json={"decision": "include"})
    assert resp.status_code == 401

    resp = client.delete("/api/students/credit-overrides/1")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# efecto en la lista de créditos
# ---------------------------------------------------------------------------


def test_override_exclude_removes_student_from_credits_list(app, client, auth_headers):
    """'exclude' omite incluso a un estudiante que cumple la regla."""
    event_id = _create_event(app)
    student_id = _create_student(app, "OV010", "Alumno Excluido")
    _add_participation(app, student_id, event_id, 12.0)

    # Sin override: aparece (12h, cruce en el único evento)
    resp = client.get(
        f"/api/students/complementary-credits?event_id={event_id}",
        headers=auth_headers,
    )
    data = resp.get_json()
    assert data["total_students"] == 1

    # Con override 'exclude': desaparece y se cuenta en excluded_by_override
    resp = _post_override(
        client, auth_headers, {"student_id": student_id, "decision": "exclude"}
    )
    assert resp.status_code == 200

    resp = client.get(
        f"/api/students/complementary-credits?event_id={event_id}",
        headers=auth_headers,
    )
    data = resp.get_json()
    assert data["total_students"] == 0
    assert data["excluded_by_override"] == 1
    assert data["excluded_already_credited"] == 0

    # Al eliminar el override vuelve a aparecer
    client.delete(f"/api/students/credit-overrides/{student_id}", headers=auth_headers)
    resp = client.get(
        f"/api/students/complementary-credits?event_id={event_id}",
        headers=auth_headers,
    )
    assert resp.get_json()["total_students"] == 1


def test_override_include_forces_early_crossed_student(app, client, auth_headers):
    """'include' fuerza la inclusión aunque la regla derivada lo excluya."""
    ev1 = _create_event(app, "Override Crono 1")
    ev2 = _create_event(app, "Override Crono 2")
    student_id = _create_student(app, "OV011", "Alumno Forzado")
    _add_participation(app, student_id, ev1, 12.0, name="Act Ev1")
    _add_participation(app, student_id, ev2, 3.0, name="Act Ev2")

    # Selección combinada: cruzó en ev1 (≠ último) → excluido por la regla
    resp = client.get(
        f"/api/students/complementary-credits?event_ids={ev1},{ev2}",
        headers=auth_headers,
    )
    data = resp.get_json()
    assert data["total_students"] == 0
    assert data["excluded_already_credited"] == 1

    # Con override 'include' se fuerza su inclusión
    resp = _post_override(
        client, auth_headers, {"student_id": student_id, "decision": "include"}
    )
    assert resp.status_code == 200

    resp = client.get(
        f"/api/students/complementary-credits?event_ids={ev1},{ev2}",
        headers=auth_headers,
    )
    data = resp.get_json()
    assert data["total_students"] == 1
    student = data["students"][0]
    assert student["control_number"] == "OV011"
    assert student["total_hours"] == 15.0
    assert data["excluded_already_credited"] == 0


def test_override_include_below_threshold(app, client, auth_headers):
    """'include' fuerza la inclusión aunque no alcance las 10 h."""
    event_id = _create_event(app, "Override Bajo Umbral")
    student_id = _create_student(app, "OV012", "Alumno Bajo Umbral")
    _add_participation(app, student_id, event_id, 7.0)

    # Sin override: no aparece
    resp = client.get(
        f"/api/students/complementary-credits?event_id={event_id}",
        headers=auth_headers,
    )
    assert resp.get_json()["total_students"] == 0

    # Con override 'include': aparece con sus 7 h reales
    _post_override(
        client, auth_headers, {"student_id": student_id, "decision": "include"}
    )
    resp = client.get(
        f"/api/students/complementary-credits?event_id={event_id}",
        headers=auth_headers,
    )
    data = resp.get_json()
    assert data["total_students"] == 1
    assert data["students"][0]["total_hours"] == 7.0
    assert data["students"][0]["has_complementary_credit"] is True


def test_override_include_without_participations(app, client, auth_headers):
    """'include' funciona incluso sin participaciones en la selección
    (fila sintética con 0 h)."""
    event_id = _create_event(app, "Override Sin Datos")
    student_id = _create_student(app, "OV013", "Alumno Sin Datos")

    _post_override(
        client, auth_headers, {"student_id": student_id, "decision": "include"}
    )

    resp = client.get(
        f"/api/students/complementary-credits?event_id={event_id}",
        headers=auth_headers,
    )
    data = resp.get_json()
    assert data["total_students"] == 1
    student = data["students"][0]
    assert student["control_number"] == "OV013"
    assert student["total_hours"] == 0.0
    assert student["activities_count"] == 0
    assert student["hours_by_event"] == {}
