from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app import db
from app.schemas import event_schema, events_schema
from app.models.event import Event
from datetime import datetime
from app.utils.auth_helpers import require_admin

events_bp = Blueprint('events', __name__, url_prefix='/api/events')

# Listar eventos


@events_bp.route('/', methods=['GET'])
def get_events():
    try:
        # Parámetros de paginación y filtrado
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        status = request.args.get('status')

        query = db.session.query(Event)

        if status:
            is_active = status.lower() == 'active'
            query = query.filter_by(is_active=is_active)

        # Ordenar por fecha de creación (más recientes primero)
        query = query.order_by(Event.created_at.desc())

        events = query.paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify({
            'events': events_schema.dump(events.items),
            'total': events.total,
            'pages': events.pages,
            'current_page': page
        }), 200

    except Exception as e:
        return jsonify({'message': 'Error al obtener eventos', 'error': str(e)}), 500

# Crear evento


@events_bp.route('/', methods=['POST'])
@jwt_required()
@require_admin
def create_event():
    try:
        # Validar datos de entrada
        data = event_schema.load(request.get_json())

        # Crear evento
        event = Event(**data)
        db.session.add(event)
        db.session.commit()

        return jsonify({
            'message': 'Evento creado exitosamente',
            'event': event_schema.dump(event)
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error al crear evento', 'error': str(e)}), 400

# Obtener evento por ID


@events_bp.route('/<int:event_id>', methods=['GET'])
def get_event(event_id):
    try:
        event = db.session.get(Event, event_id)
        if not event:
            return jsonify({'message': 'Evento no encontrado'}), 404

        return jsonify({'event': event_schema.dump(event)}), 200

    except Exception as e:
        return jsonify({'message': 'Error al obtener evento', 'error': str(e)}), 500

# Actualizar evento


@events_bp.route('/<int:event_id>', methods=['PUT'])
@jwt_required()
@require_admin
def update_event(event_id):
    try:
        event = db.session.get(Event, event_id)
        if not event:
            return jsonify({'message': 'Evento no encontrado'}), 404

        # Validar datos de entrada
        data = event_schema.load(request.get_json(), partial=True)

        # Actualizar campos
        for key, value in data.items():
            setattr(event, key, value)

        db.session.commit()

        return jsonify({
            'message': 'Evento actualizado exitosamente',
            'event': event_schema.dump(event)
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error al actualizar evento', 'error': str(e)}), 400

# Eliminar evento


@events_bp.route('/<int:event_id>', methods=['DELETE'])
@jwt_required()
@require_admin
def delete_event(event_id):
    try:
        event = db.session.get(Event, event_id)
        if not event:
            return jsonify({'message': 'Evento no encontrado'}), 404

        db.session.delete(event)
        db.session.commit()

        return jsonify({'message': 'Evento eliminado exitosamente'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error al eliminar evento', 'error': str(e)}), 500

# Obtener actividades de un evento


@events_bp.route('/<int:event_id>/activities', methods=['GET'])
def get_event_activities(event_id):
    try:
        event = db.session.get(Event, event_id)
        if not event:
            return jsonify({'message': 'Evento no encontrado'}), 404

        # Parámetros de filtrado
        activity_type = request.args.get('type')

        query = event.activities

        if activity_type:
            query = query.filter_by(activity_type=activity_type)

        activities = query.all()

        from app.schemas import activities_schema
        return jsonify({
            'activities': activities_schema.dump(activities)
        }), 200

    except Exception as e:
        return jsonify({'message': 'Error al obtener actividades', 'error': str(e)}), 500
