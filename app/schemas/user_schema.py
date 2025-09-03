from marshmallow import fields, validate, validates_schema, ValidationError
from app import ma
from app.models.user import User


class UserSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = User
        load_instance = False
        # Excluir password_hash del dump
        exclude = ('password_hash',)

    # Campos para serialización
    id = fields.Int(dump_only=True)
    username = fields.Str(
        required=True, validate=validate.Length(min=3, max=80))
    email = fields.Email(required=True, validate=validate.Length(max=120))
    role = fields.Str(
        required=True, validate=validate.OneOf(['Admin', 'Staff']))
    is_active = fields.Bool(load_default=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    # Campo especial para password (solo entrada)
    password = fields.Str(required=True, load_only=True,
                          validate=validate.Length(min=6))


user_schema = UserSchema()
users_schema = UserSchema(many=True)

# Esquema para login (solo username y password)


class UserLoginSchema(ma.Schema):
    username = fields.Str(
        required=True, validate=validate.Length(min=3, max=80))
    password = fields.Str(required=True, validate=validate.Length(min=6))


user_login_schema = UserLoginSchema()
