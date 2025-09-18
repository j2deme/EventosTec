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
            # Crear marcada como 'Asistió' pero dejar porcentaje 0.0 para
            # permitir recalcular según tiempos reales si es necesario.
            auto_attendance.attendance_percentage = 0.0
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


def sync_related_attendances_from_source(source_activity_id, student_ids=None, dry_run=False):
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

    summary = {
        'created': 0,
        'skipped': 0,
        'details': []
    }

    source_activity = db.session.get(Activity, source_activity_id)
    if not source_activity:
        raise ValueError('Actividad fuente no encontrada')

    related = list(getattr(source_activity, 'related_activities', []) or [])
    if not related:
        return summary

    # Construir query de asistencias en la actividad fuente
    query = Attendance.query.filter_by(activity_id=source_activity_id)
    if student_ids:
        query = query.filter(Attendance.student_id.in_(student_ids))

    source_attendances = query.all()

    for src in source_attendances:
        for target in related:
            # Verificar si ya existe asistencia para el student/target
            exists = Attendance.query.filter_by(
                student_id=src.student_id, activity_id=target.id).first()
            if exists:
                summary['skipped'] += 1
                summary['details'].append({
                    'student_id': src.student_id,
                    'target_activity_id': target.id,
                    'action': 'skipped',
                    'reason': 'already_exists'
                })
                continue

            # Construir nueva asistencia copiando tiempos fuente
            new_att = Attendance()
            new_att.student_id = src.student_id
            new_att.activity_id = target.id
            new_att.check_in_time = src.check_in_time
            new_att.check_out_time = src.check_out_time

            # Calcular porcentaje/estado si tenemos ambos tiempos
            if new_att.check_in_time and new_att.check_out_time:
                try:
                    # Utiliza la función local para calcular porcentaje
                    # safe: will return None if not persisted
                    calculate_attendance_percentage(new_att.id)
                except Exception:
                    # ignore calculation failures here; endpoint llamador puede recalcular
                    pass

            if not dry_run:
                db.session.add(new_att)
                # sync registration if exists
                reg = Registration.query.filter_by(
                    student_id=src.student_id, activity_id=target.id).first()
                if reg:
                    reg.attended = bool(
                        new_att.check_in_time and new_att.check_out_time)
                    if reg.attended:
                        reg.status = 'Asistió'
                        reg.confirmation_date = db.func.now()
                    db.session.add(reg)

            summary['created'] += 1
            summary['details'].append({
                'student_id': src.student_id,
                'target_activity_id': target.id,
                'action': 'created',
                'reason': 'synced_from_source'
            })

    # Commit cuando no es dry_run
    if not dry_run:
        db.session.commit()

    return summary
