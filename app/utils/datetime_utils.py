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
