"""Recuperación de contraseña de estudiantes (proxy a la plataforma MAB).

La fuente de verdad de las credenciales de los estudiantes es la plataforma
externa (``apps.tecvalles.mx:8091``); este servicio solo hace proxy de su
endpoint ``POST /api/password/forgot`` y agrega dos protecciones:

1. **Rate-limit local más estricto** que el del servicio externo (8091: 60/min
   por IP y 3/h por número de control). Todas nuestras llamadas salen desde la
   IP del servidor, así que sin este filtro cualquier visitante podría agotar
   la cuota *compartida* de 8091 y tumbar la recuperación para todos.
2. **Respuesta genérica**: nunca se revela si el número de control existe
   (anti-enumeración); el texto de éxito es siempre el mismo.

Nota sobre múltiples workers: gunicorn corre con ``-w 4`` y este contador vive
en memoria, así que cada worker lleva su propia cuenta (el límite real puede
ser hasta 4x el configurado). Por eso ``global`` es 10/min por worker
(<= 40/min agregado < 60/min que permite 8091).
"""

from __future__ import annotations

import re

import requests
from flask import current_app

# Re-exportado para mantener compatibilidad con los tests existentes
# (tests/api/test_forgot_password.py usa password_recovery_service.SlidingWindowLimiter).
from app.services.rate_limit import SlidingWindowLimiter

# Endpoint externo que envía el correo de recuperación.
EXTERNAL_FORGOT_URL = "http://apps.tecvalles.mx:8091/api/password/forgot"
EXTERNAL_TIMEOUT_SECONDS = 10

# Números de control reales son dígitos (p. ej. 25690999); se acepta
# alfanumérico de 4 a 20 caracteres por robustez ante formatos futuros.
CONTROL_NUMBER_RE = re.compile(r"^[0-9A-Za-z]{4,20}$")

# Mensaje único devuelto siempre en 200: idéntico al de 8091 y ajeno a si el
# número de control existe o no.
GENERIC_SUCCESS_MESSAGE = (
    "Si el número de control corresponde a un estudiante, se envió un "
    "enlace de recuperación al correo registrado."
)

RATE_LIMIT_MESSAGE = (
    "Demasiadas solicitudes. Espera unos minutos y vuelve a intentarlo."
)

EXTERNAL_UNAVAILABLE_MESSAGE = (
    "El servicio de recuperación no está disponible en este momento. "
    "Intenta de nuevo más tarde."
)

INVALID_CONTROL_MESSAGE = "El número de control es requerido."

INVALID_FORMAT_MESSAGE = "Número de control inválido."

# Límites locales: (número de eventos, ventana en segundos).
# Todos son más estrictos que los de 8091 por la razón descrita arriba.
LIMITS: dict[str, tuple[int, int]] = {
    # Por IP visitante (8091 da 60/min): 5 cada 10 minutos.
    "ip": (5, 600),
    # Por número de control (8091 da 3/h): 2 por hora.
    "control_number": (2, 3600),
    # Por worker (8091 da 60/min por la IP del servidor): 10/min.
    "global": (10, 60),
}


_limiter = SlidingWindowLimiter()


def reset_limits() -> None:
    """Reinicia los contadores de rate-limit (uso en tests)."""
    _limiter.reset()


def _clean_control_number(control_number) -> str:
    if isinstance(control_number, int):
        control_number = str(control_number)
    if not isinstance(control_number, str):
        return ""
    return control_number.strip()


def request_recovery(control_number, client_ip: str | None) -> tuple[int, dict]:
    """Solicita el enlace de recuperación para `control_number`.

    Devuelve ``(status_code, payload)`` listo para jsonify. El código de estado
    nunca distingue si el número de control existe:
    - 200: el servicio externo aceptó la solicitud (mensaje genérico).
    - 400: número de control ausente o con formato inválido.
    - 429: se alcanzó un límite (el nuestro o el de 8091).
    - 503: el servicio externo no respondió o respondió con error.
    """
    cleaned = _clean_control_number(control_number)
    if not cleaned:
        return 400, {"message": INVALID_CONTROL_MESSAGE}
    if not CONTROL_NUMBER_RE.match(cleaned):
        return 400, {"message": INVALID_FORMAT_MESSAGE}

    ip = (client_ip or "unknown").strip() or "unknown"
    for key, (limit, window) in (
        (f"ip:{ip}", LIMITS["ip"]),
        (f"control_number:{cleaned.lower()}", LIMITS["control_number"]),
        ("global", LIMITS["global"]),
    ):
        if not _limiter.allow(key, limit, window):
            current_app.logger.info("forgot-password limitado (%s)", key)
            return 429, {"message": RATE_LIMIT_MESSAGE}

    try:
        response = requests.post(
            EXTERNAL_FORGOT_URL,
            json={"username": cleaned},
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=EXTERNAL_TIMEOUT_SECONDS,
        )
    except requests.exceptions.RequestException as exc:
        current_app.logger.warning("forgot-password: 8091 no responde: %s", exc)
        return 503, {"message": EXTERNAL_UNAVAILABLE_MESSAGE}

    if response.status_code == 429:
        # El servicio externo aplicó su propio límite; no filtrar más detalle.
        return 429, {"message": RATE_LIMIT_MESSAGE}

    if not 200 <= response.status_code < 300:
        # 4xx/5xx distintos de 429: no se revela el motivo (podría indicar si
        # el número existe); se reporta como servicio no disponible.
        current_app.logger.warning(
            "forgot-password: 8091 respondió %s", response.status_code
        )
        return 503, {"message": EXTERNAL_UNAVAILABLE_MESSAGE}

    return 200, {"message": GENERIC_SUCCESS_MESSAGE}
