from datetime import datetime
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
    attendance.pause_time = datetime.now()
    db.session.commit()
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
    attendance.resume_time = datetime.now()
    db.session.commit()
    return attendance

# Función auxiliar para calcular duración neta (considerando pausas)


def calculate_net_duration_seconds(attendance):
    """Calcula la duración real en segundos, restando las pausas."""
    if not attendance.check_in_time:
        return 0

    # Si no hay check-out, usar ahora
    end_time = attendance.check_out_time or datetime.now()

    total_paused_seconds = 0
    if attendance.pause_time:
        # Sumar todas las pausas. Asumimos una sola pausa por ahora.
        # Para múltiples pausas, se necesitaría una estructura diferente (ej: lista de pausas)
        resume_or_now = attendance.resume_time or datetime.now()
        total_paused_seconds = (
            resume_or_now - attendance.pause_time).total_seconds()

    net_duration = (
        end_time - attendance.check_in_time).total_seconds() - total_paused_seconds
    return max(0, net_duration)  # No permitir duraciones negativas


def calculate_attendance_percentage(attendance_id):
    """
    Calcula y actualiza el porcentaje de asistencia y el estado para una asistencia.
    """
    from app import db

    attendance = db.session.get(Attendance, attendance_id)
    if not attendance or not attendance.check_in_time or not attendance.check_out_time:
        return None

    activity = attendance.activity
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

        db.session.commit()
        return attendance.attendance_percentage
    else:
        # Si la duración es 0 o inválida, asumir 100% si hubo check-in/out
        attendance.attendance_percentage = 100.0
        attendance.status = 'Asistió'
        db.session.commit()
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
    for related_activity in main_activity.related_activities:
        # Verificar si ya existe un registro de asistencia para esta relación
        # para este estudiante específico.
        existing_attendance = db.session.query(Attendance).filter_by(
            student_id=student_id, activity_id=related_activity.id
        ).first()

        if not existing_attendance:
            # Crear asistencia automática.
            # La asistencia automática no copia tiempos de otra asistencia.
            # Se marca como asistida por la relación.
            auto_attendance = Attendance(
                student_id=student_id,
                activity_id=related_activity.id,
                attendance_percentage=100.0,  # Se asume completa por relación
                status='Asistió'  # O un estado especial como 'Relacionada' si lo prefieres
            )
            db.session.add(auto_attendance)
    # Si esta función se llama desde un endpoint, el commit del endpoint debe ser suficiente.
    db.session.commit()
