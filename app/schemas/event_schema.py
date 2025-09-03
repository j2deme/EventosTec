from marshmallow import Schema, fields, validate
from app import ma
from app.models.event import Event


class EventSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Event
        load_instance = False
        include_fk = True

    # Validaciones
    name = fields.Str(required=True, validate=validate.Length(min=1, max=150))
    description = fields.Str(load_default=None)
    start_date = fields.DateTime(required=True)
    end_date = fields.DateTime(required=True)
    is_active = fields.Bool(load_default=True)

    # Campos de solo lectura
    id = fields.Int(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


# Instancias para usar en los endpoints
event_schema = EventSchema()
events_schema = EventSchema(many=True)
