from app.models.student import Student
from app.models.student import Student
from app.models.event import Event
from app.models.user import User
from app import create_app, db
import pytest
import sys
import os
from datetime import datetime

# Asegurar que el cwd está en sys.path para imports relativos en tests (igual que antes)
sys.path.insert(0, os.path.abspath('.'))


@pytest.fixture
def app():
    """Crear aplicación de test usando SQLite en archivo para compartir conexión entre request y sesión."""
    # Usar base de datos SQLite en fichero para evitar el aislamiento de conexiones de ':memory:'
    test_db_path = os.path.join(os.getcwd(), 'test_eventostec.db')
    # Eliminar si existe de ejecuciones previas (antes de crear la app)
    try:
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
    except Exception:
        pass

    # Crear la app usando la configuración de testing
    _app = create_app('testing')
    _app.config['TESTING'] = True

    # Forzar URI absoluta y opciones de engine antes de inicializar/crear tablas
    _app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{test_db_path}'
    _app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'connect_args': {'check_same_thread': False}
    }

    # Re-inicializar db binding por si create_app había ligado otro engine
    try:
        db.init_app(_app)
    except Exception:
        # si ya estaba inicializada, ignorar
        pass

    # Crear tablas dentro del contexto y mantener el contexto activo
    # durante la ejecución del test (algunos tests dependen de ello).
    with _app.app_context():
        # Importar modelos explícitamente para asegurar que están registrados
        import app.models  # noqa: F401
        # Crear todas las tablas
        db.create_all()

        # Proveer la app al test (yield dentro del app_context para mantenerlo activo)
        yield _app

        # Teardown: limpiar DB y sesión dentro del mismo contexto
        db.session.remove()
        db.drop_all()

    try:
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
    except Exception:
        pass


@pytest.fixture
def client(app):
    """Cliente de test"""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Runner para comandos CLI"""
    return app.test_cli_runner()


@pytest.fixture
def auth_headers(app):
    """Headers de autenticación para admin"""
    with app.app_context():
        # Crear usuario admin de prueba (asignación explícita para Pylance)
        user = User()
        user.username = 'testadmin'
        user.email = 'admin@test.com'
        user.role = 'Admin'
        user.set_password('testpassword')
        db.session.add(user)
        db.session.commit()

        from flask_jwt_extended import create_access_token
        # Convertir ID a string para JWT
        token = create_access_token(identity=str(user.id))
        return {'Authorization': f'Bearer {token}'}


# Fixture para datos de muestra, devolviendo IDs para evitar DetachedInstanceError


@pytest.fixture
def sample_data(app):
    """Datos de prueba, devuelve diccionario con IDs"""
    with app.app_context():
        # Crear evento de prueba con objetos datetime
        event = Event()
        event.name = 'Evento de prueba'
        event.description = 'Descripción del evento'
        event.start_date = datetime(2024, 1, 1, 9, 0, 0)
        event.end_date = datetime(2024, 1, 1, 17, 0, 0)
        event.is_active = True
        db.session.add(event)

        # Crear estudiante de prueba
        student = Student()
        student.control_number = '12345678'
        student.full_name = 'Juan Pérez'
        student.career = 'Ingeniería en Sistemas'
        db.session.add(student)

        db.session.commit()

        # Devolver solo los IDs para evitar problemas de desvinculación
        return {
            'event_id': event.id,
            'student_id': student.id
        }
