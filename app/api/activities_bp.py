from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app import db
from app.schemas import activity_schema, activities_schema
from app.models.activity import Activity
from app.models.event import Event
from app.utils.auth_helpers import require_admin

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

        query = Activity.query

        if event_id:
            query = query.filter_by(event_id=event_id)

        if activity_type:
            query = query.filter_by(activity_type=activity_type)

        # Ordenar por fecha de inicio
        query = query.order_by(Activity.start_datetime.desc())

        activities = query.paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify({
            'activities': activities_schema.dump(activities.items),
            'total': activities.total,
            'pages': activities.pages,
            'current_page': page
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

        # Verificar que el evento exista
        event = db.session.get(Event, data['event_id'])
        if not event:
            return jsonify({'message': 'Evento no encontrado'}), 404

        # Crear actividad
        activity = Activity(**data)
        db.session.add(activity)
        db.session.commit()

        return jsonify({
            'message': 'Actividad creada exitosamente',
            'activity': activity_schema.dump(activity)
        }), 201

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

        # Actualizar campos
        for key, value in data.items():
            setattr(activity, key, value)

        db.session.commit()

        return jsonify({
            'message': 'Actividad actualizada exitosamente',
            'activity': activity_schema.dump(activity)
        }), 200

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
