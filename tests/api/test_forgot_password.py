"""Tests para POST /api/auth/forgot-password (proxy de recuperación MAB)."""

import pytest
import requests

from app.services import password_recovery_service as prs


@pytest.fixture(autouse=True)
def _reset_limits():
    """Cada test empieza con contadores de rate-limit limpios."""
    prs.reset_limits()
    yield
    prs.reset_limits()


def _mock_post(mocker, status_code=200):
    mock_response = mocker.Mock()
    mock_response.status_code = status_code
    return mocker.patch("requests.post", return_value=mock_response)


def test_forgot_password_requires_control_number(client):
    response = client.post("/api/auth/forgot-password", json={})

    assert response.status_code == 400
    assert "message" in response.get_json()


def test_forgot_password_rejects_invalid_format(client):
    response = client.post(
        "/api/auth/forgot-password", json={"control_number": "abc$#%"}
    )

    assert response.status_code == 400


def test_forgot_password_rejects_non_json_payload(client):
    """Un body que no es objeto JSON no debe reventar (400, no 500)."""
    response = client.post(
        "/api/auth/forgot-password",
        data='["no es un objeto"]',
        content_type="application/json",
    )

    assert response.status_code == 400


def test_forgot_password_success_is_generic(client, mocker):
    """200 con mensaje genérico: no revela si el número de control existe."""
    mock_post = _mock_post(mocker, status_code=200)

    response = client.post(
        "/api/auth/forgot-password", json={"control_number": "25690999"}
    )

    assert response.status_code == 200
    assert response.get_json()["message"] == prs.GENERIC_SUCCESS_MESSAGE
    # Se reenvía el número de control como `username` (contrato de 8091)
    mock_post.assert_called_once()
    assert mock_post.call_args.kwargs["json"] == {"username": "25690999"}
    assert mock_post.call_args.kwargs["headers"]["Accept"] == "application/json"


def test_forgot_password_success_message_same_for_unknown_number(client, mocker):
    """Mensaje idéntico exista o no el estudiante (anti-enumeración)."""
    _mock_post(mocker, status_code=200)

    known = client.post(
        "/api/auth/forgot-password", json={"control_number": "25690999"}
    )
    prs.reset_limits()
    unknown = client.post(
        "/api/auth/forgot-password", json={"control_number": "99999999"}
    )

    assert known.status_code == unknown.status_code == 200
    assert known.get_json()["message"] == unknown.get_json()["message"]


def test_forgot_password_external_error_returns_503(client, mocker):
    """4xx/5xx de 8091 (distinto de 429) -> 503 sin filtrar el motivo."""
    _mock_post(mocker, status_code=404)

    response = client.post(
        "/api/auth/forgot-password", json={"control_number": "25690999"}
    )

    assert response.status_code == 503
    assert response.get_json()["message"] == prs.EXTERNAL_UNAVAILABLE_MESSAGE


def test_forgot_password_external_rate_limit_maps_to_429(client, mocker):
    _mock_post(mocker, status_code=429)

    response = client.post(
        "/api/auth/forgot-password", json={"control_number": "25690999"}
    )

    assert response.status_code == 429
    assert response.get_json()["message"] == prs.RATE_LIMIT_MESSAGE


def test_forgot_password_external_timeout_returns_503(client, mocker):
    mocker.patch(
        "requests.post",
        side_effect=requests.exceptions.ConnectionError("sin ruta"),
    )

    response = client.post(
        "/api/auth/forgot-password", json={"control_number": "25690999"}
    )

    assert response.status_code == 503


def test_forgot_password_rate_limited_per_control_number(client, mocker):
    """3er intento para el mismo número de control en la hora -> 429."""
    _mock_post(mocker, status_code=200)
    body = {"control_number": "25690999"}

    assert client.post("/api/auth/forgot-password", json=body).status_code == 200
    assert client.post("/api/auth/forgot-password", json=body).status_code == 200
    assert client.post("/api/auth/forgot-password", json=body).status_code == 429


def test_forgot_password_rate_limited_per_ip(client, mocker):
    """6ta solicitud desde la misma IP (distinto control) -> 429."""
    _mock_post(mocker, status_code=200)

    statuses = [
        client.post(
            "/api/auth/forgot-password", json={"control_number": f"1234560{i}"}
        ).status_code
        for i in range(6)
    ]

    assert statuses[:5] == [200] * 5
    assert statuses[5] == 429


def test_forgot_password_no_auth_required(client, mocker):
    """Endpoint público: no exige JWT."""
    _mock_post(mocker, status_code=200)

    response = client.post(
        "/api/auth/forgot-password", json={"control_number": "25690999"}
    )

    assert response.status_code == 200


def test_limiter_sliding_window_expires():
    """Los intentos vencen al salir de la ventana; no bloquea para siempre."""
    limiter = prs.SlidingWindowLimiter()

    assert limiter.allow("k", 1, 60) is True
    assert limiter.allow("k", 1, 60) is False

    # Forzar el vencimiento de la ventana limpiando el estado directamente
    entry = limiter._hits["k"]
    entry["window"] = 0
    assert limiter.allow("k", 1, 60) is True
