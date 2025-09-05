from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_marshmallow import Marshmallow
import os

# Inicializar extensiones
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
ma = Marshmallow()


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_CONFIG', 'default')

    app = Flask(__name__, template_folder='templates', static_folder='static')

    # Importar configuración
    from config import config
    app.config.from_object(config[config_name])

    # Inicializar extensiones con la app
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    ma.init_app(app)

    # Importar modelos para que Flask-Migrate los detecte
    from app.models import Event, Activity, Student, User, Attendance, Registration

    # Registrar blueprints
    from app.api.auth_bp import auth_bp
    from app.api.events_bp import events_bp
    from app.api.activities_bp import activities_bp
    from app.api.students_bp import students_bp
    from app.api.registrations_bp import registrations_bp
    from app.api.attendances_bp import attendances_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(activities_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(registrations_bp)
    app.register_blueprint(attendances_bp)

    return app
