from marshmallow import Schema, fields, validate, validates_schema, ValidationError
from app import ma
from app.models.activity import Activity


class ActivitySchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Activity
        load_instance = True
        include_fk = True

    # Validaciones
    event_id = fields.Int(required=True)
    department = fields.Str(
        required=True, validate=validate.Length(min=1, max=50))
    # Solo lectura, se genera automáticamente
    code = fields.Str(dump_only=True)
    name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    description = fields.Str(missing=None)
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
    requirements = fields.Str(missing=None)
    max_capacity = fields.Int(missing=None, validate=validate.Range(min=0))

    # Campos de solo lectura
    id = fields.Int(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    @validates_schema
    def validate_dates(self, data, **kwargs):
        if 'start_datetime' in data and 'end_datetime' in data:
            if data['start_datetime'] > data['end_datetime']:
                raise ValidationError(
                    'La fecha de inicio debe ser anterior a la fecha de fin.')


activity_schema = ActivitySchema()
activities_schema = ActivitySchema(many=True)
