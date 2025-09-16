from app.models.registration import Registration
from app.models.activity import Activity
from datetime import datetime, time, timedelta
from sqlalchemy import and_
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
        registered_activities = Activity.query.join(
            Registration
        ).filter(
            Registration.student_id == student_id,
            Registration.status.in_(['Registrado', 'Confirmado'])
        ).all()

        new_start = new_activity.start_datetime
        new_end = new_activity.end_datetime

        for existing_activity in registered_activities:
            existing_start = existing_activity.start_datetime
            existing_end = existing_activity.end_datetime

            # ✨ Manejar actividades multídias
            if is_multi_day_activity(new_start, new_end) or is_multi_day_activity(existing_start, existing_end):
                # Verificar solapamiento día por día
                if check_multiday_overlap(new_start, new_end, existing_start, existing_end):
                    return True, f"Conflicto de horario con '{existing_activity.name}'"
            else:
                # Verificación de solapamiento normal
                if check_normal_overlap(new_start, new_end, existing_start, existing_end):
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
        days.append(current_date.strftime('%Y-%m-%d'))
        current_date += timedelta(days=1)

    return days


def get_daily_range(target_date_str, activity_start, activity_end):
    """
    Obtiene el rango de horas para una actividad en un día específico.
    target_date_str: 'YYYY-MM-DD'
    """
    from datetime import datetime, time

    target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
    activity_start_date = activity_start.date()
    activity_end_date = activity_end.date()

    if target_date == activity_start_date:
        # Primer día: usar hora de inicio de la actividad
        range_start = activity_start
    else:
        # Días intermedios: usar inicio del día (00:00)
        range_start = datetime.combine(target_date, time(0, 0))

    if target_date == activity_end_date:
        # Último día: usar hora de fin de la actividad
        range_end = activity_end
    else:
        # Días intermedios: usar fin del día (23:59)
        range_end = datetime.combine(target_date, time(23, 59))

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
    if activity.activity_type not in ['Conferencia', 'Taller', 'Curso']:
        return True  # Magistrales no requieren cupo

    if activity.max_capacity is None:
        return True  # Sin cupo definido, permitir

    # Contar preregistros confirmados
    current_registrations = Registration.query.filter_by(
        activity_id=activity_id, status='Registrado'
    ).count()

    return current_registrations < activity.max_capacity
