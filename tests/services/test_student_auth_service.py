"""Validación de credenciales en proceso: mapeo de errores y rate-limit.

Cubre el reemplazo del loopback HTTP de ``POST /api/registrations/self``
contra ``/api/auth/student-login``: ambos caminos comparten esta función y
por tanto el mismo contador de intentos.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from app.services import student_auth_service as auth_service
from app.services.student_auth_service import (
    EXTERNAL_STUDENT_VALIDATION_URL,
    CredentialServiceUnavailable,
    CredentialsRateLimited,
    InvalidCredentials,
    reset_credential_limits,
    validate_student_credentials,
)


@pytest.fixture(autouse=True)
def _clean_rate_limits(app):
    """Limpia contadores y aporta contexto de aplicación (logging, settings)."""
    reset_credential_limits()
    yield
    reset_credential_limits()


def _external(status_code=200, payload=None):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    return response


def _credentials(control_number="A1234567", ip="203.0.113.10"):
    return control_number, "secret", ip


def test_success_returns_external_student_data():
    control_number, password, ip = _credentials()
    with patch.object(auth_service.requests, "post") as post:
        post.return_value = _external(
            200, {"success": True, "data": {"name": "Ana López", "career": "ISC"}}
        )
        data = validate_student_credentials(control_number, password, ip=ip)

    assert data["name"] == "Ana López"
    assert post.call_args.args[0] == EXTERNAL_STUDENT_VALIDATION_URL


def test_rejected_credentials_raise_invalid():
    control_number, password, ip = _credentials()
    with patch.object(auth_service.requests, "post") as post:
        post.return_value = _external(401)
        with pytest.raises(InvalidCredentials):
            validate_student_credentials(control_number, password, ip=ip)


def test_success_false_raises_invalid():
    control_number, password, ip = _credentials()
    with patch.object(auth_service.requests, "post") as post:
        post.return_value = _external(200, {"success": False, "data": None})
        with pytest.raises(InvalidCredentials):
            validate_student_credentials(control_number, password, ip=ip)


def test_error_status_raises_service_unavailable():
    control_number, password, ip = _credentials()
    with patch.object(auth_service.requests, "post") as post:
        post.return_value = _external(500)
        with pytest.raises(CredentialServiceUnavailable):
            validate_student_credentials(control_number, password, ip=ip)


def test_network_error_raises_service_unavailable():
    control_number, password, ip = _credentials()
    with patch.object(auth_service.requests, "post") as post:
        post.side_effect = requests.exceptions.ConnectionError("sin ruta")
        with pytest.raises(CredentialServiceUnavailable):
            validate_student_credentials(control_number, password, ip=ip)


def test_rate_limit_is_per_control_number(monkeypatch):
    """A los N intentos fallidos ya no se vuelve a llamar al sistema externo."""
    monkeypatch.setitem(
        auth_service.CREDENTIAL_ATTEMPT_LIMITS, "control_number", (2, 300)
    )
    monkeypatch.setitem(auth_service.CREDENTIAL_ATTEMPT_LIMITS, "ip", (100, 300))

    with patch.object(auth_service.requests, "post") as post:
        post.return_value = _external(401)
        for _ in range(2):
            with pytest.raises(InvalidCredentials):
                validate_student_credentials("A1234567", "secret", ip="203.0.113.10")

        with pytest.raises(CredentialsRateLimited):
            validate_student_credentials("A1234567", "secret", ip="203.0.113.10")

    assert post.call_count == 2


def test_rate_limit_is_per_ip(monkeypatch):
    """Barrer muchos números de control desde la misma IP también se frena."""
    monkeypatch.setitem(
        auth_service.CREDENTIAL_ATTEMPT_LIMITS, "control_number", (100, 300)
    )
    monkeypatch.setitem(auth_service.CREDENTIAL_ATTEMPT_LIMITS, "ip", (2, 300))

    with patch.object(auth_service.requests, "post") as post:
        post.return_value = _external(401)
        for control_number in ("A0000001", "A0000002"):
            with pytest.raises(InvalidCredentials):
                validate_student_credentials(
                    control_number, "secret", ip="203.0.113.10"
                )

        with pytest.raises(CredentialsRateLimited):
            validate_student_credentials("A0000003", "secret", ip="203.0.113.10")

    assert post.call_count == 2
