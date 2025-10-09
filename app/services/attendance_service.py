from datetime import datetime, timezone, timedelta
from flask import current_app
from app.utils.datetime_utils import localize_naive_datetime
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

    # Helper: ensure datetime is timezone-aware. If naive, interpret it in
    # the app timezone and convert to UTC using localize_naive_datetime.
    def _ensure_tz(dt):
        if dt is None:
            return None
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc)
        app_timezone = current_app.config.get(
            'APP_TIMEZONE', 'America/Mexico_City')
        return localize_naive_datetime(dt, app_timezone)

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

    # Calcular la superposición entre la ventana de presencia y la ventana programada
    # Helper: ensure timezone-aware
    def _ensure_tz(dt):
        if dt is None:
            return None
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc)
        app_timezone = current_app.config.get(
            'APP_TIMEZONE', 'America/Mexico_City')
        return localize_naive_datetime(dt, app_timezone)

    pres_start = _ensure_tz(attendance.check_in_time)
    pres_end = _ensure_tz(attendance.check_out_time)

    # Si no hay tiempos válidos, no calcular
    if not pres_start or not pres_end:
        return None

    act_start = _ensure_tz(getattr(activity, 'start_datetime', None))
    # Definir act_end según duración de la actividad si está disponible
    act_end = None
    try:
        if act_start is not None and getattr(activity, 'duration_hours', None) is not None:
            act_end = act_start + \
                timedelta(hours=float(activity.duration_hours))
    except Exception:
        act_end = None

    # Si no hay act_start o duration, caemos al comportamiento por defecto
    if not act_start or not act_end:
        # Fallback: usar duración neta completa (comportamiento legacy)
        net_duration_seconds = calculate_net_duration_seconds(attendance)
        expected_duration_seconds = (activity.duration_hours or 0) * 3600
        if expected_duration_seconds > 0:
            percentage = (net_duration_seconds /
                          expected_duration_seconds) * 100
            attendance.attendance_percentage = round(max(0, percentage), 2)
            if attendance.attendance_percentage >= 80:
                attendance.status = 'Asistió'
            elif attendance.attendance_percentage > 0:
                attendance.status = 'Parcial'
            else:
                attendance.status = 'Ausente'
            return attendance.attendance_percentage
        else:
            attendance.attendance_percentage = 100.0
            attendance.status = 'Asistió'
            return 100.0

    # calcular intersección
    window_start = max(pres_start, act_start)
    window_end = min(pres_end, act_end)
    overlap_seconds = max(0, (window_end - window_start).total_seconds())

    # calcular segundos de pausa que ocurran dentro de la superposición
    paused_seconds = 0
    if attendance.pause_time:
        pause_start = _ensure_tz(attendance.pause_time)
        pause_end = _ensure_tz(
            attendance.resume_time or attendance.check_out_time or datetime.now(timezone.utc))
        # solapamiento entre pausa y ventana calculada
        ps = max(pause_start, window_start) if pause_start and window_start else None
        pe = min(pause_end, window_end) if pause_end and window_end else None
        if ps and pe and pe > ps:
            paused_seconds = (pe - ps).total_seconds()

    net_seconds = max(0, overlap_seconds - paused_seconds)
    expected_seconds = max(0, (act_end - act_start).total_seconds())

    if expected_seconds > 0:
        # If the raw pause duration (resume - pause) exceeds or equals the
        # activity expected duration, treat as absent. This covers cases where
        # the user paused for longer than the activity length (external long
        # pause) even if a small non-paused slice remains inside the window.
        try:
            if attendance.pause_time and attendance.resume_time:
                raw_pause = (attendance.resume_time -
                             attendance.pause_time).total_seconds()
                if raw_pause >= expected_seconds:
                    attendance.attendance_percentage = 0.0
                    attendance.status = 'Ausente'
                    return 0.0
        except Exception:
            # If any unexpected issue occurs computing raw pause, continue with
            # the usual overlap-based calculation.
            pass
        percentage = (net_seconds / expected_seconds) * 100
        attendance.attendance_percentage = round(max(0, percentage), 2)
        if attendance.attendance_percentage >= 80:
            attendance.status = 'Asistió'
        elif attendance.attendance_percentage > 0:
            attendance.status = 'Parcial'
        else:
            attendance.status = 'Ausente'
        return attendance.attendance_percentage
    else:
        # fallback conservador
        attendance.attendance_percentage = 100.0
        attendance.status = 'Asistió'
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
            # Crear marcada como 'Asistió' y asumir 100% porque se deriva de
            # una asistencia confirmada en la actividad principal.
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
        'created': 0,
        'skipped': 0,
        'not_found': 0,
        'errors': [],
        'details': []
    }

    # Verificar que la actividad existe
    activity = db.session.get(Activity, activity_id)
    if not activity:
        summary['errors'].append({
            'control_number': '',
            'message': 'Actividad no encontrada'
        })
        return summary

    # Leer números de control del archivo
    control_numbers = []
    try:
        # Intentar leer como XLSX primero
        try:
            import pandas as pd
            file_stream.seek(0)
            # Read without treating first row as header
            df = pd.read_excel(io.BytesIO(
                file_stream.read()), sheet_name=0, engine='openpyxl', header=None)
            # Tomar la primera columna
            if df.shape[0] > 0:
                control_numbers = [str(val).strip()
                                   for val in df.iloc[:, 0] if str(val).strip()]
        except Exception:
            # Si falla, intentar leer como TXT
            file_stream.seek(0)
            content = file_stream.read()
            if isinstance(content, bytes):
                content = content.decode('utf-8', errors='ignore')
            lines = content.strip().split('\n')
            control_numbers = [line.strip()
                               for line in lines if line.strip()]
    except Exception as e:
        summary['errors'].append({
            'control_number': '',
            'message': f'Error al leer archivo: {str(e)}'
        })
        return summary

    if not control_numbers:
        summary['errors'].append({
            'control_number': '',
            'message': 'El archivo no contiene números de control'
        })
        return summary

    # Procesar cada número de control
    for control_number in control_numbers:
        # Evitar valores inválidos
        if not control_number or control_number.lower() in ['nan', 'none', '']:
            continue

        # Buscar estudiante en BD
        student = Student.query.filter_by(
            control_number=control_number).first()

        # Si no existe, buscar en API externa
        if not student:
            try:
                external_api_url = f"http://apps.tecvalles.mx:8091/api/estudiantes?search={control_number}"
                response = requests.get(external_api_url, timeout=10)
                if response.status_code == 200:
                    external_data = response.json()
                    # Crear nuevo estudiante
                    student = Student()
                    student.control_number = control_number
                    student.full_name = external_data.get(
                        'full_name', external_data.get('nombre', ''))
                    student.career = external_data.get(
                        'career', external_data.get('carrera', ''))
                    student.email = external_data.get('email', '')
                    if not dry_run:
                        db.session.add(student)
                        db.session.flush()  # Para obtener el ID
                else:
                    summary['not_found'] += 1
                    summary['errors'].append({
                        'control_number': control_number,
                        'message': 'No encontrado en BD ni API externa'
                    })
                    continue
            except Exception as e:
                summary['not_found'] += 1
                summary['errors'].append({
                    'control_number': control_number,
                    'message': f'Error al buscar en API externa: {str(e)}'
                })
                continue

        # Verificar si ya existe asistencia
        existing = Attendance.query.filter_by(
            student_id=student.id, activity_id=activity_id).first()
        if existing:
            summary['skipped'] += 1
            summary['details'].append({
                'control_number': control_number,
                'action': 'skipped',
                'student_name': student.full_name,
                'reason': 'Ya existe asistencia'
            })
            continue

        # Crear asistencia
        if not dry_run:
            attendance = Attendance()
            attendance.student_id = student.id
            attendance.activity_id = activity_id
            attendance.attendance_percentage = 100.0
            attendance.status = 'Asistió'
            db.session.add(attendance)

            # Actualizar registro si existe
            registration = Registration.query.filter_by(
                student_id=student.id, activity_id=activity_id).first()
            if registration:
                registration.attended = True
                registration.status = 'Asistió'
                registration.confirmation_date = db.func.now()
                db.session.add(registration)

        summary['created'] += 1
        summary['details'].append({
            'control_number': control_number,
            'action': 'created',
            'student_name': student.full_name
        })

    # Commit si no es dry_run
    if not dry_run:
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            summary['errors'].append({
                'control_number': '',
                'message': f'Error al guardar cambios: {str(e)}'
            })
            summary['created'] = 0

    return summary
