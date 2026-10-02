from datetime import datetime, timezone
from marshmallow import ValidationError
from app.services.settings_manager import AppSettings


def parse_datetime_with_timezone(dt_string):
    """Parsea una cadena de fecha o datetime y asegura que tenga zona horaria UTC.

    Acepta objetos datetime o strings en ISO o en formato '%Y-%m-%d %H:%M:%S'.
    Si no puede parsear lanza ValidationError para señales de inputs inválidos.
    """
    if dt_string is None:
        return None

    if isinstance(dt_string, datetime):
        if dt_string.tzinfo is None:
            return dt_string.replace(tzinfo=timezone.utc)
        return dt_string

    if isinstance(dt_string, str):
        # Intentar parsear con ISO
        try:
            dt = datetime.fromisoformat(dt_string)
        except Exception:
            try:
                dt = datetime.strptime(dt_string, "%Y-%m-%d %H:%M:%S")
            except Exception:
                raise ValidationError(f"Formato de fecha inválido: {dt_string}")

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt

    raise ValidationError(f"Valor de fecha no reconocido: {dt_string}")


def localize_naive_datetime(dt, app_timezone="America/Mexico_City"):
    """
    Localiza un datetime naive al timezone de la aplicación y lo convierte a UTC.

    Args:
        dt: datetime object (puede ser naive o timezone-aware)
        app_timezone: string con el nombre del timezone (default: America/Mexico_City)

    Returns:
        datetime objeto timezone-aware en UTC

    Note:
        Si dt ya tiene timezone, se convierte a UTC sin cambiar la interpretación.
        Si dt es naive, se asume que está en app_timezone y se convierte a UTC.
    """
    if dt is None:
        return None

    # Si ya tiene timezone, convertir a UTC
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc)

    # Si es naive, localizarlo al timezone de la app
    try:
        import zoneinfo

        tz = zoneinfo.ZoneInfo(app_timezone)
    except (ImportError, Exception):
        # Fallback: usar pytz si zoneinfo no está disponible (Python < 3.9)
        try:
            import pytz

            tz = pytz.timezone(app_timezone)
            localized = tz.localize(dt)
            return localized.astimezone(timezone.utc)
        except ImportError:
            # Si no hay pytz ni zoneinfo, asumir UTC (no ideal pero es el fallback)
            return dt.replace(tzinfo=timezone.utc)

    # Localizar y convertir a UTC
    localized = dt.replace(tzinfo=tz)
    return localized.astimezone(timezone.utc)


def safe_iso(dt):
    """Return an ISO 8601 string for a datetime-like value in a safe way.

    Behavior:
      - If dt is falsy -> return None
      - If dt is a naive datetime -> interpret it in APP_TIMEZONE and convert to UTC
      - If dt is an aware datetime -> convert to UTC and isoformat
      - For strings, try to parse with fromisoformat and treat accordingly; otherwise return the original string trimmed
      - On unexpected errors, return None

    .. warning:: Solo para lectura/serialización de salida. Para construir
        payloads que luego se persisten (schema.load) usar iso_for_write():
        aquí un naive se convierte a UTC y, al guardarlo, quedaría desplazado.
    """
    if not dt:
        return None

    try:
        app_tz = None
        try:
            app_tz = AppSettings.app_timezone()
        except Exception:
            app_tz = "America/Mexico_City"

        # python datetime
        if isinstance(dt, datetime):
            if dt.tzinfo is None:
                localized_dt = localize_naive_datetime(dt, app_tz)
                if localized_dt is None:
                    return None
                return localized_dt.isoformat()
            return dt.astimezone(timezone.utc).isoformat()

        # attempt to parse ISO-like strings
        if isinstance(dt, str):
            s = dt.strip()
            if not s:
                return None
            try:
                parsed = datetime.fromisoformat(s)
                if parsed.tzinfo is None:
                    parsed = localize_naive_datetime(parsed, app_tz)
                    if parsed is None:
                        return s
                return parsed.astimezone(timezone.utc).isoformat()
            except Exception:
                # not ISO parseable, return trimmed string as best-effort
                return s

        # Fallback: try to call isoformat if present
        try:
            if hasattr(dt, "isoformat") and callable(dt.isoformat):
                return dt.isoformat()
        except Exception:
            pass

        # Last resort: stringify
        try:
            return str(dt)
        except Exception:
            return None
    except Exception:
        return None


def iso_for_write(dt):
    """Serializa un datetime-like a ISO 8601 para payloads de ESCRITURA.

    A diferencia de safe_iso() —helper de LECTURA que interpreta los naive como
    hora local y los convierte a UTC—, esta función preserva el wall time: un
    datetime naive se publica "fingido como UTC" (misma convención que
    parse_datetime_with_timezone() en el endpoint manual de creación) para que
    create_activity() lo persista como hora local naive en MySQL.

    Usar safe_iso() para construir un payload que se persiste desplaza las
    horas al guardar (+6 h con America/Mexico_City): fue el bug de la
    importación batch de actividades del 46° aniversario.

    Args:
        dt: datetime naive/aware, string ISO o valor ausente.

    Returns:
        str ISO 8601 conservando la hora local, el resultado de safe_iso()
        como mejor esfuerzo si el valor no se puede parsear, o None.
    """
    if not dt:
        return None
    try:
        return parse_datetime_with_timezone(dt).isoformat()
    except ValidationError:
        return safe_iso(dt)
