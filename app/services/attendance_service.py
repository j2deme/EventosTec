from datetime import datetime, timezone, timedelta
from app.utils.datetime_utils import db_now_local, localize_naive_datetime
from app.services.settings_manager import AppSettings
from typing import Iterable, cast

from app.models.attendance import Attendance
from app.models.activity import Activity
from app.services.self_register_service import arrival_tolerance_minutes


def _normalize_external_json(obj):
    """Normalize various shapes returned by external student APIs.

    - If obj is a dict and contains a 'data' dict, return that dict.
    - If obj is a dict and contains a 'student' dict, return that dict.
    - If obj is a list whose first item is a dict, return that first dict.
    - Otherwise return an empty dict or the dict itself when appropriate.
    """
    if isinstance(obj, dict):
        # common wrapper: {"success": true, "data": {...}}
        if isinstance(obj.get("data"), dict):
            return obj.get("data")
        # proxy shape: {"student": {...}}
        if isinstance(obj.get("student"), dict):
            return obj.get("student")
        # already a useful dict
        return obj
    if isinstance(obj, list) and len(obj) > 0 and isinstance(obj[0], dict):
        return obj[0]
    return {}


# Tipos de actividad con control de sesión (check-in/checkout + pausa):
# conferencias donde el asistente puede retirarse un momento y regresar.
# La pausa se habilitó primero solo para "Magistral"; "Conferencia" es el
# mismo caso de uso y también queda habilitado.
SESSION_CONTROL_ACTIVITY_TYPES = ("Magistral", "Conferencia")


def has_session_control(activity) -> bool:
    """True si la actividad admite pausar/reanudar y check-in automático."""
    if activity is None:
        return False
    return getattr(activity, "activity_type", None) in SESSION_CONTROL_ACTIVITY_TYPES


def pause_attendance(attendance_id):
    """Marca la asistencia como pausada."""
    from app import db

    attendance = db.session.get(Attendance, attendance_id)
    if not attendance:
        raise ValueError("Asistencia no encontrada")
    if not attendance.check_in_time:
        raise ValueError("No se puede pausar sin check-in")
    if attendance.check_out_time:
        raise ValueError("No se puede pausar después del check-out")
    if attendance.is_paused:
        raise ValueError("La asistencia ya está pausada")

    attendance.is_paused = True
    attendance.pause_time = db_now_local()
    return attendance


def _ensure_utc(dt):
    """Convierte un datetime (naive en BD o aware) a UTC aware."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc)
    app_timezone = AppSettings.app_timezone()
    return localize_naive_datetime(dt, app_timezone)


def _activity_window_utc(activity):
    """``(inicio, fin)`` en UTC de la actividad según su duración.

    ``fin`` es ``None`` cuando la actividad no tiene ``duration_hours``.
    """
    if activity is None:
        return (None, None)
    start = _ensure_utc(getattr(activity, "start_datetime", None))
    if start is None:
        return (None, None)
    duration = getattr(activity, "duration_hours", None)
    try:
        if duration is None:
            return (start, None)
        return (start, start + timedelta(hours=float(duration)))
    except Exception:
        return (start, None)


def _arrival_utc(attendance):
    """Llegada real del estudiante en UTC aware.

    Usa ``arrival_time`` (columna nueva, fijada una sola vez en el primer
    check-in). En filas antiguas cae al **menor** de ``created_at`` y
    ``check_in_time``: el ``check_in_time`` puede venir plegado por una pausa
    (queda más tarde que la llegada) y el ``created_at`` puede ser posterior
    si la fila se creó antes del check-in (sync/batch), así que el mínimo es
    la cota conservadora: nunca *inventa* un retraso.

    Nota: en filas anteriores al backfill de ``created_at``
    (``tools/backfill_attendance_created_at_local.py``) esa columna todavía
    está en UTC y se lee 6 h tarde; el mínimo con ``check_in_time`` (local)
    amortigua el caso típico.
    """
    arrival = getattr(attendance, "arrival_time", None)
    if arrival is not None:
        return _ensure_utc(arrival)

    candidates = [
        utc
        for utc in (
            _ensure_utc(getattr(attendance, "created_at", None)),
            _ensure_utc(getattr(attendance, "check_in_time", None)),
        )
        if utc is not None
    ]
    return min(candidates) if candidates else None


def _forgiven_late_seconds(attendance, activity, act_start):
    """Segundos de retraso que se **perdonan** al calcular el porcentaje.

    Tolerancia = ``arrival_tolerance_minutes(activity)``: el mismo número que
    cierra la ventana de auto-registro, así la puerta y el crédito no pueden
    divergir. Regla de negocio:

    - El perdón es **incondicional** (no exige haber llegado hasta el final).
      Quien llega dentro de la tolerancia y se queda hasta el final acredita
      el 100% aunque el evento se cierre a la hora programada.
    - Sólo se perdona el *retraso*, nunca la pausa: una salida y regreso
      sigue descontando presencia, aunque el evento se desborde.
    - El crédito se recorta a la duración programada (ver
      ``compute_attendance_metrics``), de modo que el desborde no genera
      horas extra dentro del porcentaje.
    """
    arrival = _arrival_utc(attendance)
    if arrival is None or act_start is None:
        return 0.0

    late_seconds = (arrival - act_start).total_seconds()
    if late_seconds <= 0:
        return 0.0

    try:
        tolerance_seconds = float(arrival_tolerance_minutes(activity)) * 60.0
    except Exception:
        tolerance_seconds = 0.0
    return min(late_seconds, tolerance_seconds)


def _fold_paused_seconds(attendance, until):
    """Segundos de la pausa vigente que caen dentro de la ventana de la actividad.

    Se recorta a la ventana para no descontar tiempo fuera del evento (p. ej.
    una pausa iniciada antes del inicio o que se extiende más allá del fin).
    """
    pause_start = _ensure_utc(attendance.pause_time)
    pause_end = _ensure_utc(until)
    if pause_start is None or pause_end is None:
        return 0.0

    act_start, act_end = _activity_window_utc(getattr(attendance, "activity", None))
    seg_start = pause_start if act_start is None else max(pause_start, act_start)
    seg_end = pause_end if act_end is None else min(pause_end, act_end)
    if seg_end <= seg_start:
        return 0.0
    return (seg_end - seg_start).total_seconds()


def resume_attendance(attendance_id):
    """Reanuda la asistencia y pliega la pausa transcurrida en el check-in.

    ``Attendance`` solo almacena UN intervalo de pausa
    (``pause_time``/``resume_time``): si se pausa, se reanuda y se vuelve a
    pausar, la segunda pausa pisaba la primera y el cálculo descontaba 0 (un
    alumno que sale varias veces quedaba con el 100%). Para soportar N pausas
    sin migrar la tabla, cada segmento reanudado se **pliega en
    ``check_in_time``** (desplazándolo) y los campos de pausa quedan libres
    para el siguiente ciclo; ``created_at`` conserva la hora real de llegada.
    """
    from app import db

    attendance = db.session.get(Attendance, attendance_id)
    if not attendance:
        raise ValueError("Asistencia no encontrada")
    if not attendance.is_paused:
        raise ValueError("La asistencia no está pausada")

    resumed_at = datetime.now(timezone.utc)
    if attendance.check_in_time is not None and attendance.pause_time is not None:
        paused_seconds = _fold_paused_seconds(attendance, resumed_at)
        if paused_seconds > 0:
            attendance.check_in_time = attendance.check_in_time + timedelta(
                seconds=paused_seconds
            )

    attendance.is_paused = False
    attendance.pause_time = None
    attendance.resume_time = None
    return attendance


# Función auxiliar para calcular duración neta (considerando pausas)


def calculate_net_duration_seconds(attendance, end_override=None, now=None):
    """Calcula la duración real en segundos, restando las pausas.

    ``end_override`` permite simular el cierre de sesión (dry-run) sin
    escribir en la asistencia. Una pausa aún abierta descuenta hasta el fin
    efectivo de la sesión (check-out o "ahora"), igual que en el cálculo de
    porcentaje.
    """
    if not attendance.check_in_time:
        return 0

    current = now if now is not None else datetime.now(timezone.utc)
    # Sin check-out, la sesión sigue abierta: se mide hasta ahora.
    end_time = (
        end_override
        if end_override is not None
        else (attendance.check_out_time or current)
    )

    start = _ensure_utc(attendance.check_in_time)
    end = _ensure_utc(end_time)

    total_paused_seconds = 0
    if attendance.pause_time:
        # Un solo intervalo de pausa por fila (los ciclos posteriores se
        # pliegan en check_in_time al reanudar; ver resume_attendance).
        resume_or_end = _ensure_utc(attendance.resume_time or end_time)
        pause_start = _ensure_utc(attendance.pause_time)
        if resume_or_end and pause_start:
            total_paused_seconds = max(0, (resume_or_end - pause_start).total_seconds())

    if not start or not end:
        return 0

    net_duration = (end - start).total_seconds() - total_paused_seconds
    return max(0, net_duration)  # No permitir duraciones negativas


def _status_for_percentage(percentage):
    """Asistió (>= 80%), Parcial (> 0%) o Ausente (0%)."""
    if percentage >= 80:
        return "Asistió"
    if percentage > 0:
        return "Parcial"
    return "Ausente"


def compute_attendance_metrics(
    attendance, activity=None, *, now=None, check_out_override=None
):
    """Calcula ``(porcentaje, estado)`` de una asistencia **sin tocar la BD**.

    Única implementación del cálculo: la usan
    ``calculate_attendance_percentage`` (que persiste) y la vista previa de
    ``batch-checkout`` en dry-run, que antes tenía una copia propia y
    divergía (usaba duración neta en vez de la intersección con la ventana
    de la actividad, y no aplicaba la regla de "pausa >= duración").

    Fórmula (denominador fijo = duración programada, para que nadie que hoy
    acredita "Asistió" baje de categoría):

    ==========  ==========================================================
    presencia   ``|[llegada, salida] ∩ [inicio, fin] programados| - pausas``
    perdón      ``min(max(0, llegada - inicio), tolerancia)`` (incondicional)
    crédito     ``min(duración programada, presencia + perdón)``
    porcentaje  ``100 * crédito / duración programada``
    ==========  ==========================================================

    La **tolerancia** es la misma que cierra la ventana de auto-registro
    (``self_register_service.arrival_tolerance_minutes``), y el retraso se
    mide con ``arrival_time`` (no con ``check_in_time``, que las pausas
    desplazan). El tope en el fin programado hace que un evento que se
    desborda no "rescate" pausas ni salidas tempranas: el desborde queda como
    dato informativo (``activities.actual_end_datetime``).

    Args:
        attendance: fila a evaluar (no se modifica).
        activity: actividad a evaluar; por defecto ``attendance.activity``.
        now: instante de referencia (por defecto, ahora en UTC).
        check_out_override: simula el cierre de sesión sin escribirlo
            (dry-run o checkout que se está por persistir).
    """
    if attendance is None:
        return None

    pres_start = _ensure_utc(attendance.check_in_time)
    effective_check_out = (
        check_out_override
        if check_out_override is not None
        else attendance.check_out_time
    )
    pres_end = _ensure_utc(effective_check_out)

    # Sin tiempos válidos no se puede calcular (y no se modifica nada)
    if not pres_start or not pres_end:
        return None

    if activity is None:
        activity = getattr(attendance, "activity", None)
    if not activity:
        return None

    current = now if now is not None else datetime.now(timezone.utc)
    act_start, act_end = _activity_window_utc(activity)

    # Sin inicio o duración: caemos al comportamiento legacy (duración neta)
    if not act_start or not act_end:
        net_duration_seconds = calculate_net_duration_seconds(
            attendance, end_override=effective_check_out, now=current
        )
        expected_duration_seconds = (activity.duration_hours or 0) * 3600
        if expected_duration_seconds > 0:
            percentage = (net_duration_seconds / expected_duration_seconds) * 100
            percentage = round(max(0, percentage), 2)
            return (percentage, _status_for_percentage(percentage))
        return (100.0, "Asistió")

    # intersección entre la ventana de presencia y la programada
    window_start = max(pres_start, act_start)
    window_end = min(pres_end, act_end)
    overlap_seconds = max(0, (window_end - window_start).total_seconds())

    # segundos de pausa que caen dentro de la ventana calculada
    paused_seconds = 0
    if attendance.pause_time:
        pause_start = _ensure_utc(attendance.pause_time)
        pause_end = _ensure_utc(
            attendance.resume_time or effective_check_out or current
        )
        ps = max(pause_start, window_start) if pause_start and window_start else None
        pe = min(pause_end, window_end) if pause_end and window_end else None
        if ps and pe and pe > ps:
            paused_seconds = (pe - ps).total_seconds()

    net_seconds = max(0, overlap_seconds - paused_seconds)
    expected_seconds = max(0, (act_end - act_start).total_seconds())

    if expected_seconds <= 0:
        return (100.0, "Asistió")

    # Pausa igual o más larga que la actividad -> Ausente, aunque quede un
    # resto de presencia sin pausar dentro de la ventana.
    try:
        if attendance.pause_time and attendance.resume_time:
            raw_pause = (attendance.resume_time - attendance.pause_time).total_seconds()
            if raw_pause >= expected_seconds:
                return (0.0, "Ausente")
    except Exception:
        # Si algo falla al comparar la pausa, seguimos con el cálculo usual.
        pass

    # Crédito = presencia + retraso perdonado (tolerancia de llegada),
    # recortado a la duración programada:
    #   * el retraso dentro de la tolerancia no se cobra (llegada "a tiempo"),
    #   * una pausa NUNCA se rescata con el desborde del evento (el tope en el
    #     fin programado lo impide: sólo se acredita hasta 100%),
    #   * llegar tarde y pausar sólo perdona el retraso, no la pausa.
    credit_seconds = min(
        expected_seconds,
        net_seconds + _forgiven_late_seconds(attendance, activity, act_start),
    )

    percentage = round(max(0, (credit_seconds / expected_seconds) * 100), 2)
    return (percentage, _status_for_percentage(percentage))


def calculate_attendance_percentage(attendance_id):
    """Calcula, persiste y devuelve el porcentaje de asistencia de una fila.

    Devuelve ``None`` (sin modificar nada) si la asistencia no tiene
    check-in/check-out o si la actividad no está disponible.
    """
    from app import db

    attendance = db.session.get(Attendance, attendance_id)
    if not attendance:
        return None

    metrics = compute_attendance_metrics(attendance)
    if metrics is None:
        return None

    percentage, status = metrics
    attendance.attendance_percentage = percentage
    attendance.status = status
    return percentage


def sync_registration_status(attendance):
    """Refleja el resultado final del checkout en la preregistración.

    Política de cierre (self check-in / conferencias):

    - Sesión cerrada con ``attendance_percentage >= 80`` -> Registration
      ``Asistió`` (acredita horas) y ``attended = True``.
    - Sesión cerrada con ``< 80`` -> Registration ``Ausente``: el alumno
      llegó, pero no completó la actividad, por lo que **no** acredita.
    - Sesión abierta (sin check-out) -> no se toca: el resultado aún no está
      definido.

    Nota: ``hours_service`` también acredita las Registration en estado
    ``Confirmado``, así que marcar ``Ausente`` es lo único que quita las
    horas de un preregistrado que se retiró a media actividad.

    Returns:
        La ``Registration`` modificada o ``None`` (sin preregistro, sesión
        abierta o registro cancelado).
    """
    from app import db
    from app.models.registration import Registration

    if attendance is None or attendance.check_out_time is None:
        return None
    if attendance.student_id is None or attendance.activity_id is None:
        return None

    registration = Registration.query.filter_by(
        student_id=attendance.student_id, activity_id=attendance.activity_id
    ).first()
    if registration is None or registration.status == "Cancelado":
        return None

    percentage = attendance.attendance_percentage or 0
    if percentage >= 80:
        registration.status = "Asistió"
        registration.attended = True
        if registration.confirmation_date is None:
            registration.confirmation_date = db_now_local()
    else:
        registration.status = "Ausente"
        registration.attended = False

    db.session.add(registration)
    return registration


def create_related_attendances(student_id, activity_id):
    """
    Crea registros de asistencia para actividades relacionadas automáticamente.
    """
    from app import db
    from app.models.attendance import Attendance
    from app.models.activity import Activity

    # Obtener la actividad principal
    main_activity = db.session.get(Activity, activity_id)
    if not main_activity:
        # Si no se encuentra la actividad principal, lanzar excepción
        raise ValueError("Actividad principal no encontrada")

    # Iterar por actividades relacionadas
    # main_activity.related_activities es una RelationshipProperty; convertir a
    # lista y castear para que Pylance entienda que es iterable.
    related_iterable = list(
        cast(Iterable, getattr(main_activity, "related_activities", []))
    )
    for related_activity in related_iterable:
        # Verificar si ya existe un registro de asistencia para esta relación
        # para este estudiante específico.
        existing_attendance = Attendance.query.filter_by(
            student_id=student_id, activity_id=related_activity.id
        ).first()

        if not existing_attendance:
            # Crear asistencia automática.
            # La asistencia automática no copia tiempos de otra asistencia.
            # Se marca como asistida por la relación.
            auto_attendance = Attendance()
            auto_attendance.student_id = student_id
            auto_attendance.activity_id = related_activity.id
            # Crear marcada como 'Asistió' y asumir 100% porque se deriva de
            # una asistencia confirmada en la actividad principal.
            auto_attendance.attendance_percentage = 100.0
            auto_attendance.status = "Asistió"
            db.session.add(auto_attendance)
            # Sincronizar con preregistro si existe
            from app.models.registration import Registration

            registration = Registration.query.filter_by(
                student_id=student_id, activity_id=related_activity.id
            ).first()

            if registration:
                registration.attended = True
                registration.status = "Asistió"
                registration.confirmation_date = db_now_local()
                db.session.add(registration)


def sync_related_attendances_from_source(
    source_activity_id, student_ids=None, dry_run=False, target_activity_ids=None
):
    """
    Sincroniza (on-demand) asistencias desde una actividad fuente hacia sus
    actividades relacionadas.

    - source_activity_id: id de la actividad fuente (A)
    - student_ids: lista opcional de student ids a sincronizar (si None, sincroniza todos los presentes en la fuente)
    - dry_run: si True, no persiste cambios en la base de datos, solo retorna un resumen

    Retorna un dict con resumen: { created: int, skipped: int, details: [ ... ] }
    Cada detail contiene: student_id, target_activity_id, action ('created'|'skipped'), reason
    """
    from app import db
    from app.models.attendance import Attendance
    from app.models.activity import Activity
    from app.models.registration import Registration

    summary = {"created": 0, "skipped": 0, "details": []}

    source_activity = db.session.get(Activity, source_activity_id)
    if not source_activity:
        raise ValueError("Actividad fuente no encontrada")

    # Obtener solo las actividades que apuntan a la fuente (entrantes).
    # Semántica: B -> A significa que B es receptora y A es fuente; al invocar
    # sincronización sobre A se crearán asistencias en las actividades que
    # apuntan a A (p. ej. B). Esto evita sincronizaciones inesperadas en la
    # dirección opuesta.
    related = list(getattr(source_activity, "related_to_activities", []) or [])
    if not related:
        return summary

    # Si se pasó un filtro de targets, limitar la lista a esos ids
    if target_activity_ids:
        try:
            target_set = set(int(x) for x in target_activity_ids)
            related = [r for r in related if getattr(r, "id", None) in target_set]
        except Exception:
            # Si la conversión falla, ignorar el filtro y continuar con todos
            pass

    # Construir query de asistencias en la actividad fuente
    query = Attendance.query.filter_by(activity_id=source_activity_id)
    if student_ids:
        query = query.filter(Attendance.student_id.in_(student_ids))

    source_attendances = query.all()

    # Pre-cache student names and control numbers for efficiency (best-effort)
    try:
        student_ids_in_source = {s.student_id for s in source_attendances}
        students_map = {}
        if student_ids_in_source:
            from app.models.student import Student

            students = (
                db.session.query(Student.id, Student.full_name, Student.control_number)
                .filter(Student.id.in_(list(student_ids_in_source)))
                .all()
            )
            for sid, full_name, control in students:
                students_map[int(sid)] = {
                    "full_name": full_name or "",
                    "control_number": control or "",
                }
    except Exception:
        students_map = {}

    for src in source_attendances:
        for target in related:
            # Verificar si ya existe asistencia para el student/target
            exists = Attendance.query.filter_by(
                student_id=src.student_id, activity_id=target.id
            ).first()
            if exists:
                summary["skipped"] += 1
                # Build detail with explicit name and control (if available)
                student_info = students_map.get(int(src.student_id), {}) or {}
                summary["details"].append(
                    {
                        "student_id": src.student_id,
                        "student_name": student_info.get("full_name", ""),
                        "student_identifier": student_info.get("control_number", ""),
                        "target_activity_id": target.id,
                        "target_activity_name": getattr(target, "name", ""),
                        "action": "skipped",
                        "reason": "already_exists",
                    }
                )
                continue

            # Construir nueva asistencia copiando tiempos fuente.
            # Requerimiento: las asistencias sincronizadas deben representar 100%.
            new_att = Attendance()
            new_att.student_id = src.student_id
            new_att.activity_id = target.id
            # Copiar tiempos si existen para referencia, pero marcar 100% explícitamente
            new_att.check_in_time = src.check_in_time
            new_att.check_out_time = src.check_out_time
            new_att.attendance_percentage = 100.0
            new_att.status = "Asistió"

            if not dry_run:
                db.session.add(new_att)
                # Sincronizar preregistro si existe: marcar como asistido al 100%
                reg = Registration.query.filter_by(
                    student_id=src.student_id, activity_id=target.id
                ).first()
                if reg:
                    reg.attended = True
                    reg.status = "Asistió"
                    reg.confirmation_date = db_now_local()
                    db.session.add(reg)

            summary["created"] += 1
            student_info = students_map.get(int(src.student_id), {}) or {}
            summary["details"].append(
                {
                    "student_id": src.student_id,
                    "student_name": student_info.get("full_name", ""),
                    "student_identifier": student_info.get("control_number", ""),
                    "target_activity_id": target.id,
                    "target_activity_name": getattr(target, "name", ""),
                    "action": "created",
                    "reason": "synced_from_source",
                }
            )

    # Commit cuando no es dry_run
    if not dry_run:
        db.session.commit()

    return summary


def create_attendances_from_file(file_stream, activity_id, dry_run=True):
    """
    Crea asistencias en batch desde un archivo TXT o XLSX.

    Archivo TXT: un número de control por línea
    Archivo XLSX: números de control en la primera columna

    Retorna un dict: {
        'created': int,
        'skipped': int,
        'not_found': int,
        'errors': [{'control_number': str, 'message': str}],
        'details': [{'control_number': str, 'action': str, 'student_name': str}]
    }
    """
    from app import db
    from app.models.student import Student
    from app.models.attendance import Attendance
    from app.models.registration import Registration
    import requests
    import io

    summary = {
        "created": 0,
        "skipped": 0,
        "not_found": 0,
        "incomplete": 0,
        "invalid": 0,
        "errors": [],
        "details": [],
    }
    # Indicar si la ejecución es dry run para que los callers obtengan el flag
    summary["dry_run"] = bool(dry_run)

    # Verificar que la actividad existe
    activity = db.session.get(Activity, activity_id)
    if not activity:
        summary["errors"].append(
            {"control_number": "", "message": "Actividad no encontrada"}
        )
        return summary

    # Leer números de control del archivo
    control_numbers = []
    try:
        # Intentar leer como XLSX primero
        try:
            import pandas as pd

            file_stream.seek(0)
            # Read without treating first row as header
            df = pd.read_excel(
                io.BytesIO(file_stream.read()),
                sheet_name=0,
                engine="openpyxl",
                header=None,
            )
            # Tomar la primera columna
            if df.shape[0] > 0:
                control_numbers = [
                    str(val).strip() for val in df.iloc[:, 0] if str(val).strip()
                ]
        except Exception:
            # Si falla, intentar leer como TXT
            file_stream.seek(0)
            content = file_stream.read()
            if isinstance(content, bytes):
                content = content.decode("utf-8", errors="ignore")
            lines = content.strip().split("\n")
            control_numbers = [line.strip() for line in lines if line.strip()]
    except Exception as e:
        summary["errors"].append(
            {"control_number": "", "message": f"Error al leer archivo: {str(e)}"}
        )
        return summary

    if not control_numbers:
        summary["errors"].append(
            {
                "control_number": "",
                "message": "El archivo no contiene números de control",
            }
        )
        return summary

    # Procesar cada número de control
    # Filtrar líneas inválidas y normalizar la lista de controles a procesar.
    import re

    # Mantener índice de fila para trazabilidad en la UI
    valid_controls = []
    pattern = re.compile(r"^(?:\d+|[BCbc]\d+)$")
    for idx, raw in enumerate(control_numbers, start=1):
        val = str(raw).strip()
        if not val:
            continue
        if not pattern.match(val):
            # Línea no válida -> registrar como error y omitir
            summary["invalid"] += 1
            summary["errors"].append(
                {"control_number": val, "message": "Número de control inválido"}
            )
            # También incluir en details para visibilidad en UI, con row_index y fuente
            summary["details"].append(
                {
                    "control_number": val,
                    "action": "invalid",
                    "student_name": "-",
                    "row_index": idx,
                    "student_source": "invalid",
                }
            )
            continue
        # Guardar como objeto con índice de fila para mantener trazabilidad
        valid_controls.append({"value": val, "row_index": idx})

    for control in valid_controls:
        control_number = control.get("value")
        row_index = control.get("row_index")
        # Evitar valores inválidos
        if not control_number or control_number.lower() in ["nan", "none", ""]:
            continue

        # Normalize and prepare candidate variants
        raw_cn = str(control_number).strip()
        # digits-only variant (useful when TXT had prefixes like B123...)
        digits_only = "".join([c for c in raw_cn if c.isdigit()])
        candidates = [raw_cn]
        if digits_only and digits_only != raw_cn:
            candidates.append(digits_only)
        # keep unique while preserving order
        seen = set()
        candidates = [c for c in candidates if not (c in seen or seen.add(c))]

        student = None
        # fuente por defecto
        student_source = None
        # diagnostic placeholders - ensure variables exist for summary entries
        lookup_attempts = []
        external_name_used = None
        external_career_used = None
        # whether a Student was actually persisted in the DB for this row
        persisted = False

        # Try local DB for any candidate variant
        for cand in candidates:
            if not cand:
                continue
            student = Student.query.filter_by(control_number=cand).first()
            if student:
                student_source = "local"
                persisted = True
                break

        # If not found locally, try external APIs (multiple fallbacks)
        if not student:
            lookup_errors = []
            # collect what each external call returned (for diagnostics)
            lookup_attempts = []
            external_name_used = None
            external_career_used = None
            for cand in candidates:
                if not cand:
                    continue
                try:
                    # First, try the local proxy endpoint used by public UI (avoid duplicating normalization)
                    try:
                        from flask import request as _fl_req  # type: ignore

                        proxy_url = f"{_fl_req.url_root.rstrip('/')}/api/students/validate?control_number={cand}"
                        resp_proxy = requests.get(proxy_url, timeout=6)
                        if resp_proxy.status_code == 200:
                            try:
                                pdata_raw = resp_proxy.json() if resp_proxy.text else {}
                            except Exception:
                                pdata_raw = {}
                            # normalize shapes (dict with data/student, or list)
                            pdata = _normalize_external_json(pdata_raw)
                            # pdata may already be the inner student dict
                            p_student = pdata if isinstance(pdata, dict) else {}
                            external_name = (
                                p_student.get("full_name")
                                or p_student.get("name")
                                or p_student.get("nombre")
                            )
                            career_field = p_student.get("career") or p_student.get(
                                "carrera"
                            )
                            if isinstance(career_field, dict):
                                external_career = career_field.get(
                                    "name"
                                ) or career_field.get("nombre")
                            else:
                                external_career = career_field
                            lookup_attempts.append(
                                {
                                    "candidate": cand,
                                    "external_name": external_name,
                                    "external_career": external_career,
                                    "source": "local_proxy",
                                }
                            )
                            if external_name and external_career:
                                if dry_run:
                                    student_source = "external"
                                    persisted = False
                                else:
                                    student_source = "created"
                                    persisted = True
                                student = Student()
                                student.control_number = (
                                    p_student.get("control_number")
                                    or p_student.get("username")
                                    or cand
                                )
                                student.full_name = external_name
                                student.career = external_career
                                student.email = p_student.get("email") or ""
                                external_name_used = external_name
                                external_career_used = external_career
                                if not dry_run:
                                    db.session.add(student)
                                    db.session.flush()
                                break
                            else:
                                # record incomplete result from proxy and continue to other sources
                                lookup_errors.append(
                                    (
                                        cand,
                                        "API proxy devolvió datos incompletos (falta nombre o carrera)",
                                    )
                                )
                    except Exception:
                        # if proxy fails, continue to other external attempts
                        pass
                    # First, try the validate endpoint used elsewhere in the app
                    validate_url = f"http://apps.tecvalles.mx:8091/api/validate/student?username={cand}"
                    resp = requests.get(validate_url, timeout=8)
                    if resp.status_code == 200:
                        try:
                            external_raw = resp.json() if resp.text else {}
                        except Exception:
                            external_raw = {}
                        external_data = _normalize_external_json(external_raw)
                        # Ensure external_data is a dict before calling .get()
                        if not isinstance(external_data, dict):
                            external_data = {}
                        # Only create a Student if the external API returned
                        # at least a name and a career (policy requirement)
                        external_name = (
                            external_data.get("full_name")
                            or external_data.get("nombre")
                            or external_data.get("name")
                        )
                        external_career = external_data.get(
                            "career"
                        ) or external_data.get("carrera")
                        # record attempt for diagnostics
                        lookup_attempts.append(
                            {
                                "candidate": cand,
                                "external_name": external_name,
                                "external_career": external_career,
                                "source": "validate",
                            }
                        )
                        if external_name and external_career:
                            # Mark source differently for dry-run vs actual persistence
                            if dry_run:
                                student_source = "external"
                                persisted = False
                            else:
                                student_source = "created"
                                persisted = True
                            student = Student()
                            student.control_number = (
                                external_data.get("username")
                                or external_data.get("control_number")
                                or cand
                            )
                            student.full_name = external_name
                            student.career = external_career
                            student.email = external_data.get("email") or ""
                            external_name_used = external_name
                            external_career_used = external_career
                            if not dry_run:
                                db.session.add(student)
                                db.session.flush()
                            break
                        else:
                            # Record that API returned incomplete data and continue
                            lookup_errors.append(
                                (
                                    cand,
                                    "API devolvió datos incompletos (falta nombre o carrera)",
                                )
                            )
                    # NOTE: We intentionally DO NOT call the general search endpoint
                    # `/api/estudiantes?search=` as a validation fallback here because
                    # that endpoint returns a LIST of candidates (intended for free
                    # search / select UI) and can produce shapes that confuse the
                    # single-record validation flow. For validating a single
                    # control_number we prefer the dedicated single-result endpoint
                    # `/api/validate/student?username=` (handled above) or the local
                    # proxy. If additional heuristics are desired they should be
                    # implemented explicitly and carefully.
                    # If the external validate call returned 404, record it for diagnostics
                    if resp.status_code == 404:
                        lookup_errors.append((cand, "No encontrado (404)"))
                except Exception as e:
                    lookup_errors.append((cand, str(e)))
                    lookup_attempts.append({"candidate": cand, "error": str(e)})

            # If still not found, decide between 'not_found' (no external data)
            # and 'incomplete' (external returned something but incomplete)
            if not student:
                # analyze lookup results
                any_lookup_attempts = bool(lookup_attempts)
                any_lookup_errors = bool(lookup_errors)
                # consider partial if any lookup_attempts exist or any lookup_errors indicate incomplete data
                lookup_indicates_incomplete = False
                if any_lookup_attempts:
                    # if any attempt returned a name or career (even if incomplete), mark incomplete
                    for a in lookup_attempts:
                        if (
                            a.get("external_name")
                            or a.get("external_career")
                            or a.get("error")
                        ):
                            lookup_indicates_incomplete = True
                            break
                if not lookup_indicates_incomplete and any_lookup_errors:
                    for c, m in lookup_errors:
                        if "incomplet" in m.lower():
                            lookup_indicates_incomplete = True
                            break

                if lookup_indicates_incomplete:
                    summary["incomplete"] += 1
                    # Prefer the best available name/career from attempts
                    best_name = None
                    best_career = None
                    best_source = None
                    for a in lookup_attempts:
                        if not best_name and a.get("external_name"):
                            best_name = a.get("external_name")
                            best_source = a.get("source")
                        if not best_career and a.get("external_career"):
                            best_career = a.get("external_career")

                    # Build a concise reason: falta carrera/nombre o genérico
                    reasons = []
                    if best_name and not best_career:
                        reasons.append("falta carrera")
                    elif best_career and not best_name:
                        reasons.append("falta nombre")
                    else:
                        # fallback: use any unique error messages collected
                        seen = set()
                        for c, m in lookup_errors:
                            if m and m not in seen:
                                seen.add(m)
                                reasons.append(m)
                        if not reasons:
                            reasons.append("Datos incompletos en API externa")

                    msg = ", ".join(reasons)
                    if best_source and best_name:
                        msg = f"Encontrado en API ({best_source}) — {msg}"

                    # If we have a name from external, show it in student_name
                    summary["details"].append(
                        {
                            "control_number": raw_cn,
                            "action": "external_incomplete",
                            "student_name": best_name or "-",
                            "row_index": row_index,
                            "student_source": "external",
                            "lookup_message": msg,
                            "lookup_attempts": lookup_attempts or None,
                            "persisted": False,
                        }
                    )
                else:
                    # truly not found anywhere
                    summary["not_found"] += 1
                    msg_parts = []
                    seen = set()
                    if lookup_errors:
                        for c, m in lookup_errors:
                            part = f"{c}: {m}".strip()
                            if part and part not in seen:
                                seen.add(part)
                                msg_parts.append(part)
                        msg = "; ".join(msg_parts)
                    else:
                        msg = "No encontrado en BD ni API externa"
                    summary["errors"].append({"control_number": raw_cn, "message": msg})
                    summary["details"].append(
                        {
                            "control_number": raw_cn,
                            "action": "not_found",
                            "student_name": "-",
                            "row_index": row_index,
                            "student_source": "not_found",
                            "lookup_message": msg,
                            "lookup_attempts": lookup_attempts or None,
                            "persisted": False,
                        }
                    )
                continue

        # Verificar si ya existe asistencia
        existing = Attendance.query.filter_by(
            student_id=student.id, activity_id=activity_id
        ).first()
        if existing:
            summary["skipped"] += 1
            # determinar fuente: si student tiene id y fue encontrado localmente
            det_source = student_source or (
                "local"
                if persisted
                else ("external" if external_name_used else "unknown")
            )
            summary["details"].append(
                {
                    "control_number": control_number,
                    "action": "skipped",
                    "student_name": student.full_name,
                    "reason": "Ya existe asistencia",
                    "row_index": row_index,
                    "student_source": det_source,
                }
            )
            continue

        # Crear asistencia
        if not dry_run:
            attendance = Attendance()
            attendance.student_id = student.id
            attendance.activity_id = activity_id
            attendance.attendance_percentage = 100.0
            attendance.status = "Asistió"
            db.session.add(attendance)

            # Actualizar registro si existe
            registration = Registration.query.filter_by(
                student_id=student.id, activity_id=activity_id
            ).first()
            if registration:
                registration.attended = True
                registration.status = "Asistió"
                registration.confirmation_date = db_now_local()
                db.session.add(registration)

        summary["created"] += 1
        det_source = student_source or (
            "local" if persisted else ("external" if external_name_used else "created")
        )
        # attach any external values we received (useful in dry-run for preview)
        summary["details"].append(
            {
                "control_number": control_number,
                "action": "created",
                "student_name": student.full_name,
                "row_index": row_index,
                "student_source": det_source,
                "external_name": external_name_used,
                "external_career": external_career_used,
                "lookup_attempts": lookup_attempts or None,
                "persisted": bool(persisted),
            }
        )

    # Commit si no es dry_run
    if not dry_run:
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            summary["errors"].append(
                {"control_number": "", "message": f"Error al guardar cambios: {str(e)}"}
            )
            summary["created"] = 0

    return summary


def process_exit_from_file(
    file_stream, activity_id, dry_run=True, action="mark_absent"
):
    """
    Procesa un archivo TXT o XLSX con números de control para marcar salidas.

    - action: 'mark_absent' (recommended, non-destructive) or 'delete'
    - dry_run: if True, only validate and return report

    Returns dict similar to create_attendances_from_file with keys:
      created -> number of rows updated/deleted
      not_found -> attendances not found for the provided controls
      unmatched -> controls with no student
      errors, details
    """
    from app import db
    from app.models.student import Student
    from app.models.attendance import Attendance

    summary = {
        "applied": 0,
        "skipped": 0,
        "not_found": 0,
        "unmatched": 0,
        "errors": [],
        "details": [],
    }
    summary["dry_run"] = bool(dry_run)

    # Verify activity exists
    activity = db.session.get(Activity, activity_id)
    if not activity:
        summary["errors"].append(
            {"control_number": "", "message": "Actividad no encontrada"}
        )
        return summary

    # Read control numbers (reuse same strategy: try XLSX then TXT)
    control_numbers = []
    try:
        try:
            import pandas as pd
            import io

            file_stream.seek(0)
            df = pd.read_excel(
                io.BytesIO(file_stream.read()),
                sheet_name=0,
                engine="openpyxl",
                header=None,
            )
            if df.shape[0] > 0:
                control_numbers = [
                    str(val).strip() for val in df.iloc[:, 0] if str(val).strip()
                ]
        except Exception:
            file_stream.seek(0)
            content = file_stream.read()
            if isinstance(content, bytes):
                content = content.decode("utf-8", errors="ignore")
            lines = content.strip().split("\n")
            control_numbers = [line.strip() for line in lines if line.strip()]
    except Exception as e:
        summary["errors"].append(
            {"control_number": "", "message": f"Error al leer archivo: {str(e)}"}
        )
        return summary

    if not control_numbers:
        summary["errors"].append(
            {
                "control_number": "",
                "message": "El archivo no contiene números de control",
            }
        )
        return summary

    import re

    pattern = re.compile(r"^(?:\d+|[BCbc]\d+)$")

    # process
    seen = set()
    valid_controls = []
    for idx, raw in enumerate(control_numbers, start=1):
        val = str(raw).strip()
        if not val:
            continue
        if not pattern.match(val):
            summary["errors"].append(
                {"control_number": val, "message": "Número de control inválido"}
            )
            summary["details"].append(
                {"control_number": val, "action": "invalid", "row_index": idx}
            )
            continue
        if val in seen:
            continue
        seen.add(val)
        valid_controls.append({"value": val, "row_index": idx})

    # For exit processing we only consider local DB students; do not create new students from external APIs
    for control in valid_controls:
        cn = control.get("value")
        row_index = control.get("row_index")
        student = Student.query.filter_by(control_number=cn).first()
        if not student:
            summary["unmatched"] += 1
            summary["details"].append(
                {
                    "control_number": cn,
                    "action": "unmatched",
                    "action_display": "Estudiante no encontrado",
                    "student_name": "-",
                    "row_index": row_index,
                    "reason": "No student found in DB",
                }
            )
            continue

        attendance = Attendance.query.filter_by(
            student_id=student.id, activity_id=activity_id
        ).first()
        if not attendance:
            summary["not_found"] += 1
            summary["details"].append(
                {
                    "control_number": cn,
                    "student_id": student.id,
                    "student_name": (
                        getattr(student, "full_name", "-") if student else "-"
                    ),
                    "action": "not_found",
                    "action_display": "No encontrado",
                    "row_index": row_index,
                    "reason": "No attendance for activity",
                }
            )
            continue

        # matched attendance
        # determine human-friendly action display
        if action == "mark_absent":
            action_display = (
                "Se marcará como Ausente" if dry_run else "Marcado como Ausente"
            )
            action_token = "mark_absent"
        elif action == "delete":
            action_display = "Se eliminará" if dry_run else "Eliminado"
            action_token = "delete"
        else:
            action_display = "Acción" if dry_run else "Aplicado"
            action_token = action

        summary["details"].append(
            {
                "control_number": cn,
                "student_id": student.id,
                "student_name": getattr(student, "full_name", "-") if student else "-",
                "attendance_id": attendance.id,
                "current_status": attendance.status,
                "row_index": row_index,
                "action": action_token,
                "action_display": action_display,
            }
        )

        if not dry_run:
            try:
                if action == "mark_absent":
                    attendance.status = "Ausente"
                    attendance.attendance_percentage = 0.0
                    attendance.check_in_time = None
                    attendance.check_out_time = None
                    attendance.is_paused = False
                    attendance.pause_time = None
                    attendance.resume_time = None
                    db.session.add(attendance)
                elif action == "delete":
                    db.session.delete(attendance)
                else:
                    # unknown action -> skip
                    summary["skipped"] += 1
                    continue
                summary["applied"] += 1
            except Exception as e:
                db.session.rollback()
                summary["errors"].append({"control_number": cn, "message": str(e)})

    if not dry_run:
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            summary["errors"].append(
                {"control_number": "", "message": f"Error al guardar cambios: {str(e)}"}
            )

    return summary
