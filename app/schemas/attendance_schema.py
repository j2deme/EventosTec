from marshmallow import fields, validate, validates_schema, ValidationError
from app import ma
from app.models.attendance import Attendance


class AttendanceSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Attendance
        load_instance = False
        include_fk = True

    # Validaciones
    student_id = fields.Int(required=True)
    activity_id = fields.Int(required=True)
    check_in_time = fields.DateTime(load_default=None)
    check_out_time = fields.DateTime(load_default=None)
    attendance_percentage = fields.Float(
        load_default=0.0, validate=validate.Range(min=0, max=100))
    status = fields.Str(load_default='Ausente', validate=validate.OneOf([
        'Asistió', 'Parcial', 'Ausente'
    ]))

    # Campos de solo lectura
    id = fields.Int(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    @validates_schema
    def validate_times(self, data, **kwargs):
        if data.get('check_in_time') and data.get('check_out_time'):
            if data['check_in_time'] > data['check_out_time']:
                raise ValidationError(
                    'La hora de entrada debe ser anterior a la hora de salida.')


attendance_schema = AttendanceSchema()
attendances_schema = AttendanceSchema(many=True)
