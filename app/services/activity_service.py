from datetime import datetime, timezone
from app import db
from app.models.activity import Activity
from app.models.event import Event
from marshmallow import ValidationError
import json


def validate_activity_dates(activity_data):
    """
    Valida que las fechas de la actividad estén dentro del rango del evento.

    Args:
        activity_data (dict): Datos de la actividad a validar

    Raises:
        ValidationError: Si las fechas no son válidas
    """
    try:
        event_id = activity_data.get('event_id')
        start_datetime = activity_data.get('start_datetime')
        end_datetime = activity_data.get('end_datetime')

        # Asegurar que las fechas sean timezone-aware
        if start_datetime and start_datetime.tzinfo is None:
            start_datetime = start_datetime.replace(tzinfo=timezone.utc)
        if end_datetime and end_datetime.tzinfo is None:
            end_datetime = end_datetime.replace(tzinfo=timezone.utc)

        if not event_id:
            raise ValidationError('El evento es requerido')

        event = db.session.get(Event, event_id)
        if not event:
            raise ValidationError('Evento no encontrado')

        # Asegurar que las fechas del evento sean timezone-aware
        event_start = event.start_date
        event_end = event.end_date
        if event_start and event_start.tzinfo is None:
            event_start = event_start.replace(tzinfo=timezone.utc)
        if event_end and event_end.tzinfo is None:
            event_end = event_end.replace(tzinfo=timezone.utc)

        if start_datetime and (start_datetime < event_start or start_datetime > event_end):
            raise ValidationError(
                'La fecha de inicio de la actividad debe estar dentro del rango del evento')

        if end_datetime and (end_datetime < event_start or end_datetime > event_end):
            raise ValidationError(
                'La fecha de fin de la actividad debe estar dentro del rango del evento')

        if start_datetime and end_datetime and start_datetime > end_datetime:
            raise ValidationError(
                'La fecha de inicio no puede ser posterior a la fecha de fin')

    except KeyError as e:
        raise ValidationError(f'Campo requerido faltante: {str(e)}')
    except ValueError as e:
        raise ValidationError(f'Formato de fecha inválido: {str(e)}')


def create_activity(activity_data):
    """
    Crea una nueva actividad con validaciones.

    Args:
        activity_data (dict): Datos de la actividad

    Returns:
        Activity: La actividad creada

    Raises:
        ValidationError: Si los datos no son válidos
    """
    # Validar fechas
    validate_activity_dates(activity_data)

    # Asegurar que las fechas sean timezone-aware
    if 'start_datetime' in activity_data and activity_data['start_datetime'].tzinfo is None:
        activity_data['start_datetime'] = activity_data['start_datetime'].replace(
            tzinfo=timezone.utc)
    if 'end_datetime' in activity_data and activity_data['end_datetime'].tzinfo is None:
        activity_data['end_datetime'] = activity_data['end_datetime'].replace(
            tzinfo=timezone.utc)

    # Calcular duración si no se proporciona
    if 'duration_hours' not in activity_data or activity_data['duration_hours'] is None:
        start = activity_data['start_datetime']
        end = activity_data['end_datetime']
        activity_data['duration_hours'] = (end - start).total_seconds() / 3600

    # Serializar campos JSON si vienen como estructuras Python
    if 'speakers' in activity_data and activity_data['speakers'] is not None:
        try:
            if not isinstance(activity_data['speakers'], str):
                activity_data['speakers'] = json.dumps(
                    activity_data['speakers'])
            else:
                json.loads(activity_data['speakers'])
        except Exception:
            raise ValidationError('Campo speakers debe ser JSON serializable')

    if 'target_audience' in activity_data and activity_data['target_audience'] is not None:
        try:
            if not isinstance(activity_data['target_audience'], str):
                activity_data['target_audience'] = json.dumps(
                    activity_data['target_audience'])
            else:
                json.loads(activity_data['target_audience'])
        except Exception:
            raise ValidationError(
                'Campo target_audience debe ser JSON serializable')

    # Crear la actividad de forma explícita para evitar pasar un dict
    # directamente al constructor (mejora la trazabilidad y evita
    # advertencias del analizador estático).
    activity = Activity()
    for key, value in activity_data.items():
        setattr(activity, key, value)

    db.session.add(activity)
    db.session.commit()

    return activity


def update_activity(activity_id, activity_data):
    """
    Actualiza una actividad existente con validaciones.

    Args:
        activity_id (int): ID de la actividad
        activity_data (dict): Datos actualizados

    Returns:
        Activity: La actividad actualizada

    Raises:
        ValidationError: Si los datos no son válidos
    """
    # Obtener actividad existente
    activity = db.session.get(Activity, activity_id)
    if not activity:
        raise ValidationError('Actividad no encontrada')

    # Si se están actualizando fechas, validar
    if 'start_datetime' in activity_data or 'end_datetime' in activity_data or 'event_id' in activity_data:
        # Combinar datos existentes con nuevos para validación
        validation_data = {
            'event_id': activity_data.get('event_id', activity.event_id),
            'start_datetime': activity_data.get('start_datetime', activity.start_datetime),
            'end_datetime': activity_data.get('end_datetime', activity.end_datetime)
        }
        validate_activity_dates(validation_data)

    # Asegurar que las fechas sean timezone-aware si se actualizan
    if 'start_datetime' in activity_data and activity_data['start_datetime'].tzinfo is None:
        activity_data['start_datetime'] = activity_data['start_datetime'].replace(
            tzinfo=timezone.utc)
    if 'end_datetime' in activity_data and activity_data['end_datetime'].tzinfo is None:
        activity_data['end_datetime'] = activity_data['end_datetime'].replace(
            tzinfo=timezone.utc)

    if 'duration_hours' in activity_data and activity_data['duration_hours'] is not None:
        start_dt = activity_data.get('start_datetime', activity.start_datetime)
        end_dt = activity_data.get('end_datetime', activity.end_datetime)
        duration = activity_data['duration_hours']

        if start_dt and end_dt:
            calculated_duration = (end_dt - start_dt).total_seconds() / 3600
            if not (0 < duration <= calculated_duration):
                raise ValidationError(
                    f'La duración proporcionada ({duration} horas) debe ser mayor que 0 y menor o igual a la duración calculada a partir de las fechas ({calculated_duration:.2f} horas).'
                )

    for key, value in activity_data.items():
        # Serializar JSON fields cuando se actualizan
        if key == 'speakers' and value is not None:
            try:
                if not isinstance(value, str):
                    value = json.dumps(value)
                else:
                    json.loads(value)
            except Exception:
                raise ValidationError(
                    'Campo speakers debe ser JSON serializable')

        if key == 'target_audience' and value is not None:
            try:
                if not isinstance(value, str):
                    value = json.dumps(value)
                else:
                    json.loads(value)
            except Exception:
                raise ValidationError(
                    'Campo target_audience debe ser JSON serializable')

        setattr(activity, key, value)

    db.session.commit()
    return activity
