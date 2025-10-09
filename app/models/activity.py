from app import db
from datetime import datetime
from sqlalchemy import event
from sqlalchemy.orm import object_session


class Activity(db.Model):
    __tablename__ = 'activities'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey(
        'events.id'), nullable=False)
    department = db.Column(db.String(50), nullable=False)
    code = db.Column(db.String(50))  # Código autogenerado: SIGLAS/NN
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    start_datetime = db.Column(db.DateTime, nullable=False)
    end_datetime = db.Column(db.DateTime, nullable=False)
    duration_hours = db.Column(db.Float, nullable=False)  # Duración en horas
    activity_type = db.Column(db.Enum(
        'Magistral', 'Conferencia', 'Taller', 'Curso', 'Otro'), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    modality = db.Column(
        db.Enum('Presencial', 'Virtual', 'Híbrido'), nullable=False)
    requirements = db.Column(db.Text)  # Requisitos especiales
    max_capacity = db.Column(db.Integer)
    created_at = db.Column(
        db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(
    ), onupdate=db.func.now(), nullable=False)

    # Relaciones
    attendances = db.relationship(
        'Attendance', backref='activity', lazy=True, cascade='all, delete-orphan')
    registrations = db.relationship(
        'Registration', backref='activity', lazy=True, cascade='all, delete-orphan')

    # Para actividades relacionadas (magistrales en cadena)
    related_activities = db.relationship(
        'Activity',
        secondary='activity_relations',
        primaryjoin='Activity.id==activity_relations.c.activity_id',
        secondaryjoin='Activity.id==activity_relations.c.related_activity_id',
        backref='related_to_activities'
    )

    def __repr__(self):
        return f'<Activity {self.name}>'

    def to_dict(self):
        from app.utils.datetime_utils import safe_iso

        out = {
            'id': self.id,
            'event_id': self.event_id,
            'code': self.code,
            'department': self.department,
            'name': self.name,
            'description': self.description,
            'start_datetime': safe_iso(self.start_datetime),
            'end_datetime': safe_iso(self.end_datetime),
            'duration_hours': self.duration_hours,
            'activity_type': self.activity_type,
            'location': self.location,
            'modality': self.modality,
            'requirements': self.requirements,
            'max_capacity': self.max_capacity,
            'created_at': safe_iso(self.created_at),
            'updated_at': safe_iso(self.updated_at)
        }

        # Parse speakers and target_audience if stored as JSON text
        try:
            out['speakers'] = None
            if self.speakers:
                import json as _json
                try:
                    out['speakers'] = _json.loads(self.speakers)
                except Exception:
                    out['speakers'] = self.speakers
        except Exception:
            out['speakers'] = None

        try:
            out['target_audience'] = None
            if self.target_audience:
                import json as _json
                try:
                    out['target_audience'] = _json.loads(self.target_audience)
                except Exception:
                    out['target_audience'] = self.target_audience
        except Exception:
            out['target_audience'] = None

        out['knowledge_area'] = self.knowledge_area

        return out

    # Nuevos campos: ponentes (JSON), público objetivo (JSON) y área de conocimiento
    # JSON array: [{name, degree, organization}, ...]
    speakers = db.Column(db.Text)
    # JSON object: {general: bool, careers: [..]}
    target_audience = db.Column(db.Text)
    knowledge_area = db.Column(db.String(100), nullable=True)


# Generar el código automáticamente antes de insertar
@event.listens_for(Activity, 'before_insert')
def generate_activity_code(mapper, connection, target):
    if not target.department:
        raise ValueError(
            "El departamento es obligatorio para generar el código.")

    # Buscar el último número asignado en el código para el departamento y evento
    last_code = connection.execute(
        db.select(Activity.code)
        .where(Activity.event_id == target.event_id)
        .where(Activity.department == target.department)
        .where(Activity.code != None)
        .order_by(Activity.id.desc())
        .limit(1)
    ).scalar()

    if last_code and '/' in last_code:
        try:
            last_number = int(last_code.split('/')[-1])
        except ValueError:
            last_number = 0
    else:
        last_number = 0

    next_number = last_number + 1
    target.code = f"{target.department}/{next_number:02}"
