"""Contexto de la lista de asistencia imprimible.

Fuente única de verdad para la plantilla ``admin/reports/attendance_list.html``.
La usan dos rutas:

- ``GET /api/reports/attendance_list`` (admin, requiere JWT)
- ``GET /public/attendance-list/<activity_ref>`` (vista pública de Jefes de
  Carrera, resuelta por slug o ID numérico de la actividad)

Al compartir el builder, ambas vistas imprimen exactamente la misma lista
(mismo orden, mismos estados y misma detección de actividades multiday).
"""

from datetime import timedelta

from flask import current_app

from app import db
from app.models.event import Event
from app.models.registration import Registration
from app.models.student import Student
from app.utils.datetime_utils import localize_naive_datetime


def build_attendance_list_context(activity) -> dict:
    """Construye el contexto para la plantilla imprimible de la actividad.

    Retorna::

        {
          "event": Event | None,
          "activity": Activity,
          "students": [ {id, full_name, control_number, career}, ... ],
          "dates": [date | None, ...],   # día(s) de la actividad
          "multi_day": bool,
        }

    Los preregistros se ordenan por ``Student.full_name`` (mismo criterio que
    históricamente usaba el reporte de admin).
    """
    event = db.session.get(Event, activity.event_id) if activity.event_id else None

    # Preregistros ordenados por apellido/nombre (student.full_name)
    regs = (
        db.session.query(Registration)
        .filter(Registration.activity_id == activity.id)
        .join(Student)
        .order_by(Student.full_name)
        .all()
    )

    students = []
    for r in regs:
        # Cargar explícitamente el estudiante para evitar supuestos del ORM
        s = db.session.get(Student, r.student_id)
        if not s:
            continue
        students.append(
            {
                "id": s.id,
                "full_name": s.full_name,
                "control_number": s.control_number,
                "career": s.career,
            }
        )

    # Determinar si la actividad abarca varios días (localizar datetimes naive)
    multi_day = False
    dates = []
    try:
        app_tz = current_app.config.get("APP_TIMEZONE", "America/Mexico_City")
        start = activity.start_datetime
        end = activity.end_datetime
        sdt = localize_naive_datetime(start, app_tz) if start is not None else None
        edt = localize_naive_datetime(end, app_tz) if end is not None else None
        if sdt and edt and sdt.date() != edt.date():
            multi_day = True
            # Lista de fechas inclusiva
            delta = (edt.date() - sdt.date()).days
            dates = [sdt.date() + timedelta(days=i) for i in range(delta + 1)]
        else:
            dates = [
                (
                    sdt.date()
                    if sdt is not None
                    else (edt.date() if edt is not None else None)
                )
            ]
    except Exception:
        dates = []

    return {
        "event": event,
        "activity": activity,
        "students": students,
        "dates": dates,
        "multi_day": multi_day,
    }
