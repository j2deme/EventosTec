"""Ventana de auto-registro (self check-in / self-register).

Política de negocio: el formulario público ``/public/self-register/<ref>``
solo permite marcarse presente dentro de un rango configurable alrededor del
inicio de la actividad::

    abre   = inicio - public_self_register_open_minutes_before_start   (default 30)
    cierra = inicio + public_self_register_close_minutes_after_start   (default 20)

Antes solo existía el límite superior, hardcodeado en tres lugares (GET, POST
y el countdown del frontend). Con eso un QR generado días antes dejaba el
check-in abierto *antes* de que la actividad empezara.

Esta función es la **única** fuente de la ventana: la usan la vista del
formulario (para habilitar/ocultar el form y pasar el deadline al countdown)
y el endpoint POST (para aceptar o rechazar el registro), de modo que no
pueden divergir.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from app.services.settings_manager import AppSettings
from app.utils.datetime_utils import localize_naive_datetime

# Estados de la ventana
OPEN = "open"
NOT_OPEN = "not_open"
CLOSED = "closed"

GENERIC_NOT_AVAILABLE_MESSAGE = (
    "El auto-registro para esta actividad ha finalizado o no está disponible."
)


def _app_timezone() -> str:
    try:
        return AppSettings.app_timezone()
    except Exception:
        return "America/Mexico_City"


def _as_utc(value: datetime, tz_name: str) -> Optional[datetime]:
    """Normaliza un datetime (naive en BD o aware) a UTC aware."""
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc)
    return localize_naive_datetime(value, tz_name)


def _local_hhmm(value_utc: Optional[datetime], tz_name: str) -> str:
    """'HH:MM' en la zona de la aplicación, para mensajes al usuario."""
    if value_utc is None:
        return ""
    try:
        import pytz

        local = value_utc.astimezone(pytz.timezone(tz_name))
    except Exception:
        local = value_utc
    return local.strftime("%H:%M")


def self_register_window(activity) -> Optional[Tuple[datetime, datetime]]:
    """Devuelve ``(abre, cierra)`` en UTC aware para la actividad.

    Devuelve ``None`` si la actividad no tiene ``start_datetime`` (sin
    inicio no hay ventana: se comporta como siempre abierto, igual que la
    versión anterior).
    """
    if activity is None:
        return None

    start = getattr(activity, "start_datetime", None)
    if start is None:
        return None

    tz_name = _app_timezone()
    start_utc = _as_utc(start, tz_name)
    if start_utc is None:
        return None

    try:
        before = int(AppSettings.public_self_register_open_minutes_before_start())
    except Exception:
        before = 30
    try:
        after = int(AppSettings.public_self_register_close_minutes_after_start())
    except Exception:
        after = 20

    return (
        start_utc - timedelta(minutes=max(0, before)),
        start_utc + timedelta(minutes=max(0, after)),
    )


def self_register_state(
    activity, now: Optional[datetime] = None
) -> Tuple[str, Optional[datetime], Optional[datetime]]:
    """Estado de la ventana para ``activity``.

    Returns:
        ``(estado, abre, cierra)`` donde estado es ``open`` / ``not_open`` /
        ``closed`` y ``abre``/``cierra`` son datetimes UTC aware (``None`` si
        la actividad no tiene inicio).
    """
    window = self_register_window(activity)
    if window is None:
        return (OPEN, None, None)

    opens_at, closes_at = window
    current = now if now is not None else datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.astimezone(timezone.utc)

    if current < opens_at:
        return (NOT_OPEN, opens_at, closes_at)
    if current > closes_at:
        return (CLOSED, opens_at, closes_at)
    return (OPEN, opens_at, closes_at)


def window_message(
    state: str, opens_at: Optional[datetime], closes_at: Optional[datetime]
) -> Optional[str]:
    """Mensaje friendly para el usuario cuando la ventana no está abierta."""
    tz_name = _app_timezone()
    if state == OPEN:
        return None
    if state == NOT_OPEN:
        hhmm = _local_hhmm(opens_at, tz_name)
        if hhmm:
            return f"El auto-registro aún no abre. Disponible desde las {hhmm}."
        return "El auto-registro aún no está disponible."
    if state == CLOSED:
        hhmm = _local_hhmm(closes_at, tz_name)
        if hhmm:
            return f"La ventana de auto-registro terminó a las {hhmm}."
        return "La ventana de auto-registro ha terminado."
    return GENERIC_NOT_AVAILABLE_MESSAGE
