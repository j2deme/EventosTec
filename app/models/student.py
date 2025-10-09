from app import db
from datetime import datetime


class Student(db.Model):
    __tablename__ = 'students'

    id = db.Column(db.Integer, primary_key=True)
    control_number = db.Column(
        db.String(20), unique=True, nullable=False)  # Número de control
    full_name = db.Column(db.String(100), nullable=False)
    career = db.Column(db.String(100))
    email = db.Column(db.String(100))
    created_at = db.Column(
        db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(
    ), onupdate=db.func.now(), nullable=False)

    # Relaciones
    attendances = db.relationship('Attendance', backref='student', lazy=True)
    registrations = db.relationship(
        'Registration', backref='student', lazy=True)

    def __repr__(self):
        return f'<Student {self.control_number}>'

    def to_dict(self):
        from app.utils.datetime_utils import safe_iso

        return {
            'id': self.id,
            'control_number': self.control_number,
            'full_name': self.full_name,
            'career': self.career,
            'email': self.email,
            'created_at': safe_iso(self.created_at),
            'updated_at': safe_iso(self.updated_at)
        }
