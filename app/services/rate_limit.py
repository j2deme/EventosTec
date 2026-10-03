"""Rate-limit en memoria (ventana deslizante) por clave.

Contador genérico reutilizable por los endpoints que necesitan frenar fuerza
bruta o abuso sin depender de infraestructura externa (Redis, tabla nueva).

Limitaciones conocidas (aceptadas a propósito):

- El estado vive en memoria del **proceso**. Con ``gunicorn -w 4`` cada worker
  lleva su propia cuenta, así que el límite real puede ser hasta Nx el
  configurado. Los límites se eligen pensando en esa cota superior.
- No sobrevive a un reinicio del proceso (limpiar es aceptable: solo se
  pierden las cuentas, nunca datos).
"""

from __future__ import annotations

import threading
import time
from collections import deque


class SlidingWindowLimiter:
    """Contador deslizante por clave, en memoria y por proceso."""

    def __init__(self, max_keys: int = 10_000):
        self._lock = threading.Lock()
        self._hits: dict[str, dict] = {}
        self._max_keys = max_keys

    def allow(self, key: str, limit: int, window: int) -> bool:
        """Suma un intento para `key`; False si ya alcanzó `limit` en `window`."""
        now = time.monotonic()
        with self._lock:
            entry = self._hits.get(key)
            if entry is None:
                if len(self._hits) >= self._max_keys:
                    self._evict_locked(now)
                entry = {"window": window, "times": deque()}
                self._hits[key] = entry
            times = entry["times"]
            cutoff = now - entry["window"]
            while times and times[0] <= cutoff:
                times.popleft()
            if len(times) >= limit:
                return False
            times.append(now)
            return True

    def _evict_locked(self, now: float) -> None:
        """Suelta claves cuyos intentos ya vencieron para no crecer sin límite."""
        expired = [
            key
            for key, entry in self._hits.items()
            if not entry["times"] or now - entry["times"][-1] > entry["window"]
        ]
        for key in expired:
            del self._hits[key]
        # Caso límite (claves activas todas): se limpia todo antes que fallar.
        if len(self._hits) >= self._max_keys:
            self._hits.clear()

    def reset(self) -> None:
        """Vacía todos los contadores (principalmente para tests)."""
        with self._lock:
            self._hits.clear()
