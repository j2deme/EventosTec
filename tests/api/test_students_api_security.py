"""Seguridad del API de estudiantes y de los preregistros.

Cierra los tres hallazgos que bloqueaban la etiqueta v1.0.0:

  §1.1  ``GET /api/students/`` no llevaba token y ``students_schema`` anida
        ``registrations`` y ``attendances``: enumerando el padrón por nombre
        o número de control se obtenía el historial académico completo
        (a qué actividad se preregistró cada quién y con qué horario de
        entrada/salida). La app no tiene protección global por
        ``before_request``, así que cada endpoint se defiende solo.

  B-1   ``hours-by-event`` y ``event/<id>/details`` aceptaban cualquier
        token: con el mío se leían las horas o el detalle de otra persona.

  B-2   ``GET /api/registrations/`` respetaba el parámetro ``student_id``:
        se leían y paginaban los preregistros ajenos.

Además cubre ``GET /api/students/public-lookup``, el endpoint nuevo que
hizo posible proteger el listado SIN romper la preregistración pública ni
el registro rápido de staff (que solo necesitaban resolver un número de
control a datos básicos).
"""

from datetime import datetime, timedelta

import pytest
from flask_jwt_extended import create_access_token

from app import db
from app.models.activity import Activity
from app.models.registration import Registration
from app.models.student import Student


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _make_student(control, name="Estudiante", career="ISC"):
    student = Student()
    student.control_number = control
    student.full_name = name
    student.career = career
    student.email = f"{control}@test.com"
    db.session.add(student)
    db.session.flush()
    return student


def _student_headers(app, student_id):
    """Headers con token de ESTUDIANTE (claim ``type`` canónico)."""
    with app.app_context():
        token = create_access_token(
            identity=str(student_id), additional_claims={"type": "student"}
        )
    return {"Authorization": f"Bearer {token}"}


def _make_activity(event_id):
    activity = Activity(
        event_id=event_id,
        department="TEST",
        name="Actividad de prueba",
        description="...",
        start_datetime=datetime.now(),
        end_datetime=datetime.now() + timedelta(hours=2),
        duration_hours=2.0,
        activity_type="Conferencia",
        location="Aula 1",
        modality="Presencial",
    )
    db.session.add(activity)
    db.session.flush()
    return activity


# ─────────────────────────────────────────────────────────────────────────────
# §1.1 — el listado de estudiantes deja de ser anónimo (y de ser de cualquiera)
# ─────────────────────────────────────────────────────────────────────────────


class TestStudentsListRequiresAdmin:
    def test_list_without_token_is_401(self, client, app):
        """El hallazgo original: sin token devolvía el padrón con
        ``registrations`` y ``attendances`` anidados."""
        with app.app_context():
            _make_student("A1", "Ana López")
            _make_student("B2", "Beto Ruiz")
            db.session.commit()

        res = client.get("/api/students/")

        assert res.status_code == 401
        assert "students" not in (res.get_json() or {})

    def test_list_with_student_token_is_403(self, client, app):
        """Solo ``@jwt_required()`` no bastaría: cualquier estudiante
        autenticado seguiría pudiendo descargar el padrón completo."""
        with app.app_context():
            s = _make_student("A1", "Ana López")
            db.session.commit()
            student_id = s.id

        res = client.get("/api/students/", headers=_student_headers(app, student_id))

        assert res.status_code == 403
        assert "students" not in (res.get_json() or {})

    def test_list_with_admin_token_still_works(self, client, app, auth_headers):
        """El panel de admin no cambia de contrato."""
        with app.app_context():
            _make_student("A1", "Ana López")
            db.session.commit()

        res = client.get("/api/students/", headers=auth_headers)

        assert res.status_code == 200
        body = res.get_json()
        assert body["total"] == 1
        assert body["students"][0]["control_number"] == "A1"

    @pytest.mark.parametrize(
        "path",
        ["/api/students/lookup", "/api/students/careers"],
        ids=["lookup", "careers"],
    )
    def test_student_endpoints_without_token_are_401(self, client, path):
        assert client.get(path).status_code == 401

    @pytest.mark.parametrize(
        "path",
        ["/api/students/lookup", "/api/students/careers"],
        ids=["lookup", "careers"],
    )
    def test_student_endpoints_with_student_token_are_403(self, client, app, path):
        with app.app_context():
            s = _make_student("A1")
            db.session.commit()
            student_id = s.id

        res = client.get(path, headers=_student_headers(app, student_id))
        assert res.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# public-lookup — el sustituto público del listado
# ─────────────────────────────────────────────────────────────────────────────


class TestPublicLookup:
    def test_returns_only_the_four_fields_the_public_flows_read(
        self, client, app, event_factory
    ):
        """Prueba de no fuga: el estudiante SÍ tiene preregistros y
        asistencia, y el payload no debe llevar ninguno de los dos."""
        with app.app_context():
            ev = event_factory(name="Evento")
            act = _make_activity(ev.id)
            s = _make_student("26690330", "Ana López", "ISC")
            db.session.commit()
            db.session.add(
                Registration(
                    student_id=s.id,
                    activity_id=act.id,
                    status="Confirmado",
                    registration_date=datetime.now(),
                )
            )
            db.session.commit()

        res = client.get("/api/students/public-lookup?control_number=26690330")

        assert res.status_code == 200
        student = res.get_json()["student"]
        assert set(student.keys()) == {
            "control_number",
            "full_name",
            "career",
            "email",
        }
        # Ni historial académico ni identificadores internos
        for leaked in (
            "registrations",
            "attendances",
            "id",
            "created_at",
            "updated_at",
        ):
            assert leaked not in student
        assert student["control_number"] == "26690330"
        assert student["full_name"] == "Ana López"

    def test_is_public_on_purpose(self, client, app):
        """La preregistración pública y el walk-in no tienen token: este es
        el único endpoint de estudiantes que debe seguirlo sin él."""
        with app.app_context():
            _make_student("26690330")
            db.session.commit()

        assert (
            client.get(
                "/api/students/public-lookup?control_number=26690330"
            ).status_code
            == 200
        )

    def test_unknown_control_returns_404_not_empty_list(self, client):
        res = client.get("/api/students/public-lookup?control_number=NOEXISTE")

        assert res.status_code == 404
        assert "student" not in (res.get_json() or {})

    def test_missing_control_number_returns_400(self, client):
        assert client.get("/api/students/public-lookup").status_code == 400

    def test_empty_control_number_returns_400(self, client):
        assert (
            client.get("/api/students/public-lookup?control_number=%20%20").status_code
            == 400
        )

    def test_exact_match_cannot_enumerate_by_prefix(self, client, app):
        """Antes un prefijo corto devolvía hasta 10 filas del padrón
        (``?search=26690``); ahora la coincidencia es exacta."""
        with app.app_context():
            _make_student("26690330", "Ana")
            _make_student("26690331", "Beto")
            _make_student("26690332", "Caro")
            db.session.commit()

        prefix = client.get("/api/students/public-lookup?control_number=2669033")

        assert prefix.status_code == 404
        # Pero el número completo sí resuelve
        exact = client.get("/api/students/public-lookup?control_number=26690331")
        assert exact.status_code == 200
        assert exact.get_json()["student"]["full_name"] == "Beto"


# ─────────────────────────────────────────────────────────────────────────────
# B-1 — horas y detalle por evento son del estudiante que las consulta
# ─────────────────────────────────────────────────────────────────────────────


class TestStudentHoursOwnership:
    @pytest.fixture
    def two_students(self, app):
        """Dos estudiantes con actividad y preregistro, para poder medir
        el cruce de identidades."""
        from app.models.event import Event

        with app.app_context():
            event = Event(
                name="Evento horas",
                start_date=datetime.now(),
                end_date=datetime.now() + timedelta(days=7),
                is_active=True,
            )
            db.session.add(event)
            db.session.flush()

            activity = _make_activity(event.id)
            owner = _make_student("OWN01", "Dueño")
            other = _make_student("OTHER1", "Ajeno")
            db.session.add_all(
                [
                    Registration(
                        student_id=owner.id,
                        activity_id=activity.id,
                        status="Asistió",
                        registration_date=datetime.now(),
                    ),
                    Registration(
                        student_id=other.id,
                        activity_id=activity.id,
                        status="Asistió",
                        registration_date=datetime.now(),
                    ),
                ]
            )
            db.session.commit()
            return {
                "owner_id": owner.id,
                "other_id": other.id,
                "event_id": event.id,
            }

    def test_hours_without_token_is_401(self, client, two_students):
        url = f"/api/students/{two_students['owner_id']}/hours-by-event"
        assert client.get(url).status_code == 401

    def test_details_without_token_is_401(self, client, two_students):
        url = (
            f"/api/students/{two_students['owner_id']}"
            f"/event/{two_students['event_id']}/details"
        )
        assert client.get(url).status_code == 401

    def test_hours_of_another_student_with_my_token_is_403(
        self, client, app, two_students
    ):
        """B-1: antes el chequeo no existía y devolvía 200 con datos ajenos."""
        url = f"/api/students/{two_students['other_id']}/hours-by-event"
        res = client.get(url, headers=_student_headers(app, two_students["owner_id"]))

        assert res.status_code == 403

    def test_details_of_another_student_with_my_token_is_403(
        self, client, app, two_students
    ):
        url = (
            f"/api/students/{two_students['other_id']}"
            f"/event/{two_students['event_id']}/details"
        )
        res = client.get(url, headers=_student_headers(app, two_students["owner_id"]))

        assert res.status_code == 403

    def test_own_hours_still_return_200(self, client, app, two_students):
        url = f"/api/students/{two_students['owner_id']}/hours-by-event"
        res = client.get(url, headers=_student_headers(app, two_students["owner_id"]))

        assert res.status_code == 200
        assert res.get_json()["student"]["id"] == two_students["owner_id"]

    def test_admin_can_read_anyone(self, client, two_students, auth_headers):
        url = f"/api/students/{two_students['other_id']}/hours-by-event"
        res = client.get(url, headers=auth_headers)

        assert res.status_code == 200

    def test_unknown_student_is_403_not_404_for_a_student_token(
        self, client, app, two_students
    ):
        """El chequeo de propiedad va ANTES del 404, a propósito.

        Si se respondiera 404 cuando no existe y 403 cuando existe pero es
        de otro, el endpoint se convertiría en un oráculo para descubrir
        qué ids de estudiante hay en la base. Respondiendo 403 siempre,
        un token de estudiante no distingue "no existe" de "existe pero no
        es tuyo". El 404 legítimo sigue vivo para el admin (que sí puede
        consultar a cualquiera).
        """
        url = "/api/students/999999/hours-by-event"
        res = client.get(url, headers=_student_headers(app, two_students["owner_id"]))

        assert res.status_code == 403

    def test_unknown_student_is_404_for_the_admin(
        self, client, two_students, auth_headers
    ):
        res = client.get("/api/students/999999/hours-by-event", headers=auth_headers)

        assert res.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# B-2 — el listado de preregistros es propio con token de estudiante
# ─────────────────────────────────────────────────────────────────────────────


class TestRegistrationsListOwnership:
    @pytest.fixture
    def two_registrations(self, app):
        from app.models.event import Event

        with app.app_context():
            event = Event(
                name="Evento regs",
                start_date=datetime.now(),
                end_date=datetime.now() + timedelta(days=7),
                is_active=True,
            )
            db.session.add(event)
            db.session.flush()
            activity = _make_activity(event.id)
            owner = _make_student("OWN02", "Dueño")
            other = _make_student("OTHER2", "Ajeno")
            db.session.add_all(
                [
                    Registration(
                        student_id=owner.id,
                        activity_id=activity.id,
                        status="Confirmado",
                        registration_date=datetime.now(),
                    ),
                    Registration(
                        student_id=other.id,
                        activity_id=activity.id,
                        status="Confirmado",
                        registration_date=datetime.now(),
                    ),
                ]
            )
            db.session.commit()
            return {"owner_id": owner.id, "other_id": other.id}

    def test_student_cannot_list_another_students_registrations(
        self, client, app, two_registrations
    ):
        """B-2: ``?student_id=<ajeno>`` se ignora y solo vuelven los míos."""
        other = two_registrations["other_id"]
        owner = two_registrations["owner_id"]

        res = client.get(
            f"/api/registrations/?student_id={other}",
            headers=_student_headers(app, owner),
        )

        assert res.status_code == 200
        items = res.get_json()["registrations"]
        assert items, "debería devolver los propios"
        assert {r["student_id"] for r in items} == {owner}
        assert other not in {r["student_id"] for r in items}

    def test_student_without_param_still_gets_only_own(
        self, client, app, two_registrations
    ):
        res = client.get(
            "/api/registrations/",
            headers=_student_headers(app, two_registrations["owner_id"]),
        )

        items = res.get_json()["registrations"]
        assert {r["student_id"] for r in items} == {two_registrations["owner_id"]}

    def test_admin_can_still_filter_by_any_student(
        self, client, two_registrations, auth_headers
    ):
        res = client.get(
            f"/api/registrations/?student_id={two_registrations['other_id']}",
            headers=auth_headers,
        )

        items = res.get_json()["registrations"]
        assert {r["student_id"] for r in items} == {two_registrations["other_id"]}

    def test_list_without_token_is_401(self, client):
        assert client.get("/api/registrations/").status_code == 401
