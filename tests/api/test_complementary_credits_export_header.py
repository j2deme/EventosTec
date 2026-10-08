"""Sello de hora en el export de Crédito Complementario.

El XLSX de ``GET /api/students/complementary-credits/export`` estampa la hora
en dos sitios: la celda A2 (``Generado el: <dd/mm/aaaa HH:MM>``) y el
timestamp del filename de descarga. Ambos deben estar en hora local de la
app: con ``datetime.now(timezone.utc)`` salían 6 h por delante y, entre las
18:00 y las 24:00 locales, con la fecha de mañana.
"""

import re
from datetime import datetime
from io import BytesIO

from openpyxl import load_workbook

from app.utils.datetime_utils import app_today


def _create_event(app):
    """Evento mínimo y existente para que el export no responda 404."""
    from app import db
    from app.models.event import Event

    with app.app_context():
        event = Event(
            name="Evento para el sello",
            description="Solo para que el endpoint tenga qué exportar",
            start_date=datetime(2026, 1, 5, 9, 0, 0),
            end_date=datetime(2026, 1, 5, 17, 0, 0),
            is_active=True,
        )
        db.session.add(event)
        db.session.commit()
        return event.id


def _export(app, client, auth_headers):
    event_id = _create_event(app)
    return client.get(
        f"/api/students/complementary-credits/export?event_id={event_id}",
        headers=auth_headers,
    )


def _assert_local_day(stamp):
    """La fecha del sello debe ser la de hoy en APP_TIMEZONE.

    Nunca falla por falso positivo: solo distingue local de UTC en la franja
    18:00–24:00, y en el resto compara la fecha consigo misma.
    """
    assert stamp == app_today().strftime("%d/%m/%Y")


def test_export_header_uses_local_date(app, client, auth_headers):
    """A2 se estampa con la fecha de hoy en APP_TIMEZONE."""
    resp = _export(app, client, auth_headers)
    assert resp.status_code == 200
    assert (
        resp.content_type
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    ws = load_workbook(BytesIO(resp.data)).active
    header = ws["A2"].value
    assert isinstance(header, str)
    assert header.startswith("Generado el: ")

    parsed = datetime.strptime(
        header.replace("Generado el: ", "").strip(), "%d/%m/%Y %H:%M"
    )
    _assert_local_day(parsed.strftime("%d/%m/%Y"))


def test_export_filename_uses_local_date(app, client, auth_headers):
    """El timestamp del filename de descarga también es en hora local."""
    resp = _export(app, client, auth_headers)
    assert resp.status_code == 200

    disposition = resp.headers.get("Content-Disposition", "")
    match = re.search(r"_(\d{8})_(\d{6})\.xlsx", disposition)
    assert match, f"Content-Disposition sin sello local: {disposition!r}"

    parsed = datetime.strptime(match.group(1), "%Y%m%d")
    _assert_local_day(parsed.strftime("%d/%m/%Y"))
