"""Contrato de ``POST /api/registrations/self`` (self check-in público).

Cubre los cambios del módulo: ventana configurable (item 1), rate-limit y
validación de credenciales sin loopback HTTP (items 2 y 5) y política de
estado (item 3: el check-in abre la sesión pero no cierra la
preregistración).
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
import requests

from app import db
from app.models.activity import Activity
from app.models.attendance import Attendance
from app.models.registration import Registration
from app.models.student import Student
from app.services import student_auth_service as auth_service
from app.services.student_auth_service import (
    EXTERNAL_STUDENT_VALIDATION_URL,
    reset_credential_limits,
)

APP_TZ = ZoneInfo("America/Mexico_City")
POST_URL = "/api/registrations/self"


@pytest.fixture(autouse=True)
def _clean_rate_limits():
    reset_credential_limits()
    yield
    reset_credential_limits()


def _local_now() -> datetime:
    """'Ahora' en hora local de la app (naive, como se persiste en la BD)."""
    return datetime.now(APP_TZ).replace(tzinfo=None)


def _make_activity(event_id, minutes_from_start: int, slug="self-reg-act") -> Activity:
    """Actividad con inicio desplazado ``minutes_from_start`` respecto a ahora.

    El servicio localiza el ``start_datetime`` naive como hora de la app, así
    que el offset debe calcularse en hora local.
    """
    start = _local_now() + timedelta(minutes=minutes_from_start)
    activity = Activity(
        event_id=event_id,
        department="TEST",
        name="Conferencia Self",
        start_datetime=start,
        end_datetime=start + timedelta(hours=2),
        duration_hours=2.0,
        activity_type="Conferencia",
        location="Auditorio",
        modality="Presencial",
        public_slug=slug,
    )
    db.session.add(activity)
    db.session.commit()
    return activity


def _external(status_code=200, payload=None):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    return response


def _student_payload():
    return {
        "success": True,
        "data": {
            "name": "Juan Pérez",
            "email": "juan@tecvalles.mx",
            "career": "Ingeniería en Sistemas",
        },
    }


def _payload(control_number="A1234567", password="secret", activity_id=None):
    return {
        "control_number": control_number,
        "password": password,
        "activity_id": activity_id,
    }


def test_missing_fields_return_400(client):
    response = client.post(POST_URL, json={"control_number": "A1234567"})

    assert response.status_code == 400
    assert "requeridos" in response.get_json()["message"]


def test_unknown_activity_return_404(client):
    response = client.post(POST_URL, json=_payload(activity_id="no-existe"))

    assert response.status_code == 404
    assert response.get_json()["message"] == "Actividad no encontrada"


def test_window_not_yet_open_return_400(client, event_factory):
    """Antes de abrir (inicio - 30 min) el check-in está rechazado."""
    activity = _make_activity(event_factory().id, minutes_from_start=120)

    response = client.post(POST_URL, json=_payload(activity_id=activity.public_slug))

    assert response.status_code == 400
    assert "aún no abre" in response.get_json()["message"]
    assert "auto-registro" in response.get_json()["message"]


def test_window_closed_return_400(client, event_factory):
    """Después de cerrar (inicio + 20 min) el check-in está rechazado.

    A diferencia de `not_open`, el cierre se evalúa *después* de validar
    credenciales (para poder responder un 409 de verificación a quien ya se
    registró), así que el test debe mockear el sistema externo.
    """
    activity = _make_activity(event_factory().id, minutes_from_start=-180)

    with patch.object(auth_service.requests, "post") as post:
        post.return_value = _external(200, _student_payload())
        response = client.post(
            POST_URL, json=_payload(activity_id=activity.public_slug)
        )

    assert response.status_code == 400
    assert "terminó" in response.get_json()["message"]


def test_invalid_credentials_return_401(client, event_factory):
    activity = _make_activity(event_factory().id, minutes_from_start=-5)

    with patch.object(auth_service.requests, "post") as post:
        post.return_value = _external(401)
        response = client.post(
            POST_URL, json=_payload(activity_id=activity.public_slug)
        )

    assert response.status_code == 401
    assert response.get_json()["message"] == "Credenciales inválidas"


def test_external_failure_return_503(client, event_factory):
    activity = _make_activity(event_factory().id, minutes_from_start=-5)

    with patch.object(auth_service.requests, "post") as post:
        post.side_effect = requests.exceptions.ConnectionError("caído")
        response = client.post(
            POST_URL, json=_payload(activity_id=activity.public_slug)
        )

    assert response.status_code == 503
    assert "Servicio de validación no disponible" in response.get_json()["message"]


def test_rate_limit_return_429_before_calling_external(
    client, event_factory, monkeypatch
):
    """Al agotar los intentos se responde 429 sin volver a llamar a MAB."""
    monkeypatch.setitem(
        auth_service.CREDENTIAL_ATTEMPT_LIMITS, "control_number", (2, 300)
    )
    monkeypatch.setitem(auth_service.CREDENTIAL_ATTEMPT_LIMITS, "ip", (100, 300))

    activity = _make_activity(event_factory().id, minutes_from_start=-5)
    payload = _payload(activity_id=activity.public_slug)

    with patch.object(auth_service.requests, "post") as post:
        post.return_value = _external(401)
        for _ in range(2):
            assert client.post(POST_URL, json=payload).status_code == 401
        response = client.post(POST_URL, json=payload)

    assert response.status_code == 429
    assert post.call_count == 2


def test_success_opens_session_without_closing_registration(
    client, sample_data, event_factory
):
    """201: abre la sesión ('Parcial') y NO cambia el estado del preregistro."""
    activity = _make_activity(event_factory().id, minutes_from_start=-5)
    student = db.session.get(Student, sample_data["student_id"])
    registration = Registration(
        student_id=student.id,
        activity_id=activity.id,
        status="Confirmado",
        attended=False,
    )
    db.session.add(registration)
    db.session.commit()

    payload = _payload(
        control_number=student.control_number, activity_id=activity.public_slug
    )
    with patch.object(auth_service.requests, "post") as post:
        post.return_value = _external(200, _student_payload())
        response = client.post(POST_URL, json=payload)

    assert response.status_code == 201
    body = response.get_json()
    assert body["attendance"]["status"] == "Parcial"
    assert body["attendance"]["check_in_time"]

    attendance = Attendance.query.filter_by(
        student_id=student.id, activity_id=activity.id
    ).one()
    assert attendance.status == "Parcial"
    assert attendance.check_in_time is not None
    assert attendance.check_out_time is None

    # El resultado final lo define el checkout del admin
    db.session.refresh(registration)
    assert registration.status == "Confirmado"
    assert registration.attended is True

    # Sin loopback: una sola llamada y al sistema externo
    assert post.call_count == 1
    assert post.call_args.args[0] == EXTERNAL_STUDENT_VALIDATION_URL


def test_duplicate_check_in_return_409(client, sample_data, event_factory):
    """409 = confirmación de "ya registrado", con la asistencia existente."""
    activity = _make_activity(event_factory().id, minutes_from_start=-5)
    student = db.session.get(Student, sample_data["student_id"])
    payload = _payload(
        control_number=student.control_number, activity_id=activity.public_slug
    )

    with patch.object(auth_service.requests, "post") as post:
        post.return_value = _external(200, _student_payload())
        first = client.post(POST_URL, json=payload)
        second = client.post(POST_URL, json=payload)

    assert first.status_code == 201
    assert second.status_code == 409

    body = second.get_json()
    assert body["code"] == "already_registered"
    assert "ya estaba registrada" in body["message"]
    assert body["attendance"]["check_in_time"]
    assert body["attendance"]["status"] == "Parcial"

    assert (
        Attendance.query.filter_by(
            student_id=student.id, activity_id=activity.id
        ).count()
        == 1
    )


def test_duplicate_409_does_not_consume_rate_limit(
    client, sample_data, event_factory, monkeypatch
):
    """Reintentar un registro ya hecho no quema la cuota de intentos."""
    monkeypatch.setitem(
        auth_service.CREDENTIAL_ATTEMPT_LIMITS, "control_number", (3, 300)
    )
    monkeypatch.setitem(auth_service.CREDENTIAL_ATTEMPT_LIMITS, "ip", (100, 300))

    activity = _make_activity(event_factory().id, minutes_from_start=-5)
    student = db.session.get(Student, sample_data["student_id"])
    payload = _payload(
        control_number=student.control_number, activity_id=activity.public_slug
    )

    with patch.object(auth_service.requests, "post") as post:
        post.return_value = _external(200, _student_payload())
        assert client.post(POST_URL, json=payload).status_code == 201
        # Más reintentos que la cuota: ninguno debe caer en 429.
        statuses = [client.post(POST_URL, json=payload).status_code for _ in range(5)]

    assert statuses == [409] * 5
    assert post.call_count == 6


def test_window_closed_still_allows_verification(client, sample_data, event_factory):
    """Con la ventana cerrada, el que ya se registró recibe su 409 (no 400)."""
    activity = _make_activity(event_factory().id, minutes_from_start=-180)
    student = db.session.get(Student, sample_data["student_id"])
    attendance = Attendance(
        student_id=student.id,
        activity_id=activity.id,
        status="Parcial",
        check_in_time=_local_now(),
    )
    db.session.add(attendance)
    db.session.commit()

    payload = _payload(
        control_number=student.control_number, activity_id=activity.public_slug
    )
    with patch.object(auth_service.requests, "post") as post:
        post.return_value = _external(200, _student_payload())
        response = client.post(POST_URL, json=payload)

    assert response.status_code == 409
    assert response.get_json()["code"] == "already_registered"
    assert (
        Attendance.query.filter_by(
            student_id=student.id, activity_id=activity.id
        ).count()
        == 1
    )


def test_window_closed_rejection_does_not_consume_rate_limit(
    client, event_factory, monkeypatch
):
    """Quien insiste con la ventana cerrada ve el 400, nunca un 429."""
    monkeypatch.setitem(
        auth_service.CREDENTIAL_ATTEMPT_LIMITS, "control_number", (3, 300)
    )
    monkeypatch.setitem(auth_service.CREDENTIAL_ATTEMPT_LIMITS, "ip", (100, 300))

    activity = _make_activity(event_factory().id, minutes_from_start=-180)
    payload = _payload(activity_id=activity.public_slug)

    with patch.object(auth_service.requests, "post") as post:
        post.return_value = _external(200, _student_payload())
        statuses = [client.post(POST_URL, json=payload).status_code for _ in range(5)]
        last = client.post(POST_URL, json=payload)

    assert statuses == [400] * 5
    assert last.status_code == 400
    assert "terminó" in last.get_json()["message"]


def test_new_student_is_created_locally(client, event_factory):
    """El estudiante que no existía en la BD local se crea con su carrera."""
    activity = _make_activity(event_factory().id, minutes_from_start=-5)

    with patch.object(auth_service.requests, "post") as post:
        post.return_value = _external(200, _student_payload())
        response = client.post(
            POST_URL, json=_payload(activity_id=activity.public_slug)
        )

    assert response.status_code == 201
    student = Student.query.filter_by(control_number="A1234567").one()
    assert student.full_name == "Juan Pérez"
    assert student.career == "Ingeniería en Sistemas"
