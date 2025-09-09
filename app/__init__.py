from flask import Flask, render_template, redirect, url_for, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity
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

    # Configuración explícita de JWT
    app.config['JWT_TOKEN_LOCATION'] = ['headers']
    app.config['JWT_HEADER_NAME'] = 'Authorization'
    app.config['JWT_HEADER_TYPE'] = 'Bearer'

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
    from app.api.stats_bp import stats_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(activities_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(registrations_bp)
    app.register_blueprint(attendances_bp)
    app.register_blueprint(stats_bp)

    # Login
    @app.route('/')
    def index():
        return render_template('auth/login.html')

    # Ruta dashboard ADMIN
    @app.route('/dashboard/admin')
    def admin_dashboard():
        return render_template('admin/dashboard.html')

    # Ruta dashboard ESTUDIANTE
    @app.route('/dashboard/student')
    def student_dashboard():
        return render_template('student/dashboard.html')

    # Ruta para verificar autenticación
    @app.route('/api/auth/check')
    @jwt_required()
    def check_auth():
        return jsonify({'authenticated': True}), 200

    return app
