from marshmallow import Schema, fields, validate, validates_schema, ValidationError
from app import ma
from app.models.activity import Activity
from app.schemas.event_schema import EventSchema


class ActivitySchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Activity
        load_instance = False
        include_fk = True

    event = fields.Nested(EventSchema, dump_only=True)  # Solo lectura

    # Validaciones
    event_id = fields.Int(required=True)
    department = fields.Str(
        required=True, validate=validate.Length(min=1, max=50))
    # Solo lectura, se genera automáticamente
    code = fields.Str(dump_only=True)
    name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    description = fields.Str(load_default=None)
    start_datetime = fields.DateTime(required=True)
    end_datetime = fields.DateTime(required=True)
    duration_hours = fields.Float(
        required=True, validate=validate.Range(min=0))
    activity_type = fields.Str(required=True, validate=validate.OneOf([
        'Magistral', 'Conferencia', 'Taller', 'Curso', 'Otro'
    ]))
    location = fields.Str(
        required=True, validate=validate.Length(min=1, max=200))
    modality = fields.Str(required=True, validate=validate.OneOf([
        'Presencial', 'Virtual', 'Híbrido'
    ]))
    requirements = fields.Str(load_default=None)
    max_capacity = fields.Int(
        load_default=None, validate=validate.Range(min=0))
    # Nuevos campos
    speakers = fields.List(fields.Dict(), load_default=None)
    # { general: bool, careers: [..] }
    target_audience = fields.Dict(load_default=None)
    knowledge_area = fields.Str(
        load_default=None, validate=validate.Length(max=100))

    # Campos de solo lectura
    id = fields.Int(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    current_capacity = fields.Method(
        "get_current_capacity", dump_only=True)

    def get_current_capacity(self, obj):
        # Assumes 'registrations' is a relationship on Activity model
        if hasattr(obj, 'registrations') and obj.registrations:
            return sum(
                1 for r in obj.registrations
                if getattr(r, 'status', None) not in ['Ausente', 'Cancelado']
            )
        return 0

    @validates_schema
    def validate_dates(self, data, **kwargs):
        start = data.get('start_datetime')
        end = data.get('end_datetime')

        if start and end and start > end:
            raise ValidationError(
                'La fecha de inicio debe ser anterior a la fecha de fin.')

    @validates_schema
    def validate_duration(self, data, **kwargs):
        # No validar durante la deserialización de objetos existentes (carga desde DB)
        if not self.context.get('is_load', False):
            start = data.get('start_datetime')
            end = data.get('end_datetime')
            duration = data.get('duration_hours')

            # Si se proporcionan fechas y duración, validar la coherencia
            if start and end and duration is not None:
                calculated_duration = (end - start).total_seconds() / 3600
                # Validar que la duración proporcionada sea mayor a 0 y menor o igual a la calculada
                if duration <= 0:
                    raise ValidationError(
                        'La duración proporcionada debe ser mayor a 0 horas.'
                    )
                if duration > calculated_duration:
                    raise ValidationError(
                        f'La duración proporcionada ({duration} horas) no puede ser mayor que la calculada a partir de las fechas ({calculated_duration:.2f} horas).'
                    )

            # Si se proporcionan fechas pero no duración, calcularla automáticamente
            elif start and end and duration is None:
                calculated_duration = (end - start).total_seconds() / 3600
                data['duration_hours'] = round(
                    calculated_duration, 2)  # Redondear a 2 decimales

    # Actividades que enlazan a esta actividad (como B)
    linked_by = fields.Method("get_linked_by", dump_only=True)

    def get_linked_by(self, obj):
        # Buscar actividades que tengan a esta como relacionada
        if not hasattr(obj, 'related_to_activities'):
            return []
        return [
            {"id": a.id, "name": a.name, "event_id": a.event_id}
            for a in obj.related_to_activities
        ]


activity_schema = ActivitySchema()
activities_schema = ActivitySchema(many=True)
