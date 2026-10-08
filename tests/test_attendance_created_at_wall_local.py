"""`attendances.created_at` / `updated_at` persistidos en hora local naive.

Regla de escritura (ver `docs/TIMEZONE_FIX.md`): las columnas `datetime` guardan
el **wall time local** de la aplicación. Estas dos columnas se escribían con
`db.func.now()` —el reloj de MySQL, que corre en UTC— y `created_at` es la
**Fecha registro** que muestra el admin de asistencias: un check-in real de
13:19 se guardaba como 19:19 y aparecía 6 h adelantado en pantalla.
"""

from datetime import datetime, timezone
from pathlib import Path

from app import db
from app.models.attendance import Attendance
from app.services.settings_manager import AppSettings
from app.utils.datetime_utils import app_today, db_now_local, safe_iso

TOLERANCE_SECONDS = 120


def _app_tz():
    try:
        import zoneinfo

        return zoneinfo.ZoneInfo(AppSettings.app_timezone())
    except Exception:
        import pytz

        return pytz.timezone(AppSettings.app_timezone())


def _assert_close_to_local(stored, label):
    """El valor persistido debe ser ~ahora en hora local naive."""
    expected = db_now_local()
    delta = abs((stored - expected).total_seconds())
    assert delta <= TOLERANCE_SECONDS, (
        f"{label} no quedó en hora local: guardado={stored} esperado={expected}"
    )

    # Con la TZ de la app distinta de UTC (producción: America/Mexico_City) el
    # valor además NO debe parecerse a la hora UTC del servidor MySQL.
    utc_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    if abs((expected - utc_naive).total_seconds()) > 3600:
        utc_delta = abs((stored - utc_naive).total_seconds())
        assert utc_delta > 3600, f"{label} se guardó como si fuera UTC: {stored}"


def test_created_at_defaults_to_local_wall_time(app, sample_data, activity_factory):
    """Al crear una asistencia, `created_at` usa el default en Python."""
    with app.app_context():
        activity = activity_factory(name="Actividad Created At")
        att = Attendance(
            student_id=sample_data["student_id"],
            activity_id=activity.id,
            status="Asistió",
        )
        db.session.add(att)
        db.session.commit()

        db.session.refresh(att)
        assert att.created_at is not None
        _assert_close_to_local(att.created_at, "created_at")


def test_updated_at_defaults_and_onupdate_are_local(app, sample_data, activity_factory):
    """`updated_at` se escribe y se refresca en hora local (no con MySQL)."""
    with app.app_context():
        activity = activity_factory(name="Actividad Updated At")
        att = Attendance(
            student_id=sample_data["student_id"],
            activity_id=activity.id,
            status="Parcial",
        )
        db.session.add(att)
        db.session.commit()
        db.session.refresh(att)
        _assert_close_to_local(att.updated_at, "updated_at")

        att.attendance_percentage = 100.0
        db.session.commit()
        db.session.refresh(att)
        _assert_close_to_local(att.updated_at, "updated_at (onupdate)")
        assert att.updated_at >= att.created_at


def test_timestamp_defaults_are_python_side_not_server_clock():
    """Guard: `created_at`/`updated_at` deben tener default en Python.

    Un default solo de servidor (`server_default=db.func.now()`) usa el reloj
    de MySQL (UTC en producción) y rompe la convención de hora local.
    """
    table = Attendance.__table__

    for column_name in ("created_at", "updated_at"):
        default = table.c[column_name].default
        assert default is not None, (
            f"Attendance.{column_name} perdió su default en Python"
        )
        assert callable(default.arg), (
            f"Attendance.{column_name}.default debe ser una función, "
            f"recibido: {default.arg!r}"
        )

    assert table.c.updated_at.onupdate is not None
    assert callable(table.c.updated_at.onupdate.arg)


def test_attendance_model_source_has_no_server_clock_timestamps():
    """Guard de fuente: el modelo no debe asignar timestamps con `db.func.now()`."""
    import re

    path = Path(__file__).resolve().parents[1] / "app" / "models" / "attendance.py"
    src = path.read_text(encoding="utf-8")
    offenders = [
        lineno
        for lineno, line in enumerate(src.splitlines(), start=1)
        if re.search(r"(created_at|updated_at)\s*=\s*db\.func\.now\(\)", line)
    ]
    assert not offenders, (
        "asignación de timestamp con db.func.now() (hora del servidor): "
        f"líneas {offenders}"
    )


def test_list_endpoint_returns_local_wall_time(
    client, auth_headers, app, sample_data, activity_factory
):
    """El admin recibe `created_at` tal y como se guardó en hora local.

    Regresión del bug de la "Fecha registro" +6 h: la columna venía en hora
    UTC del servidor y el frontend la mostraba como hora local.
    """
    with app.app_context():
        activity = activity_factory(name="Actividad Lista")
        att = Attendance(
            student_id=sample_data["student_id"],
            activity_id=activity.id,
            status="Asistió",
        )
        db.session.add(att)
        db.session.commit()
        db.session.refresh(att)
        stored = att.created_at

    response = client.get("/api/attendances/", headers=auth_headers)
    assert response.status_code == 200
    payload = response.get_json()
    row = next(
        (r for r in payload["attendances"] if r["id"] == att.id),
        None,
    )
    assert row is not None, "la asistencia creada no aparece en el listado"

    parsed = datetime.fromisoformat(row["created_at"])
    delta = abs((parsed.replace(tzinfo=None) - stored).total_seconds())
    assert delta <= TOLERANCE_SECONDS, (
        f"created_at del API desfasado: api={row['created_at']} db={stored}"
    )

    # `safe_iso` (usado por to_dict) debe interpretarlo como hora local y
    # devolver el mismo instante, no +6 h.
    iso = datetime.fromisoformat(safe_iso(stored))
    roundtrip = iso.astimezone(_app_tz()).replace(tzinfo=None)
    delta = abs((roundtrip - stored).total_seconds())
    assert delta <= TOLERANCE_SECONDS


def test_app_today_uses_app_timezone():
    """`app_today()` devuelve la fecha de HOY en la zona de la aplicación."""
    expected = datetime.now(timezone.utc).astimezone(_app_tz()).date()
    assert app_today() == expected
