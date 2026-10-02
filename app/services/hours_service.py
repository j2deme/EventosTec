"""Cálculo unificado de horas de participación por estudiante.

Fuente única de verdad para el umbral de crédito complementario y los
reportes de horas. Semántica:

- Participación válida: ``Registration.status`` en ("Confirmado", "Asistió")
  **o** ``Attendance.status == "Asistió"`` (check-in walk-in).
- Cada actividad se cuenta UNA sola vez por estudiante (dedup), aunque existan
  Registration y Attendance para la misma actividad.
- Los totales se redondean a 2 decimales ANTES de comparar umbrales
  (evita el clásico ``9.999999999 < 10`` por aritmética de punto flotante).
"""

from app import db
from app.models.activity import Activity
from app.models.attendance import Attendance
from app.models.registration import Registration
from app.models.student import Student

# Umbral único del crédito complementario (horas)
CREDIT_MIN_HOURS = 10.0

# Statuses de Registration que acreditan participación
COUNTED_REGISTRATION_STATUSES = ("Confirmado", "Asistió")

# Status de Attendance que acredita participación (walk-ins)
COUNTED_ATTENDANCE_STATUS = "Asistió"


def meets_credit_threshold(total_hours, threshold=CREDIT_MIN_HOURS) -> bool:
    """Compara un total de horas con el umbral usando redondeo a 2 decimales."""
    try:
        total = round(float(total_hours or 0), 2)
    except (TypeError, ValueError):
        return False
    return total >= float(threshold)


def earliest_crossing_event(
    hours_by_event, chronological_event_ids, threshold=CREDIT_MIN_HOURS
):
    """Evento (según el orden cronológico dado) en el que la suma acumulada
    alcanza por primera vez el umbral.

    Devuelve el ``event_id`` del cruce, o ``None`` si nunca se alcanza.
    Se usa para la exclusión derivada de estudiantes ya acreditados: si el
    cruce ocurre en un evento ANTERIOR al último evaluado, el estudiante ya
    quedó acreditado antes.
    """
    total = 0.0
    for eid in chronological_event_ids:
        total += float(hours_by_event.get(eid, 0) or 0)
        if meets_credit_threshold(total, threshold):
            return eid
    return None


def compute_student_hours(
    event_ids=None,
    student_id=None,
    career=None,
    search=None,
    min_hours=None,
):
    """Calcula las horas de participación por estudiante (fuente única).

    Parámetros:
      - event_ids: iterable de IDs de evento (None = todos los eventos).
      - student_id: limita el cálculo a un estudiante (None = todos).
      - career: subcadena case-insensitive sobre la carrera (o "Sin especificar").
      - search: subcadena case-insensitive sobre número de control o nombre.
      - min_hours: mínimo exigido sobre el total redondeado (None/0 = sin mínimo).

    Retorna una lista ordenada por ``full_name`` de dicts con:
      ``id``, ``control_number``, ``full_name``, ``career`` (crudo, puede ser
      None), ``email`` (crudo, puede ser None), ``total_hours`` (redondeado a 2),
      ``activities_count``, ``hours_by_event`` ({event_id: horas}) y
      ``activities_by_event`` ({event_id: cantidad}).
    """
    # 1) Participaciones desde Registration (preregistrados/confirmados)
    reg_query = (
        db.session.query(
            Student.id.label("sid"),
            Student.control_number,
            Student.full_name,
            Student.career,
            Student.email,
            Activity.id.label("aid"),
            Activity.event_id.label("eid"),
            Activity.duration_hours.label("dur"),
        )
        .join(Registration, Registration.student_id == Student.id)
        .join(Activity, Activity.id == Registration.activity_id)
        .filter(Registration.status.in_(COUNTED_REGISTRATION_STATUSES))
    )

    # 2) Participaciones desde Attendance (walk-ins / check-in directo)
    att_query = (
        db.session.query(
            Attendance.student_id.label("sid"),
            Student.control_number,
            Student.full_name,
            Student.career,
            Student.email,
            Activity.id.label("aid"),
            Activity.event_id.label("eid"),
            Activity.duration_hours.label("dur"),
        )
        .join(Activity, Activity.id == Attendance.activity_id)
        .join(Student, Student.id == Attendance.student_id)
        .filter(Attendance.status == COUNTED_ATTENDANCE_STATUS)
    )

    if event_ids:
        reg_query = reg_query.filter(Activity.event_id.in_(list(event_ids)))
        att_query = att_query.filter(Activity.event_id.in_(list(event_ids)))
    if student_id is not None:
        reg_query = reg_query.filter(Student.id == student_id)
        att_query = att_query.filter(Student.id == student_id)

    students_map = {}

    def ensure_student(sid, control_number, full_name, career_val, email):
        if sid not in students_map:
            students_map[sid] = {
                "id": sid,
                "control_number": control_number,
                "full_name": full_name,
                "career": career_val,
                "email": email,
                "activities": set(),
                "hours_by_event": {},
                "activities_by_event": {},
            }
        return students_map[sid]

    def add_participation(sid, control_number, full_name, career_val, email, aid, eid, dur):
        if aid is None:
            return
        info = ensure_student(sid, control_number, full_name, career_val, email)
        if aid in info["activities"]:
            # Ya contada: misma actividad con Registration y Attendance
            return
        info["activities"].add(aid)
        info["hours_by_event"][eid] = info["hours_by_event"].get(eid, 0.0) + dur
        info["activities_by_event"][eid] = info["activities_by_event"].get(eid, 0) + 1

    for r in reg_query.all():
        add_participation(
            r.sid,
            r.control_number,
            r.full_name,
            r.career,
            r.email,
            r.aid,
            r.eid,
            float(r.dur or 0),
        )

    for a in att_query.all():
        add_participation(
            a.sid,
            a.control_number,
            a.full_name,
            a.career,
            a.email,
            a.aid,
            a.eid,
            float(a.dur or 0),
        )

    # Filtros y construcción del resultado
    results = []
    career_q = (career or "").strip().lower()
    search_q = (search or "").strip().lower()
    min_h = float(min_hours or 0)

    for info in students_map.values():
        display_career = info["career"] or "Sin especificar"
        if career_q and career_q not in display_career.lower():
            continue
        if search_q and not (
            search_q in (info["control_number"] or "").lower()
            or search_q in (info["full_name"] or "").lower()
        ):
            continue
        total = round(sum(info["hours_by_event"].values()), 2)
        if total < min_h:
            continue
        results.append(
            {
                "id": info["id"],
                "control_number": info["control_number"],
                "full_name": info["full_name"],
                "career": info["career"],
                "email": info["email"],
                "total_hours": total,
                "activities_count": len(info["activities"]),
                "hours_by_event": {
                    eid: round(hours, 2)
                    for eid, hours in info["hours_by_event"].items()
                },
                "activities_by_event": dict(info["activities_by_event"]),
            }
        )

    results.sort(key=lambda x: (x.get("full_name") or "", x.get("control_number") or ""))
    return results


def load_overrides_map():
    """Mapa ``student_id -> decision`` de los overrides manuales.

    Defensivo: si la tabla ``credit_overrides`` aún no existe (migración
    pendiente en producción), devuelve ``{}`` y registra un warning; la lista
    de créditos sigue funcionando sin overrides en lugar de fallar.
    """
    try:
        from app.models.credit_override import CreditOverride

        return {o.student_id: o.decision for o in CreditOverride.query.all()}
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        try:
            from flask import current_app

            current_app.logger.warning(
                "Tabla credit_overrides no disponible (migracion pendiente?); "
                "la lista de creditos se calculara sin overrides."
            )
        except Exception:
            pass
        return {}


def compute_credit_rows(
    event_ids, chronological_ids=None, career=None, overrides=None
):
    """Filas de la lista de créditos complementarios (fuente única).

    Pipeline:
      1. Horas unificadas por evento (sin mínimo: el umbral se aplica en este
         paso para poder forzar la inclusión vía override).
      2. Exclusión derivada: si el cruce de 10 h ocurre en un evento anterior
         al último cronológico → ya acreditado → se omite.
      3. Umbral: total redondeado >= CREDIT_MIN_HOURS.
      4. Overrides manuales: 'exclude' omite siempre; 'include' fuerza la
         inclusión aunque falle (2) o (3), incluso sin participaciones en los
         eventos seleccionados (fila sintética con 0 h).

    Parámetros:
      - event_ids: eventos seleccionados (universo de horas).
      - chronological_ids: orden cronológico para la regla de exclusión
        (default: el orden de event_ids).
      - career: subcadena de carrera (misma semántica que compute_student_hours).
      - overrides: dict {student_id: "include"|"exclude"}.

    Retorna ``(rows, stats)``, donde ``rows`` tiene el mismo formato que
    compute_student_hours y ``stats`` es
    ``{"excluded_already_credited": int, "excluded_by_override": int}``.
    """
    event_ids = list(event_ids or [])
    chronological_ids = list(chronological_ids or event_ids)
    overrides = dict(overrides or {})

    rows = compute_student_hours(event_ids=event_ids, career=career)
    stats = {"excluded_already_credited": 0, "excluded_by_override": 0}
    last_event_id = chronological_ids[-1] if chronological_ids else None

    kept = []
    kept_ids = set()
    for row in rows:
        decision = overrides.get(row["id"])
        if decision == "exclude":
            stats["excluded_by_override"] += 1
            continue
        crossing = earliest_crossing_event(
            row["hours_by_event"], chronological_ids, CREDIT_MIN_HOURS
        )
        derived_excluded = (
            crossing is not None
            and last_event_id is not None
            and crossing != last_event_id
        )
        if derived_excluded and decision != "include":
            stats["excluded_already_credited"] += 1
            continue
        if decision != "include" and not meets_credit_threshold(row["total_hours"]):
            continue
        kept.append(row)
        kept_ids.add(row["id"])

    # Overrides 'include' de estudiantes sin participaciones en la selección
    for sid, decision in overrides.items():
        if decision != "include" or sid in kept_ids:
            continue
        student = db.session.get(Student, sid)
        if student is None:
            continue
        display_career = student.career or "Sin especificar"
        if career and career.strip().lower() not in display_career.lower():
            continue
        kept.append(
            {
                "id": sid,
                "control_number": student.control_number,
                "full_name": student.full_name,
                "career": student.career,
                "email": student.email,
                "total_hours": 0.0,
                "activities_count": 0,
                "hours_by_event": {},
                "activities_by_event": {},
            }
        )
        kept_ids.add(sid)

    kept.sort(key=lambda x: (x.get("full_name") or "", x.get("control_number") or ""))
    return kept, stats
