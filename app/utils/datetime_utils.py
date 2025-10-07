from datetime import datetime, timezone
from marshmallow import ValidationError


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
                dt = datetime.strptime(dt_string, '%Y-%m-%d %H:%M:%S')
            except Exception:
                raise ValidationError(
                    f"Formato de fecha inválido: {dt_string}")

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt

    raise ValidationError(f"Valor de fecha no reconocido: {dt_string}")


def localize_naive_datetime(dt, app_timezone='America/Mexico_City'):
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

