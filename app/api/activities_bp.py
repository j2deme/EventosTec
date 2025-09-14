from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError
from app import db
from app.schemas import activity_schema, activities_schema
from app.models.activity import Activity
from app.models.event import Event
from app.services import activity_service
from app.utils.auth_helpers import require_admin
from datetime import datetime, timezone
from app.utils.datetime_utils import parse_datetime_with_timezone

activities_bp = Blueprint('activities', __name__, url_prefix='/api/activities')

# Listar actividades


@activities_bp.route('/', methods=['GET'])
def get_activities():
    try:
        # Parámetros de filtrado
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        event_id = request.args.get('event_id', type=int)
        activity_type = request.args.get('type')
        search = request.args.get('search', '').strip()
        activity_type = request.args.get('activity_type')

        query = db.session.query(Activity).join(Event)

        if search:
            search_filter = f"%{search}%"
            query = query.filter(
                db.or_(
                    Activity.name.ilike(search_filter),
                    Activity.department.ilike(search_filter),
                    Activity.description.ilike(search_filter),
                    Activity.location.ilike(search_filter)
                )
            )

        if activity_type:
            query = query.filter(Activity.activity_type == activity_type)

        if event_id:
            query = query.filter(Activity.event_id == event_id)

        if activity_type:
            query = query.filter(Activity.activity_type == activity_type)

        # Ordenar por fecha de creación (más recientes primero)
        query = query.order_by(Activity.created_at.desc())

        activities = query.paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify({
            'activities': activities_schema.dump(activities.items),
            'total': activities.total,
            'pages': activities.pages,
            'current_page': page,
            'from': (page - 1) * per_page + 1 if activities.total > 0 else 0,
            'to': min(page * per_page, activities.total)
        }), 200

    except Exception as e:
        return jsonify({'message': 'Error al obtener actividades', 'error': str(e)}), 500

# Crear actividad


@activities_bp.route('/', methods=['POST'])
@jwt_required()
@require_admin
def create_activity():
    try:
        # Validar datos de entrada
        data = activity_schema.load(request.get_json())

        if 'start_datetime' in data:
            data['start_datetime'] = parse_datetime_with_timezone(
                data['start_datetime'])
        if 'end_datetime' in data:
            data['end_datetime'] = parse_datetime_with_timezone(
                data['end_datetime'])

        # Verificar que el evento exista
        event = db.session.get(Event, data['event_id'])
        if not event:
            return jsonify({'message': 'Evento no encontrado'}), 404

        # Crear actividad
        activity = activity_service.create_activity(data)

        return jsonify({
            'message': 'Actividad creada exitosamente',
            'activity': activity_schema.dump(activity)
        }), 201

    except ValidationError as err:
        return jsonify({'message': 'Error de validación', 'errors': err.messages}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error al crear actividad', 'error': str(e)}), 400

# Obtener actividad por ID


@activities_bp.route('/<int:activity_id>', methods=['GET'])
def get_activity(activity_id):
    try:
        activity = db.session.get(Activity, activity_id)
        if not activity:
            return jsonify({'message': 'Actividad no encontrada'}), 404

        return jsonify({'activity': activity_schema.dump(activity)}), 200

    except Exception as e:
        return jsonify({'message': 'Error al obtener actividad', 'error': str(e)}), 500

# Actualizar actividad


@activities_bp.route('/<int:activity_id>', methods=['PUT'])
@jwt_required()
@require_admin
def update_activity(activity_id):
    try:
        activity = db.session.get(Activity, activity_id)
        if not activity:
            return jsonify({'message': 'Actividad no encontrada'}), 404

        # Validar datos de entrada
        data = activity_schema.load(request.get_json(), partial=True)

        # Parsear fechas con zona horaria si se proporcionan
        if 'start_datetime' in data:
            data['start_datetime'] = parse_datetime_with_timezone(
                data['start_datetime'])
        if 'end_datetime' in data:
            data['end_datetime'] = parse_datetime_with_timezone(
                data['end_datetime'])

        activity = activity_service.update_activity(activity_id, data)

        return jsonify({
            'message': 'Actividad actualizada exitosamente',
            'activity': activity_schema.dump(activity)
        }), 200

    except ValidationError as err:
        return jsonify({'message': 'Error de validación', 'errors': err.messages}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error al actualizar actividad', 'error': str(e)}), 400

# Eliminar actividad


@activities_bp.route('/<int:activity_id>', methods=['DELETE'])
@jwt_required()
@require_admin
def delete_activity(activity_id):
    try:
        activity = db.session.get(Activity, activity_id)
        if not activity:
            return jsonify({'message': 'Actividad no encontrada'}), 404

        db.session.delete(activity)
        db.session.commit()

        return jsonify({'message': 'Actividad eliminada exitosamente'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error al eliminar actividad', 'error': str(e)}), 500

# Obtener asistencias de una actividad


@activities_bp.route('/<int:activity_id>/attendances', methods=['GET'])
@jwt_required()
def get_activity_attendances(activity_id):
    try:
        activity = db.session.get(Activity, activity_id)
        if not activity:
            return jsonify({'message': 'Actividad no encontrada'}), 404

        attendances = activity.attendances
        from app.schemas import attendances_schema
        return jsonify({
            'attendances': attendances_schema.dump(attendances)
        }), 200

    except Exception as e:
        return jsonify({'message': 'Error al obtener asistencias', 'error': str(e)}), 500


# Obtener preregistros de una actividad
@activities_bp.route('/<int:activity_id>/registrations', methods=['GET'])
@jwt_required()
def get_activity_registrations(activity_id):
    try:
        activity = db.session.get(Activity, activity_id)
        if not activity:
            return jsonify({'message': 'Actividad no encontrada'}), 404

        registrations = activity.registrations
        from app.schemas import registrations_schema
        return jsonify({
            'registrations': registrations_schema.dump(registrations)
        }), 200

    except Exception as e:
        return jsonify({'message': 'Error al obtener preregistros', 'error': str(e)}), 500


@activities_bp.route('/<int:activity_id>/related', methods=['GET'])
@jwt_required()
@require_admin
def get_related_activities(activity_id):
    """Devuelve las actividades relacionadas con una actividad."""
    activity = db.session.get(Activity, activity_id)
    if not activity:
        return jsonify({'message': 'Actividad no encontrada'}), 404
    from app.schemas import activities_schema
    return jsonify({
        'related_activities': activities_schema.dump(activity.related_activities)
    }), 200


@activities_bp.route('/<int:activity_id>/related', methods=['POST'])
@jwt_required()
@require_admin
def add_related_activity(activity_id):
    """Enlaza una actividad con otra, manejando errores de concurrencia."""
    import pymysql
    data = request.get_json()
    related_id = data.get('related_activity_id')
    if not related_id:
        return jsonify({'message': 'Falta el ID de la actividad a enlazar'}), 400
    if activity_id == related_id:
        return jsonify({'message': 'No se puede enlazar una actividad consigo misma'}), 400
    activity = db.session.get(Activity, activity_id)
    related = db.session.get(Activity, related_id)
    if not activity or not related:
        return jsonify({'message': 'Una o ambas actividades no existen'}), 404
    # Solo permitir enlazar actividades del mismo evento
    if activity.event_id != related.event_id:
        return jsonify({'message': 'Solo se pueden enlazar actividades del mismo evento.'}), 400
    if related in activity.related_activities:
        return jsonify({'message': 'Las actividades ya están enlazadas'}), 400
    try:
        activity.related_activities.append(related)
        db.session.commit()
    except pymysql.err.OperationalError as e:
        # Error 1020: Record has changed since last read
        if e.args[0] == 1020:
            db.session.rollback()
            # Reintentar una vez
            try:
                db.session.refresh(activity)
                db.session.refresh(related)
                activity.related_activities.append(related)
                db.session.commit()
                return jsonify({'message': 'Actividades enlazadas exitosamente (reintento)'}), 200
            except Exception as e2:
                db.session.rollback()
                return jsonify({'message': f'Error de concurrencia al enlazar actividades: {str(e2)}'}), 500
        else:
            db.session.rollback()
            return jsonify({'message': f'Error al enlazar actividades: {str(e)}'}), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Error al enlazar actividades: {str(e)}'}), 500
    return jsonify({'message': 'Actividades enlazadas exitosamente'}), 200


@activities_bp.route('/<int:activity_id>/related/<int:related_id>', methods=['DELETE'])
@jwt_required()
@require_admin
def remove_related_activity(activity_id, related_id):
    """Desenlaza dos actividades."""
    activity = db.session.get(Activity, activity_id)
    related = db.session.get(Activity, related_id)
    if not activity or not related:
        return jsonify({'message': 'Una o ambas actividades no existen'}), 404
    if related not in activity.related_activities:
        return jsonify({'message': 'Las actividades no están enlazadas'}), 400
    activity.related_activities.remove(related)
    db.session.commit()
    return jsonify({'message': 'Actividades desenlazadas exitosamente'}), 200


@activities_bp.route('/relations', methods=['GET'])
def get_activity_relations():
    try:
        activities = db.session.query(Activity).all()
        result = []
        for activity in activities:
            result.append({
                'id': activity.id,
                'name': activity.name,
                'event_id': activity.event_id,
                'related_activities': [
                    {'id': a.id, 'name': a.name, 'event_id': a.event_id}
                    for a in activity.related_activities
                ],
                'linked_by': [
                    {'id': a.id, 'name': a.name, 'event_id': a.event_id}
                    for a in activity.related_to_activities
                ]
            })
        return jsonify({'activities': result}), 200
    except Exception as e:
        return jsonify({'message': 'Error al obtener relaciones', 'error': str(e)}), 500
