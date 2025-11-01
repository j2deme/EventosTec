from flask import Flask, render_template, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager, jwt_required
from flask_marshmallow import Marshmallow
import os

# Inicializar extensiones
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
ma = Marshmallow()


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get("FLASK_CONFIG", "default")

    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Importar configuración
    from config import config

    app.config.from_object(config[config_name])

    # Configuración explícita de JWT
    app.config["JWT_TOKEN_LOCATION"] = ["headers"]
    app.config["JWT_HEADER_NAME"] = "Authorization"
    app.config["JWT_HEADER_TYPE"] = "Bearer"

    # Inicializar extensiones con la app
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    ma.init_app(app)

    # Importar modelos para que Flask-Migrate los detecte
    from app.models import (
        Event,
        Activity,
        Student,
        User,
        Attendance,
        Registration,
        AppSetting,
    )

    # Registrar blueprints
    from app.api.auth_bp import auth_bp
    from app.api.events_bp import events_bp
    from app.api.activities_bp import activities_bp
    from app.api.students_bp import students_bp
    from app.api.registrations_bp import registrations_bp
    from app.api.attendances_bp import attendances_bp
    from app.api.stats_bp import stats_bp
    from app.api.reports_bp import reports_bp
    from app.api.self_register_bp import self_register_bp
    from app.api.public_registrations_bp import public_registrations_bp
    from app.api.public_event_bp import public_event_bp
    from app.api.admin_settings_bp import admin_settings_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(activities_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(registrations_bp)
    app.register_blueprint(attendances_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(self_register_bp)
    app.register_blueprint(public_registrations_bp)
    app.register_blueprint(public_event_bp)
    app.register_blueprint(admin_settings_bp)

    # Registrar filtros Jinja útiles
    try:
        from app.utils.datetime_utils import safe_iso

        @app.template_filter("safe_iso")
        def _jinja_safe_iso(dt):
            try:
                return safe_iso(dt)
            except Exception:
                # En plantillas, preferir devolver cadena vacía en caso de fallo
                return ""
    except Exception:
        # No fallar la creación de la app si por alguna razón no se puede importar
        pass

    # Login
    @app.route("/")
    def index():
        return render_template("auth/login.html")

    # Ruta dashboard ADMIN
    @app.route("/dashboard/admin")
    def admin_dashboard():
        return render_template("admin/dashboard.html")

    # Ruta dashboard ESTUDIANTE
    @app.route("/dashboard/student")
    def student_dashboard():
        return render_template("student/dashboard.html")

    # Ruta para verificar autenticación
    @app.route("/api/auth/check")
    @jwt_required()
    def check_auth():
        return jsonify({"authenticated": True}), 200

    # Simple favicon route to avoid 404s from browsers requesting /favicon.ico
    @app.route("/favicon.ico")
    def favicon():
        # Prefer a static file if present (favicon.svg or favicon.ico)
        static_dir = app.static_folder or os.path.join(app.root_path, "static")
        static_favicon_svg = os.path.join(static_dir, "favicon.svg")
        static_favicon_ico = os.path.join(static_dir, "favicon.ico")
        if os.path.exists(static_favicon_svg):
            return app.send_static_file("favicon.svg")
        if os.path.exists(static_favicon_ico):
            return app.send_static_file("favicon.ico")

        # Fallback to an inline SVG
        svg = (
            "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'>"
            "<rect width='100%' height='100%' fill='%233b82f6'/>"
            "<text x='50%' y='50%' font-size='10' fill='white' text-anchor='middle' dominant-baseline='central'>ET</text>"
            "</svg>"
        )
        return Response(svg, mimetype="image/svg+xml")

    return app
