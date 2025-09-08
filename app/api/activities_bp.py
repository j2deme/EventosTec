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

activities_bp = Blueprint('activities', __name__, url_prefix='/api/activities')


def parse_datetime_with_timezone(dt_string):
    """Parsea una cadena de fecha y asegura que tenga zona horaria."""
    if isinstance(dt_string, str):
        # Intentar parsear con diferentes formatos
        try:
            # Formato ISO con zona horaria
            dt = datetime.fromisoformat(dt_string)
        except ValueError:
            try:
                # Formato alternativo
                dt = datetime.strptime(dt_string, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                raise ValidationError(
                    f"Formato de fecha inválido: {dt_string}")

        # Si no tiene zona horaria, asignar UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt
    elif isinstance(dt_string, datetime):
        # Si ya es datetime, asegurar zona horaria
        if dt_string.tzinfo is None:
            return dt_string.replace(tzinfo=timezone.utc)
        return dt_string
    else:
        return dt_string

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
