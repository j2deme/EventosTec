from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError
from app import db
from app.schemas import activity_schema
from app.models.activity import Activity
from sqlalchemy import func
from app.models.event import Event
from app.models.registration import Registration
from app.services import activity_service
from app.models import activity_relations
from app.utils.slug_utils import slugify, generate_unique_slug
from app.utils.auth_helpers import require_admin
from typing import cast, Iterable
from app.utils.datetime_utils import parse_datetime_with_timezone, safe_iso
import traceback

activities_bp = Blueprint("activities", __name__, url_prefix="/api/activities")


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
            if hasattr(a, "to_dict"):
                base = a.to_dict()
            else:
                base = {"id": getattr(a, "id", None), "name": getattr(a, "name", None)}

            # Try to include minimal event info if available without forcing a
            # DB fetch. Access within try/except to avoid raising session
            # related errors.
            try:
                ev = getattr(a, "event", None)
                if ev is not None:
                    base["event"] = {
                        "id": getattr(ev, "id", None),
                        "name": getattr(ev, "name", None),
                    }
            except Exception:
                # ignore event issues
                pass

            result.append(base)

        except Exception:
            # As a final fallback, append a minimal safe representation
            try:
                result.append(
                    {"id": getattr(a, "id", None), "name": getattr(a, "name", None)}
                )
            except Exception:
                result.append({"id": None, "name": None})

    return result


# Listar actividades


@activities_bp.route("/", methods=["GET"])
def get_activities():
    try:
        # Parámetros de filtrado
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 10, type=int)
        event_id = request.args.get("event_id", type=int)
        activity_type = request.args.get("type")
        search = request.args.get("search", "").strip()
        activity_type = request.args.get("activity_type")
        for_student = request.args.get("for_student", default=None)
        exclude_types = request.args.get("exclude_types", default=None)

        # Usar Activity.query para compatibilidad con Flask-SQLAlchemy
        query = Activity.query.join(Event)

        if search:
            search_filter = f"%{search}%"
            query = query.filter(
                db.or_(
                    Activity.name.ilike(search_filter),
                    Activity.department.ilike(search_filter),
                    Activity.description.ilike(search_filter),
                    Activity.location.ilike(search_filter),
                )
            )

        if activity_type:
            query = query.filter(Activity.activity_type == activity_type)

        # Filtrar actividades que tienen relaciones salientes (activity_relations)
        has_related = request.args.get("has_related", default=None)
        if has_related is not None:
            sval = str(has_related).lower()
            if sval in ("1", "true", "yes"):
                # join con la tabla de asociación para requerir al menos una relación
                query = query.join(
                    activity_relations,
                    Activity.id == activity_relations.c.activity_id,
                )

        if event_id:
            query = query.filter(Activity.event_id == event_id)

        # Filter by department (case-insensitive). Support both partial
        # matches and exact case-insensitive equality to be tolerant with
        # how departments are stored.
        department = request.args.get("department")
        if department:
            dep = department.strip()
            if dep:
                dep_like = f"%{dep}%"
                query = query.filter(
                    db.or_(
                        Activity.department.ilike(dep_like),
                        func.lower(Activity.department) == dep.lower(),
                    )
                )

        if for_student is not None:
            fs_val = str(for_student).lower()
            if fs_val in ("1", "true", "yes"):
                # Define excluded types for students here
                excluded = ["Magistral"]
                query = query.filter(~Activity.activity_type.in_(excluded))

        if exclude_types:
            types_list = [t.strip() for t in exclude_types.split(",") if t.strip()]
            if types_list:
                query = query.filter(~Activity.activity_type.in_(types_list))

        if activity_type:
            query = query.filter(Activity.activity_type == activity_type)

        # Ordenamiento: permitir parámetro sort=name:asc|name:desc o por created_at desc por defecto
        sort = request.args.get("sort", None)
        if sort:
            try:
                key, direction = sort.split(":", 1)
                key = key.strip()
                direction = direction.strip().lower()
                if key == "name":
                    if direction == "asc":
                        query = query.order_by(Activity.name.asc())
                    else:
                        query = query.order_by(Activity.name.desc())
                else:
                    # Fallback al orden por creación
                    query = query.order_by(Activity.created_at.desc())
            except Exception:
                query = query.order_by(Activity.created_at.desc())
        else:
            # Ordenar por fecha de creación (más recientes primero) por defecto
            query = query.order_by(Activity.created_at.desc())

        # max_per_page=100: los selectores ya no necesitan descargar todo el
        # listado (usan /lookup), así que se limita el impacto de una petición
        # con un per_page desorbitado.
        activities = query.paginate(
            page=page, per_page=per_page, error_out=False, max_per_page=100
        )

        total = activities.total or 0

        # Obtener conteo de preregistros por actividad en una sola consulta
        activity_ids = [a.id for a in activities.items]
        counts = {}
        if activity_ids:
            rows = (
                db.session.query(
                    Registration.activity_id, db.func.count(Registration.id)
                )
                .filter(
                    Registration.activity_id.in_(activity_ids),
                    # Contar registros que no estén cancelados ni marcados como ausente
                    ~Registration.status.in_(["Ausente", "Cancelado"]),
                )
                .group_by(Registration.activity_id)
                .all()
            )

            counts = {r[0]: int(r[1]) for r in rows}

        dumped = _safe_dump_activities(activities.items)
        # Añadir public_url si existe public_slug en la representación
        for item in dumped:
            try:
                if isinstance(item, dict) and item.get("public_slug"):
                    item["public_url"] = (
                        request.host_url.rstrip("/")
                        + "/public/registrations/"
                        + item["public_slug"]
                    )
            except Exception:
                pass

        # Adjuntar current_capacity (número de preregistros 'Registrado') a cada actividad
        # También añadimos un alias `current_registrations` para compatibilidad
        # con plantillas/JS antiguas que esperan ese nombre.
        for item in dumped:
            try:
                val = counts.get(item.get("id"), 0)
                item["current_capacity"] = val
                # alias histórico usado en plantillas
                item["current_registrations"] = val
            except Exception:
                item["current_capacity"] = 0
                item["current_registrations"] = 0

        return jsonify(
            {
                "activities": dumped,
                "total": total,
                "pages": activities.pages,
                "current_page": page,
                "from": (page - 1) * per_page + 1 if total > 0 else 0,
                "to": min(page * per_page, total),
            }
        ), 200

    except Exception as e:
        tb = traceback.format_exc()
        # Include stack trace in response to help debugging in dev
        return jsonify(
            {"message": "Error al obtener actividades", "error": str(e), "trace": tb}
        ), 500


# Lookup de actividades para selectores y filtros
# ─────────────────────────────────────────────────────────────────────────────
# GET /api/activities/lookup[?event_id=&search=&type=&department=]
#
# Devuelve la lista COMPLETA de actividades con solo los campos que usan los
# selectores y filtros del admin (nombre, departamento, tipo y el evento al
# que pertenecen, que la plantilla muestra junto al nombre). No pagina.
#
# Antes estas vistas pedían `/api/activities?per_page=1000`, que serializaba
# 111 objetos COMPLETOS (descripción, requisitos, ponentes en JSON, fechas de
# creación...) por cada visita, solo para poblar un <select>.
#
# Contrato: { activities: [ {id, name, event_id, department, activity_type,
#                            start_datetime, end_datetime,
#                            event: {id, name}} ], total }
@activities_bp.route("/lookup", methods=["GET"])
def lookup_activities():
    try:
        from sqlalchemy.orm import joinedload

        event_id = request.args.get("event_id", type=int)
        activity_type = request.args.get("activity_type")
        department = request.args.get("department")
        search = (request.args.get("search") or "").strip()

        query = Activity.query.options(joinedload(Activity.event))

        if event_id:
            query = query.filter(Activity.event_id == event_id)

        if activity_type:
            query = query.filter(Activity.activity_type == activity_type)

        if department:
            query = query.filter(Activity.department.ilike(department.strip()))

        if search:
            search_filter = f"%{search}%"
            query = query.filter(
                db.or_(
                    Activity.name.ilike(search_filter),
                    Activity.department.ilike(search_filter),
                )
            )

        rows = query.order_by(Activity.start_datetime.asc(), Activity.name.asc()).all()

        activities = []
        for a in rows:
            ev = getattr(a, "event", None)
            activities.append(
                {
                    "id": a.id,
                    "name": a.name,
                    "code": a.code,
                    "event_id": a.event_id,
                    "department": a.department,
                    "activity_type": a.activity_type,
                    "start_datetime": safe_iso(a.start_datetime),
                    "end_datetime": safe_iso(a.end_datetime),
                    "event": {
                        "id": getattr(ev, "id", None),
                        "name": getattr(ev, "name", None),
                    }
                    if ev is not None
                    else None,
                }
            )

        return jsonify({"activities": activities, "total": len(activities)}), 200

    except Exception as e:
        tb = traceback.format_exc()
        return jsonify(
            {
                "message": "Error al obtener el listado de actividades",
                "error": str(e),
                "trace": tb,
            }
        ), 500


# Todas las actividades de UN evento (portal estudiante)
# ─────────────────────────────────────────────────────────────────────────────
# GET /api/activities/by-event/<int:event_id>[?for_student=1&exclude_types=A,B&search=]
#
# Devuelve TODAS las actividades de un evento, sin paginar, con los campos
# ricos que la vista del estudiante necesita para agruparlas por día y
# mostrar la ocupación: duración, aforo máximo y `current_capacity`.
#
# Existe porque esa vista necesita el conjunto COMPLETO de un solo evento (el
# más grande hoy tiene 66 actividades) y `max_per_page=100` en el listado
# genérico habría truncado el resultado en silencio. Al limitar por event_id
# la carga queda acotada de por sí, así que no hace falta paginar.
#
# Contrato: { activities: [Activity.to_dict() + {event, current_capacity}],
#             total, event: {id, name} }
@activities_bp.route("/by-event/<int:event_id>", methods=["GET"])
def activities_by_event(event_id):
    try:
        from sqlalchemy.orm import joinedload

        for_student = request.args.get("for_student", default=None)
        exclude_types = request.args.get("exclude_types")
        activity_type = request.args.get("activity_type")
        sort = request.args.get("sort")
        search = (request.args.get("search") or "").strip()

        # db.session.get en vez de Event.query.get: esta última es legacy en
        # SQLAlchemy 2.0 y emite LegacyAPIWarning (que el entorno de test
        # convierte en error).
        event = db.session.get(Event, event_id)
        if event is None:
            return jsonify({"message": "Evento no encontrado"}), 404

        query = Activity.query.options(joinedload(Activity.event)).filter(
            Activity.event_id == event_id
        )

        # Mismas reglas que el listado genérico: los estudiantes no ven
        # las "Magistrales".
        if for_student is not None and str(for_student).lower() in ("1", "true", "yes"):
            query = query.filter(~Activity.activity_type.in_(["Magistral"]))

        if exclude_types:
            types_list = [t.strip() for t in exclude_types.split(",") if t.strip()]
            if types_list:
                query = query.filter(~Activity.activity_type.in_(types_list))

        if search:
            search_filter = f"%{search}%"
            query = query.filter(
                db.or_(
                    Activity.name.ilike(search_filter),
                    Activity.department.ilike(search_filter),
                )
            )

        if activity_type:
            query = query.filter(Activity.activity_type == activity_type)

        # Ordenamiento opcional: name:asc|name:desc. Por defecto, cronológico
        # (la vista del estudiante agrupa por día, así que el orden importa).
        if sort and ":" in sort:
            key, direction = sort.split(":", 1)
            key = key.strip()
            direction = direction.strip().lower()
            if key == "name":
                query = query.order_by(
                    Activity.name.desc()
                    if direction == "desc"
                    else Activity.name.asc(),
                    Activity.start_datetime.asc(),
                )
            else:
                query = query.order_by(
                    Activity.start_datetime.asc(), Activity.name.asc()
                )
        else:
            query = query.order_by(Activity.start_datetime.asc(), Activity.name.asc())

        rows = query.all()

        # Conteo de preregistros vigentes por actividad en UNA sola consulta
        # (evita el N+1 que supondría preguntar actividad por actividad).
        activity_ids = [a.id for a in rows]
        counts = {}
        if activity_ids:
            count_rows = (
                db.session.query(
                    Registration.activity_id, db.func.count(Registration.id)
                )
                .filter(
                    Registration.activity_id.in_(activity_ids),
                    ~Registration.status.in_(["Ausente", "Cancelado"]),
                )
                .group_by(Registration.activity_id)
                .all()
            )
            counts = {r[0]: int(r[1]) for r in count_rows}

        activities = []
        for a in rows:
            item = a.to_dict()
            ev = getattr(a, "event", None)
            item["event"] = (
                {"id": getattr(ev, "id", None), "name": getattr(ev, "name", None)}
                if ev is not None
                else None
            )
            val = counts.get(a.id, 0)
            # `current_capacity` es el que usa el portal; el alias histórico
            # se mantiene por compatibilidad con vistas antiguas.
            item["current_capacity"] = val
            item["current_registrations"] = val
            activities.append(item)

        return jsonify(
            {
                "activities": activities,
                "total": len(activities),
                "event": {"id": event.id, "name": event.name},
            }
        ), 200

    except Exception as e:
        tb = traceback.format_exc()
        return jsonify(
            {
                "message": "Error al obtener las actividades del evento",
                "error": str(e),
                "trace": tb,
            }
        ), 500


# Crear actividad


@activities_bp.route("/", methods=["POST"])
@jwt_required()
@require_admin
def create_activity():
    try:
        # Normalizar payload y validar datos de entrada
        payload = request.get_json() or {}

        data = activity_schema.load(payload)

        # Accept optional manual public_slug from payload; normalize it
        if "public_slug" in payload and payload.get("public_slug"):
            try:
                data["public_slug"] = slugify(str(payload.get("public_slug")))
            except Exception:
                data["public_slug"] = None

        if "start_datetime" in data:
            data["start_datetime"] = parse_datetime_with_timezone(
                data["start_datetime"]
            )
        if "end_datetime" in data:
            data["end_datetime"] = parse_datetime_with_timezone(data["end_datetime"])

        # Verificar que el evento exista
        event = db.session.get(Event, data["event_id"])
        if not event:
            return jsonify({"message": "Evento no encontrado"}), 404

        # Crear actividad
        activity = activity_service.create_activity(data)

        act = activity_schema.dump(activity)
        if isinstance(act, dict) and act.get("public_slug"):
            act["public_url"] = (
                request.host_url.rstrip("/")
                + "/public/registrations/"
                + act["public_slug"]
            )
        return jsonify(
            {"message": "Actividad creada exitosamente", "activity": act}
        ), 201

    except ValidationError as err:
        return jsonify({"message": "Error de validación", "errors": err.messages}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Error al crear actividad", "error": str(e)}), 400


# Obtener actividad por ID


@activities_bp.route("/<int:activity_id>", methods=["GET"])
def get_activity(activity_id):
    try:
        activity = db.session.get(Activity, activity_id)
        if not activity:
            return jsonify({"message": "Actividad no encontrada"}), 404

        dumped = activity_schema.dump(activity)
        # Añadir conteo real de preregistros (excluyendo 'Ausente' y 'Cancelado')
        try:
            count = (
                db.session.query(db.func.count(Registration.id))
                .filter(
                    Registration.activity_id == activity_id,
                    ~Registration.status.in_(["Ausente", "Cancelado"]),
                )
                .scalar()
                or 0
            )
            if isinstance(dumped, dict):
                dumped["current_capacity"] = int(count)
                dumped["current_registrations"] = int(count)
        except Exception:
            # Si hay cualquier error al calcular el conteo, mantener comportamiento previo
            if isinstance(dumped, dict):
                try:
                    dumped["current_registrations"] = dumped.get("current_capacity", 0)
                except Exception:
                    pass

        # Añadir public_url si corresponde en la representación individual
        if isinstance(dumped, dict) and dumped.get("public_slug"):
            dumped["public_url"] = (
                request.host_url.rstrip("/")
                + "/public/registrations/"
                + dumped["public_slug"]
            )
        return jsonify({"activity": dumped}), 200

    except Exception as e:
        return jsonify({"message": "Error al obtener actividad", "error": str(e)}), 500


# Actualizar actividad


@activities_bp.route("/<int:activity_id>", methods=["PUT"])
@jwt_required()
@require_admin
def update_activity(activity_id):
    try:
        activity = db.session.get(Activity, activity_id)
        if not activity:
            return jsonify({"message": "Actividad no encontrada"}), 404

        # Validar datos de entrada
        payload = request.get_json() or {}

        data = activity_schema.load(payload, partial=True)

        # Normalize public_slug if provided
        if "public_slug" in payload and payload.get("public_slug"):
            try:
                data["public_slug"] = slugify(str(payload.get("public_slug")))
            except Exception:
                data["public_slug"] = None

        # Parsear fechas con zona horaria si se proporcionan
        if "start_datetime" in data:
            data["start_datetime"] = parse_datetime_with_timezone(
                data["start_datetime"]
            )
        if "end_datetime" in data:
            data["end_datetime"] = parse_datetime_with_timezone(data["end_datetime"])

        activity = activity_service.update_activity(activity_id, data)

        act = activity_schema.dump(activity)
        if isinstance(act, dict) and act.get("public_slug"):
            act["public_url"] = (
                request.host_url.rstrip("/")
                + "/public/registrations/"
                + act["public_slug"]
            )
        return jsonify(
            {"message": "Actividad actualizada exitosamente", "activity": act}
        ), 200

    except ValidationError as err:
        return jsonify({"message": "Error de validación", "errors": err.messages}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify(
            {"message": "Error al actualizar actividad", "error": str(e)}
        ), 400


@activities_bp.route("/generate-slug", methods=["POST"])
@jwt_required()
@require_admin
def api_generate_slug():
    """Generate a unique slug for a given name server-side.

    Body: { name: <string>, maxlen: <int, optional> }
    Returns: { slug: <unique-slug> }
    """
    try:
        payload = request.get_json() or {}
        name = payload.get("name") or ""
        maxlen = int(payload.get("maxlen") or 200)
        if not name:
            return jsonify({"message": "Name required"}), 400
        slug = generate_unique_slug(
            db.session, Activity, name, column="public_slug", maxlen=maxlen
        )
        return jsonify({"slug": slug}), 200
    except Exception as e:
        return jsonify({"message": "Error generando slug", "error": str(e)}), 500


# Eliminar actividad


@activities_bp.route("/<int:activity_id>", methods=["DELETE"])
@jwt_required()
@require_admin
def delete_activity(activity_id):
    try:
        activity = db.session.get(Activity, activity_id)
        if not activity:
            return jsonify({"message": "Actividad no encontrada"}), 404

        db.session.delete(activity)
        db.session.commit()

        return jsonify({"message": "Actividad eliminada exitosamente"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Error al eliminar actividad", "error": str(e)}), 500


@activities_bp.route("/<int:activity_id>/related", methods=["GET"])
@jwt_required()
@require_admin
def get_related_activities(activity_id):
    """Devuelve las actividades relacionadas con una actividad."""
    activity = db.session.get(Activity, activity_id)
    if not activity:
        return jsonify({"message": "Actividad no encontrada"}), 404
    return jsonify(
        {
            "related_activities": _safe_dump_activities(
                list(cast(Iterable, activity.related_activities))
            )
        }
    ), 200


@activities_bp.route("/<int:activity_id>/token", methods=["GET"])
@jwt_required()
@require_admin
def get_activity_token(activity_id):
    """Devuelve un token stateless para la actividad y la URL de registro basada en token.

    Este endpoint está protegido (admin) y sirve para generar enlaces/QRs operativos.
    """
    # Token generation for public self-register was deprecated.
    # Keep the endpoint to provide a clear error rather than raising an unexpected exception.
    activity = db.session.get(Activity, activity_id)
    if not activity:
        return jsonify({"message": "Actividad no encontrada"}), 404
    return (
        jsonify(
            {
                "message": "Generación de tokens deshabilitada: use slugs públicos o IDs para enlaces.",
            }
        ),
        410,
    )


@activities_bp.route("/<int:activity_id>/public-token", methods=["GET"])
@jwt_required()
@require_admin
def get_public_activity_token(activity_id):
    """Devuelve un token público (para jefes) distinto del token de autorregistro."""
    activity = db.session.get(Activity, activity_id)
    if not activity:
        return jsonify({"message": "Actividad no encontrada"}), 404
    return (
        jsonify(
            {
                "message": "Generación de tokens públicos deshabilitada: use slugs públicos o IDs para enlaces de jefes.",
            }
        ),
        410,
    )


@activities_bp.route("/<int:activity_id>/related", methods=["POST"])
@jwt_required()
@require_admin
def add_related_activity(activity_id):
    """Enlaza una actividad con otra, manejando errores de concurrencia."""
    import pymysql

    data = request.get_json()
    related_id = data.get("related_activity_id")
    if not related_id:
        return jsonify({"message": "Falta el ID de la actividad a enlazar"}), 400
    if activity_id == related_id:
        return jsonify(
            {"message": "No se puede enlazar una actividad consigo misma"}
        ), 400
    activity = db.session.get(Activity, activity_id)
    related = db.session.get(Activity, related_id)
    if not activity or not related:
        return jsonify({"message": "Una o ambas actividades no existen"}), 404
    # Solo permitir enlazar actividades del mismo evento
    if activity.event_id != related.event_id:
        return jsonify(
            {"message": "Solo se pueden enlazar actividades del mismo evento."}
        ), 400
    # Enforce single outgoing link: una actividad sólo puede enlazarse a UNA otra
    existing_outgoing = list(cast(Iterable, activity.related_activities))
    if existing_outgoing and len(existing_outgoing) > 0:
        # If the existing link is exactly the same as requested, return a duplicate message
        if related in existing_outgoing:
            return jsonify({"message": "Las actividades ya están enlazadas"}), 400
        return jsonify(
            {
                "message": "Esta actividad ya está enlazada a otra. Quita el enlace existente antes de añadir uno nuevo."
            }
        ), 400
    if related in existing_outgoing:
        return jsonify({"message": "Las actividades ya están enlazadas"}), 400
    try:
        # Protección extra: evitar crear ciclos en la grafo de relaciones.
        # Si a partir de `related` se puede alcanzar `activity`, crear el enlace
        # produciría un ciclo (por ejemplo: A <- ... <- related -> A). Rechazar.
        def _creates_cycle(start_id, target_id):
            # DFS desde start_id buscando target_id
            seen = set()
            stack = [start_id]
            while stack:
                cur = stack.pop()
                if cur in seen:
                    continue
                seen.add(cur)
                if cur == target_id:
                    return True
                node = db.session.get(Activity, cur)
                if not node:
                    continue
                try:
                    for r in getattr(node, "related_activities", []) or []:
                        rid = getattr(r, "id", None)
                        if rid and rid not in seen:
                            stack.append(rid)
                except Exception:
                    # Si hay algún problema al navegar relaciones, no asumir ciclo
                    continue

        if _creates_cycle(related.id, activity.id):
            return jsonify(
                {
                    "message": "Enlazar crearía un ciclo de relaciones; operación rechazada."
                }
            ), 400

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
                return jsonify(
                    {"message": "Actividades enlazadas exitosamente (reintento)"}
                ), 200
            except Exception as e2:
                db.session.rollback()
                return jsonify(
                    {
                        "message": f"Error de concurrencia al enlazar actividades: {str(e2)}"
                    }
                ), 500
        else:
            db.session.rollback()
            return jsonify({"message": f"Error al enlazar actividades: {str(e)}"}), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error al enlazar actividades: {str(e)}"}), 500
    return jsonify({"message": "Actividades enlazadas exitosamente"}), 200


@activities_bp.route("/<int:activity_id>/related/<int:related_id>", methods=["DELETE"])
@jwt_required()
@require_admin
def remove_related_activity(activity_id, related_id):
    """Desenlaza dos actividades."""
    activity = db.session.get(Activity, activity_id)
    related = db.session.get(Activity, related_id)
    if not activity or not related:
        return jsonify({"message": "Una o ambas actividades no existen"}), 404
    if related not in list(cast(Iterable, activity.related_activities)):
        return jsonify({"message": "Las actividades no están enlazadas"}), 400
    activity.related_activities.remove(related)
    db.session.commit()
    return jsonify({"message": "Actividades desenlazadas exitosamente"}), 200


@activities_bp.route("/relations", methods=["GET"])
def get_activity_relations():
    try:
        activities = Activity.query.all()
        result = []
        for activity in activities:
            related_list = list(cast(Iterable, activity.related_activities))
            linked_by_list = list(
                cast(Iterable, getattr(activity, "related_to_activities", []))
            )
            result.append(
                {
                    "id": activity.id,
                    "name": activity.name,
                    "event_id": activity.event_id,
                    "related_activities": [
                        {"id": a.id, "name": a.name, "event_id": a.event_id}
                        for a in related_list
                    ],
                    "linked_by": [
                        {"id": a.id, "name": a.name, "event_id": a.event_id}
                        for a in linked_by_list
                    ],
                }
            )
        return jsonify({"activities": result}), 200
    except Exception as e:
        return jsonify({"message": "Error al obtener relaciones", "error": str(e)}), 500


@activities_bp.route("/batch", methods=["POST"])
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
        if "file" not in request.files:
            return jsonify({"message": "Falta el archivo."}), 400

        file = request.files["file"]
        event_id = request.form.get("event_id")
        dry_run = request.form.get("dry_run", "1")
        dry = str(dry_run).strip() in ("1", "true", "yes")

        # Call service
        report = activity_service.create_activities_from_xlsx(
            file.stream, event_id=event_id, dry_run=dry
        )

        status_code = 200 if dry else 201
        return jsonify({"message": "Batch processed", "report": report}), status_code

    except Exception as e:
        tb = traceback.format_exc()
        return jsonify(
            {"message": "Error en importación batch", "error": str(e), "trace": tb}
        ), 500


@activities_bp.route("/batch-template", methods=["GET"])
def download_batch_template():
    """Descarga una plantilla XLSX con la estructura esperada por POST /batch.

    Sin autenticación a propósito: solo expone encabezados, límites y filas de
    ejemplo (sin datos reales) para que el enlace <a download> del modal
    "Importar XLSX" funcione sin cabecera Authorization.
    """
    try:
        buf = activity_service.build_activities_xlsx_template()
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="plantilla_actividades.xlsx",
        )
    except Exception as e:
        return jsonify(
            {"message": "Error generando la plantilla", "error": str(e)}
        ), 500
