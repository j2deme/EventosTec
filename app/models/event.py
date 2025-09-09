from sqlalchemy import func
from app import db
from datetime import datetime


class Event(db.Model):
    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(
    ), onupdate=db.func.now(), nullable=False)

    # Relaciones
    activities = db.relationship(
        'Activity', backref='event', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Event {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    @classmethod
    def get_stats(cls, event_id):
        """Obtiene estadísticas optimizadas para un evento."""
        from app.models.activity import Activity
        from app.models.registration import Registration
        from app.models.attendance import Attendance
        from app.models.student import Student

        # Usar subconsultas para mejor rendimiento
        total_activities = db.session.query(func.count(Activity.id)).filter(
            Activity.event_id == event_id
        ).scalar() or 0

        total_registrations = db.session.query(func.count(Registration.id)).filter(
            Registration.activity_id.in_(
                db.session.query(Activity.id).filter(
                    Activity.event_id == event_id)
            )
        ).scalar() or 0

        total_attendances = db.session.query(func.count(Attendance.id)).filter(
            Attendance.activity_id.in_(
                db.session.query(Activity.id).filter(
                    Activity.event_id == event_id)
            ),
            Attendance.status == 'Asistió'
        ).scalar() or 0

        total_students = db.session.query(func.count(func.distinct(Student.id))).filter(
            Student.id.in_(
                db.session.query(Registration.student_id).filter(
                    Registration.activity_id.in_(
                        db.session.query(Activity.id).filter(
                            Activity.event_id == event_id)
                    )
                )
            )
        ).scalar() or db.session.query(Student).count()

        return {
            'total_activities': total_activities,
            'total_registrations': total_registrations,
            'total_attendances': total_attendances,
            'total_students': total_students
        }
