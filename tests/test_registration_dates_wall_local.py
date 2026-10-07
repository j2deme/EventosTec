"""Fechas de preregistro persistidas en hora local naive.

Regla de escritura (ver `docs/TIMEZONE_FIX.md`): las columnas `datetime` guardan
el **wall time local** de la aplicación. `registration_date` y
`confirmation_date` se escribían con `db.func.now()`, que con el servidor MySQL
en UTC dejaba la hora 6 h adelantada: en el modal del admin la "Fecha de
registro / confirmación" no coincidía con la hora real del evento.
"""

import re
from datetime import datetime, timezone
from pathlib import Path

from app import db
from app.models.attendance import Attendance
from app.models.registration import Registration
from app.services.attendance_service import (
    calculate_attendance_percentage,
    sync_registration_status,
)
from app.utils.datetime_utils import db_now_local

TOLERANCE_SECONDS = 120


def _assert_close_to_local(stored, label):
    """El valor persistido debe ser ~ahora en hora local naive."""
    expected = db_now_local()
    delta = abs((stored - expected).total_seconds())
    assert delta <= TOLERANCE_SECONDS, (
        f"{label} no quedó en hora local: guardado={stored} esperado={expected}"
    )

    # Cuando la TZ de la app no es UTC (producción: America/Mexico_City) el
    # valor además NO debe parecerse a la hora UTC del servidor MySQL.
    utc_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    if abs((expected - utc_naive).total_seconds()) > 3600:
        utc_delta = abs((stored - utc_naive).total_seconds())
        assert utc_delta > 3600, f"{label} se guardó como si fuera UTC: {stored}"


def test_registration_date_defaults_to_local_wall_time(
    app, sample_data, activity_factory
):
    """Al crear un preregistro, `registration_date` usa el default en Python."""
    with app.app_context():
        activity = activity_factory(name="Actividad Fecha Registro")
        reg = Registration(
            student_id=sample_data["student_id"], activity_id=activity.id
        )
        db.session.add(reg)
        db.session.commit()

        db.session.refresh(reg)
        assert reg.registration_date is not None
        _assert_close_to_local(reg.registration_date, "registration_date")


def test_re_register_updates_registration_date_in_local_time(
    app, sample_data, activity_factory
):
    """Re-registrar un cancelado actualiza `registration_date` en hora local."""
    with app.app_context():
        activity = activity_factory(name="Actividad Re-registro")
        reg = Registration(
            student_id=sample_data["student_id"],
            activity_id=activity.id,
            status="Cancelado",
            # Valor antiguo escrito en UTC (6 h desfasado) para verificar el fix
            registration_date=datetime(2024, 1, 1, 16, 0, 0),
        )
        db.session.add(reg)
        db.session.commit()

        from app.services.registration_service import create_registration_simple

        ok, updated = create_registration_simple(sample_data["student_id"], activity.id)
        assert ok is True, updated

        db.session.refresh(updated)
        _assert_close_to_local(updated.registration_date, "registration_date")


def test_confirmation_date_from_checkout_is_local(app, sample_data, activity_factory):
    """El checkout escribe `confirmation_date` en hora local, no en UTC."""
    with app.app_context():
        activity = activity_factory(
            name="Conferencia Fechas",
            start_datetime=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc),
            duration_hours=1.0,
        )
        reg = Registration(
            student_id=sample_data["student_id"], activity_id=activity.id
        )
        attendance = Attendance(
            student_id=sample_data["student_id"],
            activity_id=activity.id,
            check_in_time=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            check_out_time=datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc),
        )
        db.session.add_all([reg, attendance])
        db.session.commit()

        calculate_attendance_percentage(attendance.id)
        db.session.commit()

        db.session.refresh(attendance)
        assert attendance.attendance_percentage == 100.0

        sync_registration_status(attendance)
        db.session.commit()

        db.session.refresh(reg)
        assert reg.status == "Asistió"
        assert reg.confirmation_date is not None
        _assert_close_to_local(reg.confirmation_date, "confirmation_date")


def test_no_registration_dates_written_with_db_func_now():
    """Guard: ninguna fecha de preregistro se escribe con `db.func.now()`.

    `db.func.now()` se ejecuta en el servidor MySQL (UTC en producción), lo que
    rompe la convención de escritura en hora local de la aplicación.
    """
    root = Path(__file__).resolve().parents[1] / "app"
    pattern = re.compile(
        r"(registration_date|confirmation_date)\s*=\s*db\.func\.now\(\)"
    )
    offenders = []
    for path in sorted(root.rglob("*.py")):
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if pattern.search(line):
                offenders.append(f"{path.relative_to(root.parent)}:{lineno}")

    assert not offenders, (
        "Escrituras con db.func.now() (hora del servidor, UTC en producción):\n"
        + "\n".join(offenders)
    )
