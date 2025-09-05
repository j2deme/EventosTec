from app.models.registration import Registration
from app.models.activity import Activity


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
