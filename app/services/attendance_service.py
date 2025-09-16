from datetime import datetime, timezone
from typing import Iterable, cast

from app.models.attendance import Attendance
from app.models.activity import Activity


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
    attendance.pause_time = datetime.now(timezone.utc)
    return attendance


def resume_attendance(attendance_id):
    """Reanuda la asistencia y ajusta tiempos para el cálculo."""
    from app import db
    attendance = db.session.get(Attendance, attendance_id)
    if not attendance:
        raise ValueError("Asistencia no encontrada")
    if not attendance.is_paused:
        raise ValueError("La asistencia no está pausada")

    attendance.is_paused = False
    attendance.resume_time = datetime.now(timezone.utc)
    return attendance

# Función auxiliar para calcular duración neta (considerando pausas)


def calculate_net_duration_seconds(attendance):
    """Calcula la duración real en segundos, restando las pausas."""
    if not attendance.check_in_time:
        return 0

    # Si no hay check-out, usar ahora
    end_time = attendance.check_out_time or datetime.now(timezone.utc)

    # Helper: ensure datetime is timezone-aware (assume UTC if naive)
    def _ensure_tz(dt):
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    start = _ensure_tz(attendance.check_in_time)
    end = _ensure_tz(end_time)

    total_paused_seconds = 0
    if attendance.pause_time:
        # Sumar todas las pausas. Asumimos una sola pausa por ahora.
        # Para múltiples pausas, se necesitaría una estructura diferente (ej: lista de pausas)
        resume_or_now = attendance.resume_time or datetime.now(timezone.utc)
        resume_or_now = _ensure_tz(resume_or_now)
        pause_time = _ensure_tz(attendance.pause_time)
        if resume_or_now and pause_time:
            total_paused_seconds = (resume_or_now - pause_time).total_seconds()

    if not start or not end:
        return 0

    net_duration = (end - start).total_seconds() - total_paused_seconds
    return max(0, net_duration)  # No permitir duraciones negativas


def calculate_attendance_percentage(attendance_id):
    """
    Calcula y actualiza el porcentaje de asistencia y el estado para una asistencia.
    """
    from app import db

    attendance = db.session.get(Attendance, attendance_id)
    if not attendance or not attendance.check_in_time or not attendance.check_out_time:
        return None

    activity = getattr(attendance, 'activity', None)
    if not activity:
        return None

    # Usar la duración neta (considerando pausas)
    net_duration_seconds = calculate_net_duration_seconds(attendance)
    expected_duration_seconds = activity.duration_hours * 3600

    if expected_duration_seconds > 0:
        percentage = (net_duration_seconds / expected_duration_seconds) * 100
        attendance.attendance_percentage = round(
            max(0, percentage), 2)  # Asegurar porcentaje no negativo

        if attendance.attendance_percentage >= 80:
            attendance.status = 'Asistió'
        elif attendance.attendance_percentage > 0:
            attendance.status = 'Parcial'
        else:
            attendance.status = 'Ausente'
        # No hacer commit aquí; el endpoint debe encargarse de commit/rollback
        return attendance.attendance_percentage
    else:
        # Si la duración es 0 o inválida, asumir 100% si hubo check-in/out
        attendance.attendance_percentage = 100.0
        attendance.status = 'Asistió'
        # No hacer commit aquí; el endpoint debe encargarse de commit/rollback
        return 100.0


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
    related_iterable = list(cast(Iterable, getattr(
        main_activity, 'related_activities', [])))
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
            auto_attendance.attendance_percentage = 100.0
            auto_attendance.status = 'Asistió'
            db.session.add(auto_attendance)
            # Sincronizar con preregistro si existe
            from app.models.registration import Registration

            registration = Registration.query.filter_by(
                student_id=student_id,
                activity_id=related_activity.id
            ).first()

            if registration:
                registration.attended = True
                registration.status = 'Asistió'
                registration.confirmation_date = db.func.now()
                db.session.add(registration)
    # Si esta función se llama desde un endpoint, el commit del endpoint debe ser suficiente.
    # No hacer commit aquí; el endpoint será responsable de la transacción.
