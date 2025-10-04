from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError
from app import db
from app.schemas import activity_schema, activities_schema
from app.models.activity import Activity
from app.models.event import Event
from app.models.registration import Registration
from app.services import activity_service
from app.utils.auth_helpers import require_admin, get_user_or_403
from datetime import datetime, timezone
from typing import cast, Iterable
from app.utils.datetime_utils import parse_datetime_with_timezone
import json
import traceback

activities_bp = Blueprint('activities', __name__, url_prefix='/api/activities')


def _safe_dump_activities(iterable):
    """Dump an iterable of Activity objects one by one, falling back to
    Activity.to_dict() or a minimal representation if dumping fails for an item.
    This prevents a single malformed row (for example a raw JSON string in a
    JSON/Text column) from breaking the whole response with a "dictionary
    update sequence" error.
    """
    result = []
    for a in iterable:
        # Prefer using the model's to_dict() which avoids triggering lazy
        # loading or other session-dependent behaviour. Only use the
        # schema-based dump as a last resort.
        try:
            if hasattr(a, 'to_dict'):
                base = a.to_dict()
            else:
                base = {'id': getattr(a, 'id', None),
                        'name': getattr(a, 'name', None)}

            # Try to include minimal event info if available without forcing a
            # DB fetch. Access within try/except to avoid raising session
            # related errors.
            try:
                ev = getattr(a, 'event', None)
                if ev is not None:
                    base['event'] = {'id': getattr(
                        ev, 'id', None), 'name': getattr(ev, 'name', None)}
            except Exception:
                # ignore event issues
                pass

            result.append(base)

        except Exception:
            # As a final fallback, append a minimal safe representation
            try:
                result.append({'id': getattr(a, 'id', None),
                              'name': getattr(a, 'name', None)})
            except Exception:
                result.append({'id': None, 'name': None})

    return result

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
        for_student = request.args.get('for_student', default=None)
        exclude_types = request.args.get('exclude_types', default=None)

        # Usar Activity.query para compatibilidad con Flask-SQLAlchemy
        query = Activity.query.join(Event)

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

        if for_student is not None:
            fs_val = str(for_student).lower()
            if fs_val in ('1', 'true', 'yes'):
                # Define excluded types for students here
                excluded = ['Magistral']
                query = query.filter(~Activity.activity_type.in_(excluded))

        if exclude_types:
            types_list = [t.strip()
                          for t in exclude_types.split(',') if t.strip()]
            if types_list:
                query = query.filter(~Activity.activity_type.in_(types_list))

        if activity_type:
            query = query.filter(Activity.activity_type == activity_type)

        # Ordenar por fecha de creación (más recientes primero)
        query = query.order_by(Activity.created_at.desc())

        activities = query.paginate(
            page=page, per_page=per_page, error_out=False
        )

        total = activities.total or 0

        # Obtener conteo de preregistros por actividad en una sola consulta
        activity_ids = [a.id for a in activities.items]
        counts = {}
        if activity_ids:
            rows = db.session.query(
                Registration.activity_id,
                db.func.count(Registration.id)
            ).filter(
                Registration.activity_id.in_(activity_ids),
                # Contar registros que no estén cancelados ni marcados como ausente
                ~Registration.status.in_(['Ausente', 'Cancelado'])
            ).group_by(Registration.activity_id).all()

            counts = {r[0]: int(r[1]) for r in rows}

        dumped = _safe_dump_activities(activities.items)

        # Adjuntar current_capacity (número de preregistros 'Registrado') a cada actividad
        # También añadimos un alias `current_registrations` para compatibilidad
        # con plantillas/JS antiguas que esperan ese nombre.
        for item in dumped:
            try:
                val = counts.get(item.get('id'), 0)
                item['current_capacity'] = val
                # alias histórico usado en plantillas
                item['current_registrations'] = val
            except Exception:
                item['current_capacity'] = 0
                item['current_registrations'] = 0

        return jsonify({
            'activities': dumped,
            'total': total,
            'pages': activities.pages,
            'current_page': page,
            'from': (page - 1) * per_page + 1 if total > 0 else 0,
            'to': min(page * per_page, total)
        }), 200

    except Exception as e:
        tb = traceback.format_exc()
        # Include stack trace in response to help debugging in dev
        return jsonify({'message': 'Error al obtener actividades', 'error': str(e), 'trace': tb}), 500

# Crear actividad


@activities_bp.route('/', methods=['POST'])
@jwt_required()
@require_admin
def create_activity():
    try:
        # Normalizar payload y validar datos de entrada
        payload = request.get_json() or {}

        data = activity_schema.load(payload)

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

        dumped = activity_schema.dump(activity)
        # Añadir conteo real de preregistros (excluyendo 'Ausente' y 'Cancelado')
        try:
            count = db.session.query(db.func.count(Registration.id)).filter(
                Registration.activity_id == activity_id,
                ~Registration.status.in_(['Ausente', 'Cancelado'])
            ).scalar() or 0
            if isinstance(dumped, dict):
                dumped['current_capacity'] = int(count)
                dumped['current_registrations'] = int(count)
        except Exception:
            # Si hay cualquier error al calcular el conteo, mantener comportamiento previo
            if isinstance(dumped, dict):
                try:
                    dumped['current_registrations'] = dumped.get(
                        'current_capacity', 0)
                except Exception:
                    pass

        return jsonify({'activity': dumped}), 200

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
        payload = request.get_json() or {}

        data = activity_schema.load(payload, partial=True)

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

        # Control de acceso: admin ve todas; estudiante solo ve sus propias asistencias
        user, user_type, err = get_user_or_403()
        if err:
            return err

        from app.schemas import attendances_schema
        if user_type == 'admin':
            attendances = list(cast(Iterable, activity.attendances))
            return jsonify({'attendances': attendances_schema.dump(attendances)}), 200
        elif user_type == 'student' and user is not None:
            # filtrar asistencias por student_id
            attendances = [a for a in list(
                cast(Iterable, activity.attendances)) if a.student_id == user.id]
            return jsonify({'attendances': attendances_schema.dump(attendances)}), 200
        else:
            return jsonify({'message': 'Acceso denegado'}), 403

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

        # Control de acceso: admin ve todos los preregistros; student solo los suyos
        user, user_type, err = get_user_or_403()
        if err:
            return err

        from app.schemas import registrations_schema
        if user_type == 'admin':
            registrations = list(cast(Iterable, activity.registrations))
            return jsonify({'registrations': registrations_schema.dump(registrations)}), 200
        elif user_type == 'student' and user is not None:
            registrations = [r for r in list(
                cast(Iterable, activity.registrations)) if r.student_id == user.id]
            return jsonify({'registrations': registrations_schema.dump(registrations)}), 200
        else:
            return jsonify({'message': 'Acceso denegado'}), 403

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
        'related_activities': _safe_dump_activities(list(cast(Iterable, activity.related_activities)))
    }), 200


@activities_bp.route('/<int:activity_id>/token', methods=['GET'])
@jwt_required()
@require_admin
def get_activity_token(activity_id):
    """Devuelve un token stateless para la actividad y la URL de registro basada en token.

    Este endpoint está protegido (admin) y sirve para generar enlaces/QRs operativos.
    """
    try:
        activity = db.session.get(Activity, activity_id)
        if not activity:
            return jsonify({'message': 'Actividad no encontrada'}), 404

        # Importar la util util de tokens
        from app.utils.token_utils import generate_activity_token

        token = generate_activity_token(activity.id)
        url = request.host_url.rstrip('/') + '/self-register/' + token

        return jsonify({'token': token, 'url': url}), 200
    except Exception as e:
        return jsonify({'message': 'Error generando token', 'error': str(e)}), 500


@activities_bp.route('/<int:activity_id>/public-token', methods=['GET'])
@jwt_required()
@require_admin
def get_public_activity_token(activity_id):
    """Devuelve un token público (para jefes) distinto del token de autorregistro."""
    try:
        activity = db.session.get(Activity, activity_id)
        if not activity:
            return jsonify({'message': 'Actividad no encontrada'}), 404

        from app.utils.token_utils import generate_public_token

        token = generate_public_token(activity.id)
        url = request.host_url.rstrip('/') + '/public/registrations/' + token

        return jsonify({'token': token, 'url': url}), 200
    except Exception as e:
        return jsonify({'message': 'Error generando public token', 'error': str(e)}), 500


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
    if related in list(cast(Iterable, activity.related_activities)):
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
    if related not in list(cast(Iterable, activity.related_activities)):
        return jsonify({'message': 'Las actividades no están enlazadas'}), 400
    activity.related_activities.remove(related)
    db.session.commit()
    return jsonify({'message': 'Actividades desenlazadas exitosamente'}), 200


@activities_bp.route('/relations', methods=['GET'])
def get_activity_relations():
    try:
        activities = Activity.query.all()
        result = []
        for activity in activities:
            related_list = list(cast(Iterable, activity.related_activities))
            linked_by_list = list(cast(Iterable, getattr(
                activity, 'related_to_activities', [])))
            result.append({
                'id': activity.id,
                'name': activity.name,
                'event_id': activity.event_id,
                'related_activities': [
                    {'id': a.id, 'name': a.name, 'event_id': a.event_id}
                    for a in related_list
                ],
                'linked_by': [
                    {'id': a.id, 'name': a.name, 'event_id': a.event_id}
                    for a in linked_by_list
                ]
            })
        return jsonify({'activities': result}), 200
    except Exception as e:
        return jsonify({'message': 'Error al obtener relaciones', 'error': str(e)}), 500


@activities_bp.route('/batch', methods=['POST'])
@jwt_required()
@require_admin
def batch_upload_activities():
    """Upload an XLSX file containing multiple activities and create them in batch.

    Form data:
      - file: the XLSX file (required)
      - event_id: optional; if provided, used for rows that lack event_id
      - dry_run: optional (1/0) default 1 -> if 1 only validate and return report
    """
    try:
        if 'file' not in request.files:
            return jsonify({'message': 'Falta el archivo.'}), 400

        file = request.files['file']
        event_id = request.form.get('event_id')
        dry_run = request.form.get('dry_run', '1')
        dry = str(dry_run).strip() in ('1', 'true', 'yes')

        # Call service
        report = activity_service.create_activities_from_xlsx(
            file.stream, event_id=event_id, dry_run=dry)

        status_code = 200 if dry else 201
        return jsonify({'message': 'Batch processed', 'report': report}), status_code

    except Exception as e:
        tb = traceback.format_exc()
        return jsonify({'message': 'Error en importación batch', 'error': str(e), 'trace': tb}), 500
