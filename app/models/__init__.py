from app.models.event import Event
from app.models.activity import Activity
from app.models.student import Student
from app.models.user import User  # NUEVO
from app.models.attendance import Attendance
from app.models.registration import Registration

# Tabla de relación muchos a muchos para actividades relacionadas
from app import db

activity_relations = db.Table('activity_relations',
                              db.Column('activity_id', db.Integer, db.ForeignKey(
                                  'activities.id'), primary_key=True),
                              db.Column('related_activity_id', db.Integer,
                                        db.ForeignKey('activities.id'), primary_key=True)
                              )

__all__ = [
    'Event', 'Activity', 'Student', 'User', 'Attendance', 'Registration', 'activity_relations'
]
