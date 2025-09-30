from marshmallow import Schema, fields, validate, validates_schema, ValidationError
from app import ma
from app.models.activity import Activity
from app.schemas.event_schema import EventSchema
import json
from marshmallow import pre_dump
from types import SimpleNamespace
from marshmallow import pre_load


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
        # If a controller/service precomputed 'current_capacity' and attached
        # it to the object/dict (to avoid N+1 queries), prefer that value.
        try:
            pre = getattr(obj, 'current_capacity', None)
            if pre is not None:
                return int(pre)
        except Exception:
            pass

        # Fallback: compute from related registrations (may trigger additional queries)
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

    @pre_dump
    def parse_json_fields(self, obj, **kwargs):
        """
        Asegura que los campos que pueden almacenarse como JSON text
        (`speakers`, `target_audience`) sean estructuras Python antes
        de que Marshmallow intente iterarlas/dump.
        """
        # No mutamos la instancia del modelo (puede romper el session/ORM).
        # En lugar de ello devolvemos un objeto ligero (dict) con los mismos
        # atributos y con los campos JSON parseados. Marshmallow aceptará ese
        # dict para serializarlo.
        try:
            result = SimpleNamespace()
            # Copiar atributos básicos esperados por el schema
            attrs = [
                'id', 'event_id', 'department', 'code', 'name', 'description',
                'start_datetime', 'end_datetime', 'duration_hours', 'activity_type',
                'location', 'modality', 'requirements', 'max_capacity',
                'created_at', 'updated_at', 'knowledge_area'
            ]
            for a in attrs:
                setattr(result, a, getattr(obj, a, None))

            # Event (nested) — intentar copiar si existe
            try:
                ev = getattr(obj, 'event', None)
                if ev is not None:
                    setattr(result, 'event', SimpleNamespace(id=getattr(
                        ev, 'id', None), name=getattr(ev, 'name', None)))
            except Exception:
                pass

            # Parsear speakers sin modificar el modelo
            try:
                sp = getattr(obj, 'speakers', None)
                if sp is None:
                    setattr(result, 'speakers', None)
                elif isinstance(sp, str):
                    try:
                        setattr(result, 'speakers', json.loads(sp))
                    except Exception:
                        setattr(result, 'speakers', [])
                else:
                    setattr(result, 'speakers', sp)
            except Exception:
                setattr(result, 'speakers', None)

            # Parsear target_audience
            try:
                ta = getattr(obj, 'target_audience', None)
                if ta is None:
                    setattr(result, 'target_audience', None)
                elif isinstance(ta, str):
                    try:
                        setattr(result, 'target_audience', json.loads(ta))
                    except Exception:
                        careers = [x.strip()
                                   for x in (ta or '').split(',') if x.strip()]
                        setattr(result, 'target_audience', {
                                'general': False, 'careers': careers})
                else:
                    setattr(result, 'target_audience', ta)
            except Exception:
                setattr(result, 'target_audience', None)

            return result
        except Exception:
            # En caso de cualquier fallo, devolver el objeto original para no romper
            # la serialización; Marshmallow tratará de extraer atributos del modelo.
            return obj

    @pre_load
    def normalize_input(self, data, **kwargs):
        """
        Normaliza entradas que pueden llegar como strings JSON o CSV
        para que el resto del schema y los servicios trabajen con
        estructuras Python (listas/dicts).
        """
        try:
            # speakers: puede venir como JSON-string, CSV o lista
            sp = data.get('speakers')
            if isinstance(sp, str):
                s = sp.strip()
                if s == '':
                    data['speakers'] = None
                else:
                    try:
                        data['speakers'] = json.loads(s)
                    except Exception:
                        if ',' in s:
                            data['speakers'] = [
                                {'name': x.strip()} for x in s.split(',') if x.strip()]
                        else:
                            data['speakers'] = [{'name': s}]

            # target_audience: JSON-string or comma-separated careers
            ta = data.get('target_audience')
            if isinstance(ta, str):
                t = ta.strip()
                if t == '':
                    data['target_audience'] = None
                else:
                    try:
                        data['target_audience'] = json.loads(t)
                    except Exception:
                        careers = [x.strip()
                                   for x in t.split(',') if x.strip()]
                        data['target_audience'] = {
                            'general': False, 'careers': careers}

        except Exception:
            # si algo falla, devolvemos los datos sin tocar
            return data

        return data


activity_schema = ActivitySchema()
activities_schema = ActivitySchema(many=True)
