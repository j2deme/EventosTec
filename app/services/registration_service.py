from app.models.registration import Registration
from app.models.activity import Activity
from datetime import datetime, timedelta
from app import db


def _get_daily_sessions(activity):
    """
    Genera una lista de tuplas (inicio, fin) para cada dia habil de una actividad.
    Asume que la actividad va de start_datetime a end_datetime,
    y se repite diariamente entre esas fechas con un horario fijo.
    """
    if not activity.start_datetime or not activity.end_datetime:
        return []  # O manejar error

    start_date = activity.start_datetime.date()
    end_date = activity.end_datetime.date()

    # Asumimos que la hora de inicio y fin diaria es la de start_datetime y end_datetime
    daily_start_time = activity.start_datetime.time()
    daily_end_time = activity.end_datetime.time()

    sessions = []
    current_date = start_date
    while current_date <= end_date:
        session_start = datetime.combine(current_date, daily_start_time)
        session_end = datetime.combine(current_date, daily_end_time)
        sessions.append((session_start, session_end))
        current_date += timedelta(days=1)

    return sessions


def has_schedule_conflict(student_id, new_activity_id):
    """
    Verifica si hay conflicto de horario para una nueva actividad.
    Maneja correctamente actividades multídias.
    """
    try:
        new_activity = db.session.get(Activity, new_activity_id)
        if not new_activity:
            return False, "Actividad no encontrada"

        # Obtener todas las actividades registradas del estudiante
        # Usar el query del modelo (Flask-SQLAlchemy) en lugar de db.session.query
        registered_activities = (
            Activity.query.join(Registration)
            .filter(
                Registration.student_id == student_id,
                Registration.status.in_(["Registrado", "Confirmado"]),
            )
            .all()
        )

        new_start = new_activity.start_datetime
        new_end = new_activity.end_datetime

        for existing_activity in registered_activities:
            existing_start = existing_activity.start_datetime
            existing_end = existing_activity.end_datetime

            # ✨ Manejar actividades multídias
            if is_multi_day_activity(new_start, new_end) or is_multi_day_activity(
                existing_start, existing_end
            ):
                # Verificar solapamiento día por día
                if check_multiday_overlap(
                    new_start, new_end, existing_start, existing_end
                ):
                    return True, f"Conflicto de horario con '{existing_activity.name}'"
            else:
                # Verificación de solapamiento normal
                if check_normal_overlap(
                    new_start, new_end, existing_start, existing_end
                ):
                    return True, f"Conflicto de horario con '{existing_activity.name}'"

        return False, ""
    except Exception as e:
        return False, f"Error al verificar conflictos: {str(e)}"


def is_multi_day_activity(start_datetime, end_datetime):
    """Verifica si una actividad abarca múltiples días."""
    start_date = start_datetime.date()
    end_date = end_datetime.date()
    return start_date != end_date


def check_multiday_overlap(start1, end1, start2, end2):
    """
    Verifica solapamiento entre actividades multídias.
    Divide cada actividad en días y verifica solapamiento día por día.
    """
    # Obtener días de cada actividad
    days1 = get_days_between(start1, end1)
    days2 = get_days_between(start2, end2)

    # Verificar si hay días en común
    common_days = set(days1) & set(days2)

    if not common_days:
        return False

    # Para cada día común, verificar solapamiento de horarios
    for common_day in common_days:
        # Obtener horario de cada actividad para ese día
        range1_start, range1_end = get_daily_range(common_day, start1, end1)
        range2_start, range2_end = get_daily_range(common_day, start2, end2)

        # Verificar solapamiento en ese día
        if check_normal_overlap(range1_start, range1_end, range2_start, range2_end):
            return True

    return False


def get_days_between(start_datetime, end_datetime):
    """Obtiene lista de fechas (YYYY-MM-DD) entre dos fechas."""
    from datetime import timedelta

    days = []
    current_date = start_datetime.date()
    end_date = end_datetime.date()

    while current_date <= end_date:
        days.append(current_date.strftime("%Y-%m-%d"))
        current_date += timedelta(days=1)

    return days


def get_daily_range(target_date_str, activity_start, activity_end):
    """
    Obtiene el rango de horas para una actividad en un día específico.
    target_date_str: 'YYYY-MM-DD'
    """
    from datetime import datetime, timedelta

    target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()

    # Use the activity's time-of-day for the given target date.
    start_time = activity_start.time()
    end_time = activity_end.time()

    # Base daily range: combine target date with activity times
    range_start = datetime.combine(target_date, start_time)
    range_end = datetime.combine(target_date, end_time)

    # Handle activities that cross midnight within the same daily slot
    if range_end <= range_start:
        # If end time is earlier or equal to start time, assume it continues to next day
        range_end = range_end + timedelta(days=1)

    # Respect exact datetimes on first/last day to preserve potential partial-day edges
    if target_date == activity_start.date():
        range_start = activity_start
    if target_date == activity_end.date():
        range_end = activity_end

    return range_start, range_end


def check_normal_overlap(start1, end1, start2, end2):
    """Verificación de solapamiento normal."""
    return max(start1, start2) < min(end1, end2)


def is_registration_allowed(activity_id):
    """
    Verifica si se permite un nuevo preregistro para una actividad.
    Retorna True si hay cupo, False si está lleno.
    """
    from app import db

    activity = db.session.get(Activity, activity_id)
    if not activity:
        raise ValueError("Actividad no encontrada")

    # Solo validar cupo para actividades que lo requieran (Conferencias, Talleres, Cursos)
    if activity.activity_type not in ["Conferencia", "Taller", "Curso"]:
        return True  # Magistrales no requieren cupo

    if activity.max_capacity is None:
        return True  # Sin cupo definido, permitir

    # Contar preregistros confirmados
    current_registrations = Registration.query.filter_by(
        activity_id=activity_id, status="Registrado"
    ).count()

    return current_registrations < activity.max_capacity


def create_registration_simple(student_id, activity_id):
    """
    Versión no-atalica y simple de creación de preregistro.
    Realiza comprobaciones básicas y hace commit inmediatamente sin
    usar bloqueos FOR UPDATE ni transacciones anidadas.
    Útil para pruebas o entornos sin concurrencia alta.
    """
    from app import db

    try:
        # Validaciones básicas
        activity = db.session.get(Activity, activity_id)
        if not activity:
            return False, "Actividad no encontrada"

        # Validar cupo si aplica
        if (
            activity.activity_type in ["Conferencia", "Taller", "Curso"]
            and activity.max_capacity is not None
        ):
            current_registrations = Registration.query.filter_by(
                activity_id=activity_id, status="Registrado"
            ).count()
            if current_registrations >= activity.max_capacity:
                return False, "Cupo lleno para esta actividad."

        # Verificar registro existente
        existing = Registration.query.filter_by(
            student_id=student_id, activity_id=activity_id
        ).first()
        if existing:
            if existing.status == "Cancelado":
                existing.status = "Registrado"
                existing.registration_date = db.func.now()
                existing.confirmation_date = None
                existing.attended = False
                db.session.add(existing)
                db.session.commit()
                return True, existing
            else:
                return False, "Ya existe un preregistro para esta actividad"

        # Crear nuevo preregistro y commitear inmediatamente
        reg = Registration()
        reg.student_id = student_id
        reg.activity_id = activity_id
        reg.status = "Registrado"
        db.session.add(reg)
        db.session.commit()
        return True, reg
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return False, str(e)


def create_registration_atomic(student_id, activity_id):
    """
    Intenta crear un preregistro de forma atómica respetando el cupo.
    Retorna (True, registration) si se creó, (False, message) si no es posible.

    Implementación:
    - Inicia una transacción.
    - Bloquea la fila de Activity (SELECT FOR UPDATE) cuando el dialecto lo soporte.
    - Recalcula la cantidad de registros y compara con max_capacity.
    - Crea el Registration y hace commit.

    Nota: en SQLite el FOR UPDATE no tiene efecto; aun así, la UniqueConstraint en
    `registrations` evita duplicados del mismo estudiante, pero para evitar
    sobrepasar el cupo en entornos concurrentes se recomienda usar una DB con
    soporte de row-level locking (Postgres). Aquí se hace lo mejor posible con
    SQLAlchemy y transacciones.
    """
    from app import db

    try:
        # Abrir transacción
        with db.session.begin_nested():
            # Intentar obtener la actividad con bloqueo de fila si está soportado
            session = db.session
            # Obtener el 'bind' de forma robusta: preferir session.get_bind()
            # y caer a session.bind o al engine global si es necesario.
            try:
                bind = session.get_bind()
            except Exception:
                bind = getattr(session, "bind", None)

            if bind is None:
                # Fallback al engine global (por ejemplo en tests o contextos especiales)
                from app import db as _db

                bind = getattr(_db, "engine", None)

            dialect_name = None
            try:
                dialect_name = bind.dialect.name if bind is not None else None
            except Exception:
                dialect_name = None

            if dialect_name in ("postgresql", "mysql"):
                # Usar FOR UPDATE para evitar race conditions
                activity = session.execute(
                    db.select(Activity)
                    .where(Activity.id == activity_id)
                    .with_for_update()
                ).scalar_one_or_none()
            else:
                # Para SQLite y otros, caer al get normal
                activity = session.get(Activity, activity_id)

            if not activity:
                return False, "Actividad no encontrada"

            if activity.activity_type not in ["Conferencia", "Taller", "Curso"]:
                # No aplica cupo
                pass

            if activity.max_capacity is None:
                # No hay límite
                pass
            else:
                # Recalcular cantidad de preregistros actuales dentro de la transacción
                current_registrations = (
                    session.query(Registration)
                    .filter_by(activity_id=activity_id, status="Registrado")
                    .count()
                )

                if current_registrations >= activity.max_capacity:
                    return False, "Cupo lleno para esta actividad."

            # Verificar si el estudiante ya tiene un registro (UniqueConstraint protege, pero mejor chequear)
            existing = (
                session.query(Registration)
                .filter_by(student_id=student_id, activity_id=activity_id)
                .first()
            )
            if existing:
                # Si existe y está cancelado, reactivar
                if existing.status == "Cancelado":
                    existing.status = "Registrado"
                    existing.registration_date = db.func.now()
                    existing.confirmation_date = None
                    existing.attended = False
                    session.add(existing)
                    session.commit()
                    return True, existing
                else:
                    return False, "Ya existe un preregistro para esta actividad"

            # Crear nuevo preregistro
            reg = Registration()
            reg.student_id = student_id
            reg.activity_id = activity_id
            reg.status = "Registrado"
            session.add(reg)
            # Commit de la transacción
        # Si llegamos aquí, commit automático del context manager
        return True, reg
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        return False, str(e)
