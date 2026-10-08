"""Encabezado de hora del export de Crédito Complementario.

El XLSX generado por ``GET /api/students/complementary-credits/export`` escribe
``Generado el: <dd/mm/aaaa HH:MM>`` en A2. Ese sello debe estar en hora local
de la app: con ``datetime.now(timezone.utc)`` salía 6 h por delante y, entre
las 18:00 y las 24:00 locales, con la fecha de mañana.

Nota: vive en un fichero propio porque ``tests/api/test_students_hours.py``
(el otro test de este endpoint) todavía no pasa ``ruff format`` y tocarlo
arrastraría un reformateo de código sin relación.
"""

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


def test_export_header_uses_local_date(app, client, auth_headers):
    """A2 se estampa con la fecha de hoy en APP_TIMEZONE."""
    event_id = _create_event(app)

    resp = client.get(
        f"/api/students/complementary-credits/export?event_id={event_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert (
        resp.content_type
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    ws = load_workbook(BytesIO(resp.data)).active
    header = ws["A2"].value
    assert isinstance(header, str)
    assert header.startswith("Generado el: ")

    stamp = header.replace("Generado el: ", "").strip()
    parsed = datetime.strptime(stamp, "%d/%m/%Y %H:%M")

    # Nunca falla por falso positivo: solo distingue local de UTC en la
    # franja 18:00–24:00, y en el resto compara la fecha consigo misma.
    assert parsed.strftime("%d/%m/%Y") == app_today().strftime("%d/%m/%Y")
