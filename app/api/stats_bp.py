# app/api/stats_bp.py
from flask import Blueprint, jsonify
from app import db
from app.models.event import Event
from app.models.activity import Activity
from app.models.attendance import Attendance
from datetime import datetime


stats_bp = Blueprint('stats', __name__, url_prefix='/api/stats')


@stats_bp.route('/', methods=['GET'])
def get_general_stats():
    """Devuelve estadísticas generales del sistema."""
    # Aquí podrías hacer consultas a la base de datos
    # Por ahora devolvemos datos simulados
    stats_data = {
        'total_students': db.session.query(Attendance).distinct(Attendance.student_id).count(),
        'active_events': db.session.query(Event).filter_by(is_active=True).count(),
        'total_activities': db.session.query(Activity).count(),
        'today_attendances': db.session.query(Attendance).filter_by(date=datetime.today()).count()
    }

    return jsonify(stats_data), 200
