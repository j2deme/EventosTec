# app/api/stats_bp.py
from flask import Blueprint, jsonify
from app import db
from app.models.event import Event
from app.models.activity import Activity
from app.models.attendance import Attendance
from app.models.student import Student
from app.models.registration import Registration
from datetime import datetime


stats_bp = Blueprint('stats', __name__, url_prefix='/api/stats')


@stats_bp.route('/', methods=['GET'])
def get_general_stats():
    """Devuelve estadísticas generales del sistema."""
    # Get the latest event (by start date or id)
    active_events = Event.query.filter_by(is_active=True).all()

    if len(active_events) == 1:
        stats_data = Event.get_stats(active_events[0].id)
    elif len(active_events) > 1:
        stats_data = {
            'total_activities': 0,
            'total_registrations': 0,
            'total_attendances': 0,
        }
        for event in active_events:
            event_stats = Event.get_stats(event.id)
            for key in stats_data:
                stats_data[key] += event_stats.get(key, 0)
    else:
        stats_data = {
            'total_activities': 0,
            'total_registrations': 0,
            'total_attendances': 0,
        }

    stats_data['active_events'] = Event.query.filter_by(is_active=True).count()

    stats_data['total_students'] = Student.query.count()

    # Agregar estadísticas específicas de registros
    from datetime import timezone as _tz
    today = datetime.now(_tz.utc).date()

    # Asistencias de hoy
    stats_data['today_attendances'] = Attendance.query.filter(
        db.func.date(Attendance.created_at) == today
    ).count()

    return jsonify(stats_data), 200
