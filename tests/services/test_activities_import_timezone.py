"""La importación batch (create_activities_from_xlsx) preserva la hora local.

Regresión del bug del 46° aniversario: el importador usaba safe_iso() (helper
de LECTURA que convierte naive→UTC) para construir el payload de escritura,
por lo que las actividades importadas desde XLSX se almacenaban +6 h (hora
México) y la UI las mostraba desplazadas, mientras que la creación manual las
guardaba bien. La convención del sistema es almacenar hora local naive en
MySQL (ver docs/TIMEZONE_FIX.md).
"""

from datetime import datetime, timezone
from io import BytesIO
from zoneinfo import ZoneInfo

from openpyxl import Workbook

from app.models.activity import Activity
from app.services.activity_service import BATCH_COLUMNS, create_activities_from_xlsx
from app.services.settings_manager import AppSettings


def _build_xlsx(rows):
    """XLSX en memoria con los encabezados canónicos de BATCH_COLUMNS."""
    headers = [c["header"] for c in BATCH_COLUMNS]
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h) for h in headers])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def test_batch_import_almacena_hora_local_naive(event_factory):
    """Las horas del Excel se guardan tal cual (naive local), no convertidas a UTC.

    Cubre los dos formatos de entrada del importador: celda de fecha de Excel
    (datetime naive) y celda de texto ISO 'AAAA-MM-DD HH:MM'.
    """
    event = event_factory(
        name="46 Aniversario (test tz)",
        start_date=datetime(2026, 10, 1, 0, 0),
        end_date=datetime(2026, 10, 10, 23, 59),
    )

    start = datetime(2026, 10, 8, 9, 0)
    end = datetime(2026, 10, 8, 14, 0)

    buf = _build_xlsx(
        [
            {
                "department": "ISC",
                "name": "Taller hora local (celda fecha)",
                "description": "Fila con celda datetime de Excel",
                "start_datetime": start,
                "end_datetime": end,
                "duration_hours": 5,
                "activity_type": "Taller",
            },
            {
                "department": "ISC",
                "name": "Taller hora local (texto ISO)",
                "description": "Fila con celda de texto",
                "start_datetime": "2026-10-09 13:00",
                "end_datetime": "2026-10-09 18:00",
                "duration_hours": 5,
                "activity_type": "Taller",
            },
        ]
    )

    report = create_activities_from_xlsx(buf, event_id=event.id, dry_run=False)

    assert report["errors"] == [], report["errors"]
    assert report["created"] == 2

    # Celda datetime: regresión — safe_iso() persistía 15:00 UTC en vez de 09:00.
    act_dt = Activity.query.filter_by(name="Taller hora local (celda fecha)").one()
    assert act_dt.start_datetime == start
    assert act_dt.end_datetime == end
    assert act_dt.start_datetime.tzinfo is None

    # Celda de texto ISO: mismo comportamiento.
    act_txt = Activity.query.filter_by(name="Taller hora local (texto ISO)").one()
    assert act_txt.start_datetime == datetime(2026, 10, 9, 13, 0)
    assert act_txt.end_datetime == datetime(2026, 10, 9, 18, 0)

    # Round-trip de lectura: la API expone la hora local convertida a UTC
    # (igual que la creación manual), que el frontend muestra en hora local.
    app_tz = AppSettings.app_timezone()
    expected_iso = (
        start.replace(tzinfo=ZoneInfo(app_tz)).astimezone(timezone.utc).isoformat()
    )
    assert act_dt.to_dict()["start_datetime"] == expected_iso
