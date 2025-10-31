from flask import Blueprint, jsonify
from app import db
from app.models.event import Event
from app.models.activity import Activity
from app.utils.slug_utils import slugify as canonical_slugify
from flask import request

public_event_bp = Blueprint("public_event", __name__, url_prefix="")


@public_event_bp.route("/api/public/event/<event_ref>/activity-slug", methods=["POST"])
def api_public_event_activity_slug(event_ref):
    """Given an event reference (slug or id) and activity_id in body, return the activity slug.

    POST body: { activity_id }
    Response: { activity_slug, event_slug }

    Event reference resolution:
      1. Try Event.public_slug == event_ref (prefer DB lookup)
      2. Try numeric id: Event.id == int(event_ref)
    """
    event = None

    # Slug-first + ID fallback
    try:
        event = Event.query.filter_by(public_slug=event_ref).first()
    except Exception:
        event = None

    if not event:
        try:
            if str(event_ref).isdigit():
                event = db.session.get(Event, int(event_ref))
        except Exception:
            event = None

    if not event:
        return jsonify({"message": "Evento no encontrado"}), 400

    payload = request.get_json(silent=True) or {}
    activity_id = payload.get("activity_id")
    if not activity_id:
        return jsonify({"message": "activity_id es requerido"}), 400

    activity = db.session.get(Activity, int(activity_id))
    if not activity or activity.event_id != event.id:
        return jsonify({"message": "Actividad no pertenece al evento o no existe"}), 404

    # Get activity slug from DB if available, otherwise slugify name
    activity_slug = (
        activity.public_slug
        if activity.public_slug
        else canonical_slugify(activity.name or "")
    )

    # Get event slug from DB if available, otherwise slugify name
    event_slug = (
        event.public_slug if event.public_slug else canonical_slugify(event.name or "")
    )

    return jsonify(
        {
            "activity_slug": activity_slug,
            "event_slug": event_slug,
        }
    ), 200
