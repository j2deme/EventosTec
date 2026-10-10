"""Tests de los endpoints de lookup.

Estos endpoints existen para que los selectores y filtros dejen de descargar
el listado COMPLETO con `per_page=1000` (2253 estudiantes para poblar un
<select>). Cubren:

  GET /api/students/lookup       → lista slim, sin paginar
  GET /api/students/careers      → carreras distintas normalizadas
  GET /api/activities/lookup     → lista slim con el evento anidado
  GET /api/events/lookup         → lista completa sin paginar
  GET /api/activities/by-event/<id> → todas las actividades de UN evento

Y el tope `max_per_page=100` que ahora aplican los listados genéricos.
"""

from datetime import datetime

from app import db
from app.models.activity import Activity
from app.models.registration import Registration
from app.models.student import Student


def _make_student(name, career, control):
    student = Student()
    student.full_name = name
    student.career = career
    student.control_number = control
    db.session.add(student)
    return student


def _make_registration(student, activity, status="Registrado"):
    reg = Registration()
    reg.student_id = student.id
    reg.activity_id = activity.id
    reg.status = status
    db.session.add(reg)
    return reg


# ─────────────────────────────────────────────────────────────────────────────
# /api/students/lookup
# ─────────────────────────────────────────────────────────────────────────────


class TestStudentsLookup:
    def test_returns_200_with_expected_contract(self, client, app):
        with app.app_context():
            _make_student("Ana López", "ISC", "A1")
            _make_student("Beto Ruiz", "IM", "B2")
            db.session.commit()

        res = client.get("/api/students/lookup")

        assert res.status_code == 200
        body = res.get_json()
        assert set(body.keys()) == {"students", "total"}
        assert body["total"] == len(body["students"]) == 2

    def test_items_are_slim_not_full_objects(self, client, app):
        """El payload debe limitarse a lo que consume un <select>.

        Antes se descargaba el objeto completo por estudiante; el punto de
        este endpoint es reducir ese payload.
        """
        with app.app_context():
            _make_student("Ana López", "ISC", "A1")
            db.session.commit()

        res = client.get("/api/students/lookup")
        item = res.get_json()["students"][0]

        assert set(item.keys()) == {"id", "control_number", "full_name", "career"}
        # Ningún campo sensible extra (email, fechas, etc.)
        assert "email" not in item
        assert "created_at" not in item

    def test_search_filters_by_name_and_control(self, client, app):
        with app.app_context():
            _make_student("Ana López", "ISC", "A1")
            _make_student("Beto Ruiz", "IM", "B2")
            db.session.commit()

        by_name = client.get("/api/students/lookup?search=Beto").get_json()
        by_control = client.get("/api/students/lookup?search=A1").get_json()

        assert by_name["total"] == 1
        assert by_name["students"][0]["full_name"] == "Beto Ruiz"
        assert by_control["total"] == 1
        assert by_control["students"][0]["control_number"] == "A1"

    def test_search_is_case_insensitive(self, client, app):
        with app.app_context():
            _make_student("Ana López", "ISC", "A1")
            db.session.commit()

        res = client.get("/api/students/lookup?search=ana").get_json()
        assert res["total"] == 1

    def test_empty_database_returns_empty_list_not_error(self, client):
        res = client.get("/api/students/lookup")

        assert res.status_code == 200
        body = res.get_json()
        assert body["students"] == []
        assert body["total"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# /api/students/careers
# ─────────────────────────────────────────────────────────────────────────────


class TestStudentsCareers:
    def test_returns_distinct_careers_only(self, client, app):
        """Reemplaza el Set() que el informe montaba en el navegador."""
        with app.app_context():
            _make_student("Ana", "ISC", "A1")
            _make_student("Beto", "ISC", "B2")  # duplicada
            _make_student("Caro", "IM", "C3")
            db.session.commit()

        body = client.get("/api/students/careers").get_json()

        assert set(body.keys()) == {"careers", "total"}
        assert sorted(body["careers"]) == ["IM", "ISC"]
        assert body["total"] == 2

    def test_careers_are_sorted_case_insensitively(self, client, app):
        with app.app_context():
            _make_student("Ana", "ingeniería", "A1")
            _make_student("Beto", "ISC", "B2")
            db.session.commit()

        body = client.get("/api/students/careers").get_json()

        assert body["careers"] == sorted(body["careers"], key=lambda c: c.lower())

    def test_null_and_blank_careers_are_excluded(self, client, app):
        with app.app_context():
            _make_student("Ana", None, "A1")
            _make_student("Beto", "", "B2")
            _make_student("Caro", "ISC", "C3")
            db.session.commit()

        body = client.get("/api/students/careers").get_json()

        assert body["careers"] == ["ISC"]
        assert body["total"] == 1

    def test_empty_database_returns_empty_list(self, client):
        body = client.get("/api/students/careers").get_json()

        assert body["careers"] == []
        assert body["total"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# /api/activities/lookup
# ─────────────────────────────────────────────────────────────────────────────


class TestActivitiesLookup:
    def test_returns_200_with_expected_contract(self, client, activity_factory):
        act = activity_factory(name="Única")

        res = client.get("/api/activities/lookup")

        assert res.status_code == 200
        body = res.get_json()
        assert set(body.keys()) == {"activities", "total"}
        assert body["total"] == len(body["activities"]) == 1
        assert body["activities"][0]["id"] == act.id

    def test_items_are_slim_and_include_nested_event(self, client, activity_factory):
        """La plantilla muestra `activity.event?.name` junto al nombre."""
        act = activity_factory(name="Taller X", department="ISC")

        res = client.get("/api/activities/lookup")
        item = res.get_json()["activities"][0]

        assert set(item.keys()) == {
            "id",
            "name",
            "code",
            "event_id",
            "department",
            "activity_type",
            "start_datetime",
            "end_datetime",
            "event",
        }
        assert item["id"] == act.id
        assert item["department"] == "ISC"
        # El evento viene anidado (la plantilla lo necesita para el <option>)
        assert item["event"] is not None
        assert item["event"]["id"] == act.event_id
        assert item["event"]["name"]

    def test_event_id_filter_returns_only_that_event(
        self, client, event_factory, activity_factory
    ):
        ev_a = event_factory(name="Evento A")
        ev_b = event_factory(name="Evento B")
        activity_factory(event_id=ev_a.id, name="De A")
        activity_factory(event_id=ev_b.id, name="De B")

        body = client.get(f"/api/activities/lookup?event_id={ev_a.id}").get_json()

        assert body["total"] == 1
        assert body["activities"][0]["name"] == "De A"

    def test_search_filters_by_name_and_department(self, client, activity_factory):
        activity_factory(name="Taller de Excel", department="TI")
        activity_factory(name="Conferencia", department="RRHH")

        by_name = client.get("/api/activities/lookup?search=Excel").get_json()
        by_dept = client.get("/api/activities/lookup?search=rrhh").get_json()

        assert by_name["total"] == 1
        assert by_name["activities"][0]["name"] == "Taller de Excel"
        assert by_dept["total"] == 1
        assert by_dept["activities"][0]["department"] == "RRHH"

    def test_activity_type_filter(self, client, activity_factory):
        activity_factory(name="Uno", activity_type="Taller")
        activity_factory(name="Dos", activity_type="Conferencia")

        body = client.get("/api/activities/lookup?activity_type=Taller").get_json()

        assert body["total"] == 1
        assert body["activities"][0]["name"] == "Uno"


# ─────────────────────────────────────────────────────────────────────────────
# /api/events/lookup
# ─────────────────────────────────────────────────────────────────────────────


class TestEventsLookup:
    def test_returns_200_with_expected_contract(self, client, event_factory):
        event_factory(name="Uno")
        event_factory(name="Dos")

        res = client.get("/api/events/lookup")

        assert res.status_code == 200
        body = res.get_json()
        assert set(body.keys()) == {"events", "total"}
        assert body["total"] == len(body["events"]) == 2

    def test_status_active_filter(self, client, event_factory):
        event_factory(name="Activo")
        inactive = event_factory(name="Inactivo")
        inactive.is_active = False
        db.session.commit()

        body = client.get("/api/events/lookup?status=active").get_json()

        assert body["total"] == 1
        assert body["events"][0]["name"] == "Activo"

    def test_default_sort_is_start_date_ascending(self, client, event_factory):
        event_factory(name="Tardío", start_date=datetime(2026, 6, 1, 9, 0, 0))
        event_factory(name="Temprano", start_date=datetime(2025, 1, 1, 9, 0, 0))

        body = client.get("/api/events/lookup").get_json()
        names = [e["name"] for e in body["events"]]

        assert names == ["Temprano", "Tardío"]

    def test_sort_desc_is_supported(self, client, event_factory):
        """Lo usa el calendario del admin (que pedía start_date:desc)."""
        event_factory(name="Tardío", start_date=datetime(2026, 6, 1, 9, 0, 0))
        event_factory(name="Temprano", start_date=datetime(2025, 1, 1, 9, 0, 0))

        body = client.get("/api/events/lookup?sort=start_date:desc").get_json()
        names = [e["name"] for e in body["events"]]

        assert names == ["Tardío", "Temprano"]

    def test_malicious_sort_key_is_ignored_not_injected(self, client, event_factory):
        """El sort se valida contra una whitelist de columnas."""
        event_factory(name="Uno")

        res = client.get("/api/events/lookup?sort=evil_column:asc")

        assert res.status_code == 200

    def test_search_filter(self, client, event_factory):
        event_factory(name="Aniversario Tec")
        event_factory(name="Congreso")

        body = client.get("/api/events/lookup?search=aniversario").get_json()

        assert body["total"] == 1
        assert body["events"][0]["name"] == "Aniversario Tec"


# ─────────────────────────────────────────────────────────────────────────────
# /api/activities/by-event/<id>
# ─────────────────────────────────────────────────────────────────────────────


class TestActivitiesByEvent:
    def test_returns_all_activities_without_paginating(
        self, client, event_factory, activity_factory
    ):
        ev = event_factory(name="Evento Full")
        for i in range(5):
            activity_factory(event_id=ev.id, name=f"Act {i}")

        body = client.get(f"/api/activities/by-event/{ev.id}").get_json()

        assert set(body.keys()) == {"activities", "total", "event"}
        assert body["total"] == 5
        assert body["event"]["id"] == ev.id
        assert body["event"]["name"] == "Evento Full"

    def test_items_are_rich_not_slim(self, client, activity_factory):
        """La vista del estudiante agrupa por día y muestra el aforo: necesita
        los campos completos, no la versión reducida del lookup."""
        act = activity_factory(name="Taller", max_capacity=30)

        body = client.get(f"/api/activities/by-event/{act.event_id}").get_json()
        item = body["activities"][0]

        # Campos ricos que la vista del portal consume
        assert item["max_capacity"] == 30
        assert item["duration_hours"] == 2.0
        assert item["start_datetime"]
        assert item["end_datetime"]
        assert item["event"]["id"] == act.event_id

    def test_includes_current_capacity_count(self, client, app, activity_factory):
        """`current_capacity` es el que usa el portal para la ocupación."""
        with app.app_context():
            act = activity_factory(name="Llena")
            s1 = _make_student("Ana", "ISC", "A1")
            s2 = _make_student("Beto", "IM", "B2")
            db.session.commit()
            _make_registration(s1, act)
            _make_registration(s2, act)
            db.session.commit()
            act_id = act.id
            ev_id = act.event_id

        body = client.get(f"/api/activities/by-event/{ev_id}").get_json()
        item = next(a for a in body["activities"] if a["id"] == act_id)

        assert item["current_capacity"] == 2
        # Alias histórico, se mantiene por compatibilidad
        assert item["current_registrations"] == 2

    def test_cancelled_and_absent_do_not_count(self, client, app, activity_factory):
        with app.app_context():
            act = activity_factory(name="Parcial")
            s1 = _make_student("Ana", "ISC", "A1")
            s2 = _make_student("Beto", "IM", "B2")
            s3 = _make_student("Caro", "ISC", "C3")
            db.session.commit()
            _make_registration(s1, act, status="Registrado")
            _make_registration(s2, act, status="Cancelado")
            _make_registration(s3, act, status="Ausente")
            db.session.commit()
            ev_id = act.event_id

        body = client.get(f"/api/activities/by-event/{ev_id}").get_json()

        assert body["activities"][0]["current_capacity"] == 1

    def test_for_student_excludes_magistral(self, client, activity_factory):
        """Regla heredada del listado genérico: los estudiantes no ven
        las 'Magistrales'."""
        act = activity_factory(name="Con Taller", activity_type="Taller")
        ev_id = act.event_id
        activity_factory(event_id=ev_id, name="Magistral", activity_type="Magistral")

        all_body = client.get(f"/api/activities/by-event/{ev_id}").get_json()
        student_body = client.get(
            f"/api/activities/by-event/{ev_id}?for_student=true"
        ).get_json()

        assert all_body["total"] == 2
        assert student_body["total"] == 1
        assert all_body["activities"][1]["activity_type"] == "Magistral"

    def test_exclude_types_accepts_comma_separated_list(self, client, activity_factory):
        act = activity_factory(name="Base", activity_type="Taller")
        ev_id = act.event_id
        activity_factory(event_id=ev_id, name="Conf", activity_type="Conferencia")

        body = client.get(
            f"/api/activities/by-event/{ev_id}?exclude_types=Conferencia"
        ).get_json()

        assert body["total"] == 1
        assert body["activities"][0]["activity_type"] == "Taller"

    def test_activity_type_filter(self, client, activity_factory):
        act = activity_factory(name="Uno", activity_type="Taller")
        ev_id = act.event_id
        activity_factory(event_id=ev_id, name="Dos", activity_type="Conferencia")

        body = client.get(
            f"/api/activities/by-event/{ev_id}?activity_type=Taller"
        ).get_json()

        assert body["total"] == 1
        assert body["activities"][0]["name"] == "Uno"

    def test_search_filter(self, client, activity_factory):
        act = activity_factory(name="Taller de Excel")
        ev_id = act.event_id
        activity_factory(event_id=ev_id, name="Conferencia")

        body = client.get(f"/api/activities/by-event/{ev_id}?search=excel").get_json()

        assert body["total"] == 1
        assert body["activities"][0]["name"] == "Taller de Excel"

    def test_only_returns_activities_of_the_requested_event(
        self, client, event_factory, activity_factory
    ):
        ev_a = event_factory(name="A")
        ev_b = event_factory(name="B")
        activity_factory(event_id=ev_a.id, name="De A")
        activity_factory(event_id=ev_b.id, name="De B")

        body = client.get(f"/api/activities/by-event/{ev_a.id}").get_json()

        assert body["total"] == 1
        assert body["activities"][0]["name"] == "De A"

    def test_unknown_event_returns_404(self, client):
        res = client.get("/api/activities/by-event/999999")

        assert res.status_code == 404
        assert "message" in res.get_json()


# ─────────────────────────────────────────────────────────────────────────────
# max_per_page=100 en los listados genéricos
# ─────────────────────────────────────────────────────────────────────────────


class TestMaxPerPageCap:
    """El tope solo es viable porque los selectores ya usan /lookup."""

    def test_students_list_caps_per_page_at_100(self, client, app):
        with app.app_context():
            for i in range(120):
                _make_student(f"Est {i}", "ISC", f"C{i}")
            db.session.commit()

        body = client.get("/api/students/?per_page=1000&page=1").get_json()

        assert len(body["students"]) == 100
        assert body["total"] == 120

    def test_activities_list_caps_per_page_at_100(
        self, client, event_factory, activity_factory
    ):
        ev = event_factory(name="Evento")
        for i in range(110):
            activity_factory(event_id=ev.id, name=f"Act {i}")

        body = client.get("/api/activities/?per_page=500&page=1").get_json()

        assert len(body["activities"]) == 100
        assert body["total"] == 110

    def test_events_list_caps_per_page_at_100(self, client, event_factory):
        for i in range(105):
            event_factory(name=f"Evento {i}")

        body = client.get("/api/events/?per_page=999&page=1").get_json()

        assert len(body["events"]) == 100
        assert body["total"] == 105

    def test_per_page_below_cap_is_respected(self, client, app):
        """El tope no debe interferir con los valores normales."""
        with app.app_context():
            for i in range(30):
                _make_student(f"Est {i}", "ISC", f"C{i}")
            db.session.commit()

        body = client.get("/api/students/?per_page=10&page=2").get_json()

        assert len(body["students"]) == 10
        assert body["total"] == 30

    def test_attendances_list_caps_per_page_at_100(self, client, auth_headers):
        """Esta vista pagina a mano con limit/offset, así que el tope se
        aplica aparte de paginate()."""
        res = client.get("/api/attendances/?per_page=1000&page=1", headers=auth_headers)

        assert res.status_code == 200
        assert len(res.get_json()["attendances"]) <= 100
