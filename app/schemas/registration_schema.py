from marshmallow import fields, validate
from app import ma
from app.models.registration import Registration


class RegistrationSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Registration
        load_instance = False
        include_fk = True

    # Validaciones
    student_id = fields.Int(required=True)
    activity_id = fields.Int(required=True)
    status = fields.Str(load_default='Registrado', validate=validate.OneOf([
        'Registrado', 'Confirmado', 'Asistió', 'Ausente', 'Cancelado'
    ]))
    attended = fields.Bool(load_default=False)

    # Campos de solo lectura
    id = fields.Int(dump_only=True)
    registration_date = fields.DateTime(dump_only=True)
    confirmation_date = fields.DateTime(load_default=None)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


registration_schema = RegistrationSchema()
registrations_schema = RegistrationSchema(many=True)
