from flask import Blueprint, render_template
from app.utils.token_utils import verify_public_event_token
from app import db
from app.models.event import Event
from app.models.activity import Activity
from app.utils.token_utils import generate_activity_token, generate_public_token
from flask import request, jsonify

public_event_bp = Blueprint('public_event', __name__, url_prefix='')


@public_event_bp.route('/public/event-registrations/<token>', methods=['GET'])
def public_event_view(token):
    eid, err = verify_public_event_token(token)
    if err or eid is None:
        return render_template('public/event_registrations_public.html', token_provided=True, token_invalid=True)

    event = db.session.get(Event, int(eid))
    if not event:
        return render_template('public/event_registrations_public.html', token_provided=True, token_invalid=True)

    # Build context: event name, id, token
    return render_template('public/event_registrations_public.html', event_token=token, event_name=event.name, event_id=event.id)


@public_event_bp.route('/api/public/event/<token>/activity-token', methods=['POST'])
def api_public_event_activity_token(token):
    """Given an event public token and activity_id in body, return a public activity token.

    POST body: { activity_id }
    Response: { public_token }
    """
    # Accept either a public event token (pe:...) or a plain numeric event id
    eid = None
    err = None
    try:
        # if token looks like an integer id, accept it as event id
        if str(token).isdigit():
            eid = int(token)
        else:
            eid, err = verify_public_event_token(token)
    except Exception:
        eid = None

    if err or eid is None:
        return jsonify({'message': 'Token de evento inválido'}), 400

    payload = request.get_json(silent=True) or {}
    activity_id = payload.get('activity_id')
    if not activity_id:
        return jsonify({'message': 'activity_id es requerido'}), 400

    activity = db.session.get(Activity, int(activity_id))
    if not activity or activity.event_id != int(eid):
        return jsonify({'message': 'Actividad no pertenece al evento o no existe'}), 404

    # generate public activity token (p:...)
    public_act_token = generate_public_token(activity.id)
    return jsonify({'public_token': public_act_token}), 200
