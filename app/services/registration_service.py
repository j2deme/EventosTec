from app.models.registration import Registration
from app.models.activity import Activity
from datetime import datetime, time, timedelta
from sqlalchemy import and_


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
    Verifica si una nueva actividad tiene un horario que se solapa 
    con otras actividades en las que el estudiante ya está preregistrado.

    Args:
        student_id (int): ID del estudiante.
        new_activity_id (int): ID de la nueva actividad a verificar.

    Returns:
        tuple: (bool, str) - (True/False si hay conflicto, mensaje descriptivo del conflicto o "").
    """
    from app import db
    from app.models.activity import Activity
    from app.models.registration import Registration

    new_activity = db.session.get(Activity, new_activity_id)
    if not new_activity:
        return False, "Actividad nueva no encontrada."

    # Obtener sesiones diarias de la nueva actividad
    new_sessions = _get_daily_sessions(new_activity)
    if not new_sessions:
        # Si no se pueden calcular sesiones, asumimos que no hay conflicto o se maneja como error.
        return False, ""

    # Buscar actividades ya registradas (no canceladas)
    existing_registrations = db.session.query(Registration).filter(
        and_(
            Registration.student_id == student_id,
            Registration.status != 'Cancelado'  # Ajustar según tu enum
        )
    ).all()

    for reg in existing_registrations:
        existing_activity = reg.activity
        if not existing_activity or existing_activity.id == new_activity_id:
            continue  # Saltar si no existe o es la misma actividad

        existing_sessions = _get_daily_sessions(existing_activity)
        if not existing_sessions:
            continue

        # Comparar cada sesion nueva contra cada sesion existente
        for new_start, new_end in new_sessions:
            for existing_start, existing_end in existing_sessions:
                # Formula estandar de solapamiento
                if new_start < existing_end and existing_start < new_end:
                    conflict_msg = (
                        f"Conflicto de horario: La actividad '{new_activity.name}' "
                        f"({new_start.strftime('%Y-%m-%d %H:%M')} - {new_end.strftime('%H:%M')}) "
                        f"se solapa con la actividad ya registrada '{existing_activity.name}' "
                        f"({existing_start.strftime('%Y-%m-%d %H:%M')} - {existing_end.strftime('%H:%M')})."
                    )
                    return True, conflict_msg

    return False, ""


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
    current_registrations = db.session.query(Registration).filter_by(
        activity_id=activity_id, status='Registrado'
    ).count()

    print(
        f"Activity ID: {activity_id}, Max Cap: {activity.max_capacity}, Current Regs: {current_registrations}")

    return current_registrations < activity.max_capacity
