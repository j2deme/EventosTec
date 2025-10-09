from app import db
from datetime import datetime


class Registration(db.Model):
    __tablename__ = 'registrations'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey(
        'students.id'), nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey(
        'activities.id'), nullable=False)
    registration_date = db.Column(
        db.DateTime, server_default=db.func.now(), nullable=False)
    status = db.Column(db.Enum('Registrado', 'Confirmado', 'Asistió', 'Ausente', 'Cancelado'),
                       default='Registrado')
    confirmation_date = db.Column(db.DateTime)
    # Para confirmar asistencia post-evento
    attended = db.Column(db.Boolean, default=False)
    created_at = db.Column(
        db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(
    ), onupdate=db.func.now(), nullable=False)

    # Índice compuesto para evitar registros duplicados
    __table_args__ = (db.UniqueConstraint(
        'student_id', 'activity_id', name='unique_registration'),)

    def __repr__(self):
        return f'<Registration Student:{self.student_id} Activity:{self.activity_id}>'

    def to_dict(self):
        from app.utils.datetime_utils import safe_iso

        return {
            'id': self.id,
            'student_id': self.student_id,
            'activity_id': self.activity_id,
            'registration_date': safe_iso(self.registration_date),
            'status': self.status,
            'confirmation_date': safe_iso(self.confirmation_date),
            'attended': self.attended,
            'created_at': safe_iso(self.created_at),
            'updated_at': safe_iso(self.updated_at)
        }
