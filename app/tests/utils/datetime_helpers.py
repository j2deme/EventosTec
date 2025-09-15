from datetime import datetime, timezone


def now_utc() -> datetime:
    """Devuelve la hora actual en UTC como un objeto timezone-aware.

    Uso recomendado en tests para evitar DeprecationWarning y ambigüedades.
    """
    return datetime.now(timezone.utc)
