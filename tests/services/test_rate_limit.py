"""Rate-limit en memoria (ventana deslizante): `allow` y `refund`.

``refund`` existe para que los reintentos inofensivos (auto-registro
duplicado → 409, o rechazo por ventana cerrada con credenciales válidas) no
le quemen la cuota al estudiante.
"""

from app.services.rate_limit import SlidingWindowLimiter


def test_allow_acumula_hasta_el_limite_y_luego_rechaza():
    limiter = SlidingWindowLimiter()

    assert limiter.allow("k", 2, 60) is True
    assert limiter.allow("k", 2, 60) is True
    assert limiter.allow("k", 2, 60) is False


def test_refund_devuelve_un_intento():
    limiter = SlidingWindowLimiter()
    limiter.allow("k", 1, 60)
    assert limiter.allow("k", 1, 60) is False  # cuota agotada

    assert limiter.refund("k") is True

    assert limiter.allow("k", 1, 60) is True


def test_refund_sin_intentos_previos_no_hace_nada():
    limiter = SlidingWindowLimiter()

    assert limiter.refund("k") is False

    limiter.allow("k", 1, 60)
    limiter.reset()
    assert limiter.refund("k") is False


def test_refund_solo_afecta_la_clave_indicada():
    limiter = SlidingWindowLimiter()
    limiter.allow("a", 1, 60)
    limiter.allow("b", 1, 60)

    limiter.refund("a")

    assert limiter.allow("a", 1, 60) is True  # "a" recuperó su intento
    assert limiter.allow("b", 1, 60) is False  # "b" sigue gastado
