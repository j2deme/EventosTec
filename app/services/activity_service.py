# app/services/activity_service.py
from app import db
from app.models.activity import Activity
from app.models.event import Event
from datetime import datetime
from marshmallow import ValidationError


def validate_activity_dates(activity_data):
    """
    Valida que las fechas de la actividad estén dentro del rango del evento.

    Args:
        activity_data (dict): Datos de la actividad a validar

    Raises:
        ValidationError: Si las fechas no son válidas
    """
    try:
        # Obtener el evento
        event = db.session.get(Event, activity_data['event_id'])
        if not event:
            raise ValidationError('Evento no encontrado', 'event_id')

        # Convertir fechas si son strings (para compatibilidad)
        start_datetime = activity_data['start_datetime']
        end_datetime = activity_data['end_datetime']

        # Si son strings, convertir a datetime
        if isinstance(start_datetime, str):
            start_datetime = datetime.fromisoformat(
                start_datetime.replace('Z', '+00:00'))
        if isinstance(end_datetime, str):
            end_datetime = datetime.fromisoformat(
                end_datetime.replace('Z', '+00:00'))

        # Validar que las fechas de la actividad estén dentro del rango del evento
        if start_datetime < event.start_date:
            raise ValidationError(
                f'La fecha de inicio de la actividad ({start_datetime}) no puede ser anterior a la fecha de inicio del evento ({event.start_date})',
                'start_datetime'
            )

        if end_datetime > event.end_date:
            raise ValidationError(
                f'La fecha de fin de la actividad ({end_datetime}) no puede ser posterior a la fecha de fin del evento ({event.end_date})',
                'end_datetime'
            )

        # Validar que la fecha de inicio sea anterior a la fecha de fin
        if start_datetime >= end_datetime:
            raise ValidationError(
                'La fecha de inicio debe ser anterior a la fecha de fin',
                'start_datetime'
            )

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

    # Crear actividad
    activity = Activity(**activity_data)
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

    # Si se están actualizando fechas o evento, validar
    if ('start_datetime' in activity_data or
        'end_datetime' in activity_data or
            'event_id' in activity_data):
        # Crear datos combinados para validación
        combined_data = {
            'event_id': activity_data.get('event_id', activity.event_id),
            'start_datetime': activity_data.get('start_datetime', activity.start_datetime),
            'end_datetime': activity_data.get('end_datetime', activity.end_datetime),
            **{k: v for k, v in activity_data.items() if k not in ['event_id', 'start_datetime', 'end_datetime']}
        }
        validate_activity_dates(combined_data)

    # Actualizar campos
    for key, value in activity_data.items():
        setattr(activity, key, value)

    db.session.commit()
    return activity
