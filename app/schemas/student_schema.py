from marshmallow import fields, validate
from app import ma
from app.models.student import Student


class StudentSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Student
        load_instance = False

    # Validaciones
    control_number = fields.Str(
        required=True, validate=validate.Length(min=1, max=20))
    full_name = fields.Str(
        required=True, validate=validate.Length(min=1, max=100))
    career = fields.Str(load_default=None, validate=validate.Length(max=100))
    email = fields.Email(load_default=None, validate=validate.Length(max=100))

    # Campos de solo lectura
    id = fields.Int(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


student_schema = StudentSchema()
students_schema = StudentSchema(many=True)
