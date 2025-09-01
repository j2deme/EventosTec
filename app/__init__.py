from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_marshmallow import Marshmallow
from app.config import config

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
ma = Marshmallow()


def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Inicializar extensiones
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    ma.init_app(app)

    # Registrar blueprints
    from app.api.auth_bp import auth_bp
    from app.api.events_bp import events_bp
    from app.api.activities_bp import activities_bp
    from app.api.students_bp import students_bp
    from app.api.attendance_bp import attendance_bp
    from app.api.registrations_bp import registrations_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(activities_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(registrations_bp)

    return app
