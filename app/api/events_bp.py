from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from datetime import timedelta
from app import db
from app.schemas import event_schema, events_schema
from app.models.event import Event
from app.models.activity import Activity
from app.models.registration import Registration
from app.utils.auth_helpers import require_admin
from app.services.registration_service import _get_daily_sessions
from sqlalchemy import asc, desc, or_
from app.utils.slug_utils import generate_unique_slug, slugify as canonical_slugify

events_bp = Blueprint("events", __name__, url_prefix="/api/events")

# Listar eventos


@events_bp.route("/", methods=["GET"])
def get_events():
    try:
        # Parámetros de paginación y filtrado
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 10, type=int)
        status = request.args.get("status")
        search = request.args.get("search", "").strip()
        sort = request.args.get("sort", "start_date:desc")

        # Use the model's query attribute so .paginate() is recognized by the analyzer
        query = Event.query

        if search:
            query = query.filter(
                or_(
                    Event.name.ilike(f"%{search}%"),
                    Event.description.ilike(f"%{search}%"),
                )
            )

        if status:
            is_active = status.lower() == "active"
            query = query.filter_by(is_active=is_active)

        # Aplicar ordenamiento
        sort_field, sort_order = "created_at", "desc"  # Valores por defecto
        if sort and ":" in sort:
            parts = sort.split(":")
            if len(parts) == 2:
                sort_field, sort_order = parts
                # Validar que el campo de ordenamiento sea seguro
                if sort_field not in [
                    "id",
                    "name",
                    "start_date",
                    "end_date",
                    "created_at",
                ]:
                    sort_field = "created_at"
                if sort_order not in ["asc", "desc"]:
                    sort_order = "desc"

        # Aplicar ordenamiento
        if sort_order == "asc":
            query = query.order_by(asc(getattr(Event, sort_field)))
        else:
            query = query.order_by(desc(getattr(Event, sort_field)))

        events = query.paginate(page=page, per_page=per_page, error_out=False)

        total = events.total or 0
        items = events_schema.dump(events.items)
        # Add public_url for items that have public_slug
        for ev in items:
            if isinstance(ev, dict) and ev.get("public_slug"):
                ev["public_url"] = (
                    request.host_url.rstrip("/") + "/public/event/" + ev["public_slug"]
                )

        return jsonify(
            {
                "events": items,
                "total": total,
                "pages": events.pages,
                "current_page": page,
                "from": (page - 1) * per_page + 1 if total > 0 else 0,
                "to": min(page * per_page, total),
            }
        ), 200

    except Exception as e:
        return jsonify({"message": "Error al obtener eventos", "error": str(e)}), 500


# Crear evento


@events_bp.route("/", methods=["POST"])
@jwt_required()
@require_admin
def create_event():
    try:
        # Validar datos de entrada
        data = event_schema.load(request.get_json() or {})

        # Crear evento (asignaciones explícitas en lugar de kwargs para ayudar al analizador)
        event = Event()
        for key, value in data.items():
            setattr(event, key, value)
        # Ensure a public_slug is generated when creating an event if not provided
        try:
            if not getattr(event, "public_slug", None):
                # Use the name to generate a unique slug; fallback to id-based later
                name_val = getattr(event, "name", "") or ""
                if name_val:
                    event.public_slug = generate_unique_slug(
                        db.session, Event, name_val, column="public_slug"
                    )
        except Exception:
            # swallow slug generation issues; event can still be created
            pass
        db.session.add(event)
        db.session.commit()

        ev = event_schema.dump(event)
        if isinstance(ev, dict) and ev.get("public_slug"):
            ev["public_url"] = (
                request.host_url.rstrip("/") + "/public/event/" + ev["public_slug"]
            )
        return jsonify({"message": "Evento creado exitosamente", "event": ev}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Error al crear evento", "error": str(e)}), 400


# Obtener evento por ID


@events_bp.route("/<int:event_id>", methods=["GET"])
def get_event(event_id):
    try:
        event = db.session.get(Event, event_id)
        if not event:
            return jsonify({"message": "Evento no encontrado"}), 404

        # If event lacks a public_slug, generate and persist one so the admin
        # UI can show the public link immediately.
        try:
            if not getattr(event, "public_slug", None):
                if getattr(event, "name", None):
                    event.public_slug = generate_unique_slug(
                        db.session, Event, event.name or "", column="public_slug"
                    )
                    db.session.add(event)
                    db.session.commit()
        except Exception:
            # Don't fail the GET if slug generation fails; just continue.
            try:
                db.session.rollback()
            except Exception:
                pass

        ev = event_schema.dump(event)
        if isinstance(ev, dict) and ev.get("public_slug"):
            ev["public_url"] = (
                request.host_url.rstrip("/") + "/public/event/" + ev["public_slug"]
            )
        return jsonify({"event": ev}), 200

    except Exception as e:
        return jsonify({"message": "Error al obtener evento", "error": str(e)}), 500


# Vista calendario del evento (días definidos + actividades con horario)


@events_bp.route("/<int:event_id>/calendar", methods=["GET"])
@jwt_required()
def get_event_calendar(event_id):
    """Distribución de las actividades del evento por día y horario.

    Contrato (aditivo/backward-compatible, no modifica endpoints existentes):
    {
      "event": {"id", "name", "start_date", "end_date"},  # fechas %Y-%m-%d
      "days": ["2026-10-07", ...],   # días CON actividades (sesiones) dentro
                                      # de la ventana del evento; los días
                                      # vacíos se omiten
      "activities": [ ...to_dict() + day/starts_at/ends_at/registered_count
                      + session_index/session_total ],
                                      # UNA entrada por sesión: las
                                      # actividades multídía generan una
                      # entrada por día (sesión diaria con horario fijo)
      "total_activities": int         # actividades únicas (no sesiones)
    }

    `day`/`starts_at`/`ends_at` se derivan del almacenamiento naive local
    (hora de pared, convención de docs/TIMEZONE_FIX.md): sin conversiones tz.
    Las sesiones usan `_get_daily_sessions` (misma estrategia que la vista
    de estudiantes: una sesión por día con horario fijo entre start y end).
    `registered_count` usa la misma semántica de cupo que
    `is_registration_allowed` (status == "Registrado"), en una sola consulta.
    """
    try:
        event = db.session.get(Event, event_id)
        if not event:
            return jsonify({"message": "Evento no encontrado"}), 404

        # Ventana del evento (fechas locales, sin hora): solo se usará para
        # filtrar qué días con actividades se muestran en el grid
        first_day = event.start_date.date()
        last_day = event.end_date.date()
        if last_day < first_day:
            last_day = first_day
        window_days = set()
        cursor = first_day
        while cursor <= last_day:
            window_days.add(cursor.strftime("%Y-%m-%d"))
            cursor += timedelta(days=1)

        activities = (
            Activity.query.filter_by(event_id=event_id)
            .order_by(Activity.start_datetime.asc())
            .all()
        )

        # Conteos de cupo en una sola consulta agrupada
        counts = {}
        if activities:
            rows = (
                db.session.query(
                    Registration.activity_id, db.func.count(Registration.id)
                )
                .filter(
                    Registration.activity_id.in_([a.id for a in activities]),
                    Registration.status == "Registrado",
                )
                .group_by(Registration.activity_id)
                .all()
            )
            counts = {activity_id: total for activity_id, total in rows}

        items = []
        for activity in activities:
            payload_base = activity.to_dict()
            payload_base["registered_count"] = counts.get(activity.id, 0)

            # Sin fecha de inicio: entrada única sin día (bloque externo)
            if not activity.start_datetime:
                items.append(
                    {
                        **payload_base,
                        "day": None,
                        "starts_at": None,
                        "ends_at": None,
                        "session_index": None,
                        "session_total": None,
                    }
                )
                continue

            # Sesiones: una entrada por día con horario fijo (misma
            # estrategia que la vista de estudiantes). Fallback a entrada
            # única si faltan fechas o si end < start (datos inválidos).
            sessions = []
            if activity.end_datetime:
                sessions = _get_daily_sessions(activity)
            if not sessions:
                sessions = [(activity.start_datetime, activity.end_datetime)]

            session_total = len(sessions)
            for session_index, (session_start, session_end) in enumerate(
                sessions, start=1
            ):
                items.append(
                    {
                        **payload_base,
                        "day": session_start.strftime("%Y-%m-%d"),
                        "starts_at": session_start.strftime("%H:%M"),
                        "ends_at": (
                            session_end.strftime("%H:%M") if session_end else None
                        ),
                        "session_index": session_index,
                        "session_total": session_total,
                    }
                )

        # Días con ≥1 sesión DENTRO de la ventana del evento: solo esos
        # días generan columna en el grid (los vacíos se omiten). Las
        # sesiones fuera de la ventana quedan en el bloque "fuera" del
        # frontend (day no pertenece a days).
        days = sorted(
            {
                item["day"]
                for item in items
                if item["day"] and item["day"] in window_days
            }
        )

        return (
            jsonify(
                {
                    "event": {
                        "id": event.id,
                        "name": event.name,
                        "start_date": event.start_date.strftime("%Y-%m-%d"),
                        "end_date": event.end_date.strftime("%Y-%m-%d"),
                        "is_active": event.is_active,
                    },
                    "days": days,
                    "activities": items,
                    # Actividades únicas (no sesiones: items puede tener
                    # varias entradas por actividad multídía)
                    "total_activities": len(activities),
                }
            ),
            200,
        )

    except Exception as e:
        return (
            jsonify({"message": "Error al construir el calendario", "error": str(e)}),
            500,
        )


@events_bp.route("/<int:event_id>/public-token", methods=["GET"])
@jwt_required()
@require_admin
def get_event_public_token(event_id):
    try:
        event = db.session.get(Event, event_id)
        if not event:
            return jsonify({"message": "Evento no encontrado"}), 404

        from app.utils.token_utils import generate_public_event_token

        token = generate_public_event_token(event.id)
        url = (
            request.host_url.rstrip("/") + "/public/event/" + event.public_slug
            if event.public_slug
            else request.host_url.rstrip("/") + "/public/event/" + str(event.id)
        )

        return jsonify({"token": token, "url": url}), 200
    except Exception as e:
        return jsonify(
            {"message": "Error generando token de evento", "error": str(e)}
        ), 500


@events_bp.route("/<int:event_id>", methods=["PUT"])
@jwt_required()
@require_admin
def update_event(event_id):
    try:
        event = db.session.get(Event, event_id)
        if not event:
            return jsonify({"message": "Evento no encontrado"}), 404
        # Validar datos de entrada
        data = event_schema.load(request.get_json() or {}, partial=True)

        # Preserve previous name to decide whether slug should be regenerated
        old_name = getattr(event, "name", None)

        # Actualizar campos
        for key, value in data.items():
            setattr(event, key, value)

        # If name changed and slug was empty or derived from previous name,
        # regenerate a unique slug so public URL stays consistent with title.
        try:
            if "name" in data:
                new_name = data.get("name") or ""
                current_slug = getattr(event, "public_slug", None)
                # regenerate if slug missing or equals slugified old name
                if (not current_slug) or (
                    old_name and current_slug == canonical_slugify(old_name or "")
                ):
                    if new_name:
                        event.public_slug = generate_unique_slug(
                            db.session, Event, new_name, column="public_slug"
                        )
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass

        db.session.commit()

        ev = event_schema.dump(event)
        if isinstance(ev, dict) and ev.get("public_slug"):
            ev["public_url"] = (
                request.host_url.rstrip("/") + "/public/event/" + ev["public_slug"]
            )
        return jsonify({"message": "Evento actualizado exitosamente", "event": ev}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Error al actualizar evento", "error": str(e)}), 400


# Eliminar evento


@events_bp.route("/<int:event_id>", methods=["DELETE"])
@jwt_required()
@require_admin
def delete_event(event_id):
    try:
        event = db.session.get(Event, event_id)
        if not event:
            return jsonify({"message": "Evento no encontrado"}), 404

        db.session.delete(event)
        db.session.commit()

        return jsonify({"message": "Evento eliminado exitosamente"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Error al eliminar evento", "error": str(e)}), 500


@events_bp.route("/<int:event_id>/departments", methods=["GET"])
def get_event_departments(event_id):
    try:
        event = db.session.get(Event, event_id)
        if not event:
            return jsonify({"message": "Evento no encontrado"}), 404

        # Query distinct departments for the event
        rows = (
            db.session.query(db.distinct(Activity.department))
            .filter(Activity.event_id == event_id)
            .order_by(Activity.department.asc())
            .all()
        )
        departments = [r[0] for r in rows if r and r[0]]
        return jsonify({"departments": departments}), 200
    except Exception as e:
        return jsonify(
            {"message": "Error al obtener departamentos", "error": str(e)}
        ), 500
