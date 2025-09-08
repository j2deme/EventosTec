# app/api/stats_bp.py
from flask import Blueprint, jsonify
from app import db
from app.models.event import Event
from app.models.activity import Activity
from app.models.attendance import Attendance
from app.models.student import Student


stats_bp = Blueprint('stats', __name__, url_prefix='/api/stats')


@stats_bp.route('/', methods=['GET'])
def get_general_stats():
    """Devuelve estadísticas generales del sistema."""
    # Get the latest event (by start date or id)
    latest_event = db.session.query(Event).order_by(
        Event.start_date.desc()).first()

    stats_data = Event.get_stats(latest_event.id) if latest_event else {
        'total_activities': 0,
        'total_registrations': 0,
        'total_attendances': 0,
        'total_students': 0
    }

    stats_data['active_events'] = db.session.query(
        Event).filter_by(is_active=True).count()

    return jsonify(stats_data), 200
