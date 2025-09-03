from marshmallow import fields, validate
from app import ma
from app.models.registration import Registration


class RegistrationSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Registration
        load_instance = True
        include_fk = True

    # Validaciones
    student_id = fields.Int(required=True)
    activity_id = fields.Int(required=True)
    status = fields.Str(missing='registered', validate=validate.OneOf([
        'registered', 'confirmed', 'attended', 'absent', 'cancelled'
    ]))
    attended = fields.Bool(missing=False)

    # Campos de solo lectura
    id = fields.Int(dump_only=True)
    registration_date = fields.DateTime(dump_only=True)
    confirmation_date = fields.DateTime(missing=None)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


registration_schema = RegistrationSchema()
registrations_schema = RegistrationSchema(many=True)
