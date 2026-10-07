"""Validación de credenciales de estudiantes contra la plataforma MAB (8091).

Fuente única para los dos puntos de entrada que validan credenciales de
estudiantes:

- ``POST /api/auth/student-login`` (login del portal del estudiante)
- ``POST /api/registrations/self`` (registro in situ / self check-in)

Antes el segundo llamaba al primero por HTTP interno
(``request.host_url + /api/auth/student-login``), lo que dependía de que la
aplicación pudiera alcanzar su propia URL pública (proxy, DNS, TLS) y añadía
una llamada de red por cada registro in situ. Aquí la validación corre **en
proceso** y comparte el rate-limit entre ambos caminos, de modo que un
ataque de fuerza bruta contra un número de control queda frenado aunque
entra por cualquiera de las dos puertas.

Respuestas/errores (mapeados por cada endpoint):

- ``InvalidCredentials``            -> 401
- ``CredentialServiceUnavailable``  -> 503
- ``CredentialsRateLimited``        -> 429
"""

from __future__ import annotations

import requests
from flask import current_app, request

from app import db
from app.models.student import Student
from app.services.rate_limit import SlidingWindowLimiter

EXTERNAL_STUDENT_VALIDATION_URL = "http://apps.tecvalles.mx:8091/api/validate/student"
EXTERNAL_TIMEOUT_SECONDS = 10

# (intentos, ventana_en_segundos) por clave.
# - Por número de control: frena la adivinación de una cuenta concreta.
# - Por IP: frena el barrido de muchos números de control desde un origen.
CREDENTIAL_ATTEMPT_LIMITS: dict[str, tuple[int, int]] = {
    "control_number": (8, 300),
    "ip": (80, 300),
}

RATE_LIMIT_MESSAGE = "Demasiados intentos. Espera unos minutos y vuelve a intentarlo."

_credential_limiter = SlidingWindowLimiter()


class CredentialsRateLimited(Exception):
    """Se superó el límite de intentos de validación de credenciales."""


class InvalidCredentials(Exception):
    """El sistema externo rechazó las credenciales."""


class CredentialServiceUnavailable(Exception):
    """El sistema externo no respondió o devolvió un error no esperado."""


def reset_credential_limits() -> None:
    """Vacía los contadores de intentos (principalmente para tests)."""
    _credential_limiter.reset()


def client_ip() -> str:
    """IP del visitante, considerando proxies inversos si reportan X-Forwarded-For."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        # Primera IP de la cadena: la que agregó el proxy más cercano.
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _enforce_rate_limit(control_number: str, ip: str | None) -> None:
    """Lanza ``CredentialsRateLimited`` si se agotaron los intentos permitidos."""
    limit, window = CREDENTIAL_ATTEMPT_LIMITS["control_number"]
    if not _credential_limiter.allow(
        f"student-credentials:{control_number}", limit, window
    ):
        raise CredentialsRateLimited(control_number)

    ip_limit, ip_window = CREDENTIAL_ATTEMPT_LIMITS["ip"]
    if ip and not _credential_limiter.allow(
        f"student-credentials-ip:{ip}", ip_limit, ip_window
    ):
        raise CredentialsRateLimited(ip)


def validate_student_credentials(
    control_number: str, password: str, *, ip: str | None = None
) -> dict:
    """Valida credenciales de estudiante contra la plataforma MAB.

    Aplica rate-limit antes de llamar al sistema externo. Devuelve el
    ``data`` de la respuesta externa (nombre, carrera, correo) normalizado
    a un dict.

    Raises:
        CredentialsRateLimited: límite de intentos alcanzado.
        InvalidCredentials: credenciales rechazadas.
        CredentialServiceUnavailable: sistema externo inaccesible o con error.
    """
    if ip is None:
        try:
            ip = client_ip()
        except RuntimeError:
            # Sin contexto de request (llamada desde un job/test).
            ip = None

    _enforce_rate_limit(control_number, ip)

    try:
        response = requests.post(
            EXTERNAL_STUDENT_VALIDATION_URL,
            json={"username": control_number, "password": password},
            timeout=EXTERNAL_TIMEOUT_SECONDS,
        )
    except requests.exceptions.RequestException as exc:
        current_app.logger.warning(
            "student-auth: sin respuesta del sistema externo (%s)", exc
        )
        raise CredentialServiceUnavailable(str(exc)) from exc

    if response.status_code == 401:
        raise InvalidCredentials()

    if response.status_code != 200:
        raise CredentialServiceUnavailable(f"status={response.status_code}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise CredentialServiceUnavailable("respuesta no JSON") from exc

    if not (
        isinstance(payload, dict) and payload.get("success") and payload.get("data")
    ):
        raise InvalidCredentials()

    student_info = payload.get("data")
    if not isinstance(student_info, dict):
        raise CredentialServiceUnavailable("estructura inesperada de 'data'")

    return student_info


def upsert_student(control_number: str, student_info: dict) -> Student:
    """Crea o actualiza el ``Student`` local a partir de los datos de MAB.

    No confirma la sesión: el caller decide cuándo hacer commit (cada
    endpoint tiene su propia transacción).
    """
    student = Student.query.filter_by(control_number=control_number).first()
    name = student_info.get("name") or student_info.get("full_name") or ""
    email = student_info.get("email") or ""
    career = (
        student_info.get("career", {}).get("name", "")
        if isinstance(student_info.get("career"), dict)
        else (student_info.get("career") or "")
    )

    if not student:
        # Asignaciones explícitas (sin kwargs) para evitar sorpresas del
        # constructor de SQLAlchemy con campos no soportados.
        student = Student()
        student.control_number = control_number
        student.full_name = name
        student.career = career
        student.email = email
    else:
        if name:
            student.full_name = name
        if career:
            student.career = career
        if email:
            student.email = email

    db.session.add(student)
    return student
