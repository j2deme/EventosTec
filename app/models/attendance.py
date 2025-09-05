from app import db
from datetime import datetime


class Attendance(db.Model):
    __tablename__ = 'attendances'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey(
        'students.id'), nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey(
        'activities.id'), nullable=False)

    # Solo lo necesario para conferencias magistrales
    check_in_time = db.Column(db.DateTime)
    check_out_time = db.Column(db.DateTime, nullable=True)
    is_paused = db.Column(db.Boolean, default=False)
    pause_time = db.Column(db.DateTime, nullable=True)
    resume_time = db.Column(db.DateTime, nullable=True)

    # Campos calculados
    attendance_percentage = db.Column(db.Float, default=0.0)
    status = db.Column(db.Enum('Asistió', 'Parcial',
                       'Ausente'), default='Ausente')
    created_at = db.Column(
        db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(
    ), onupdate=db.func.now(), nullable=False)

    # Índice compuesto
    __table_args__ = (db.UniqueConstraint(
        'student_id', 'activity_id', name='unique_student_activity'),)

    def __repr__(self):
        return f'<Attendance Student:{self.student_id} Activity:{self.activity_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'activity_id': self.activity_id,
            'check_in_time': self.check_in_time.isoformat() if self.check_in_time else None,
            'check_out_time': self.check_out_time.isoformat() if self.check_out_time else None,
            'is_paused': self.is_paused,
            'pause_time': self.pause_time.isoformat() if self.pause_time else None,
            'resume_time': self.resume_time.isoformat() if self.resume_time else None,
            'attendance_percentage': self.attendance_percentage,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
