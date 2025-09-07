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

    if latest_event and latest_event.is_active:
        # Count values for the current (active) event
        total_students = db.session.query(Student).join(Attendance).join(Activity).filter(
            Activity.event_id == latest_event.id
        ).distinct(Student.id).count()
        total_activities = db.session.query(Activity).filter_by(
            event_id=latest_event.id).count()
        today_attendances = db.session.query(Attendance).join(Activity).filter(
            Activity.event_id == latest_event.id,
            db.func.date(Attendance.created_at) == db.func.current_date()
        ).count()
    elif latest_event:
        # Show values from the last event
        total_students = db.session.query(Student).join(Attendance).join(Activity).filter(
            Activity.event_id == latest_event.id
        ).distinct(Student.id).count()
        total_activities = db.session.query(Activity).filter_by(
            event_id=latest_event.id).count()
        today_attendances = db.session.query(Attendance).join(Activity).filter(
            Activity.event_id == latest_event.id,
            db.func.date(Attendance.created_at) == db.func.current_date()
        ).count()
    else:
        # No events found
        total_students = db.session.query(Student).count()
        total_activities = db.session.query(Activity).join(
            Event).filter(Event.is_active == True).count()
        today_attendances = 0

    stats_data = {
        'total_students': total_students,
        'active_events': db.session.query(Event).filter_by(is_active=True).count(),
        'total_activities': total_activities,
        'today_attendances': today_attendances
    }

    return jsonify(stats_data), 200
