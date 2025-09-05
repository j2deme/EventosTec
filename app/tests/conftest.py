from app.models.student import Student
from app.models.event import Event
from app.models.user import User
from app import create_app, db
import pytest
import sys
import os
from datetime import datetime
sys.path.insert(0, os.path.abspath('.'))


@pytest.fixture
def app():
    """Crear aplicación de test"""
    app = create_app('testing')
    app.config['TESTING'] = True
    # Asegurar que se crea la base de datos en memoria y las tablas
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

    with app.app_context():
        # Crear todas las tablas
        db.create_all()
        yield app
        # Limpiar al finalizar
        db.drop_all()


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
        # Crear usuario admin de prueba
        user = User(username='testadmin', email='admin@test.com', role='Admin')
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
        event = Event(
            name='Evento de prueba',
            description='Descripción del evento',
            start_date=datetime(2024, 1, 1, 9, 0, 0),  # Objeto datetime
            end_date=datetime(2024, 1, 1, 17, 0, 0),   # Objeto datetime
            is_active=True
        )
        db.session.add(event)

        # Crear estudiante de prueba
        student = Student(
            control_number='12345678',
            full_name='Juan Pérez',
            career='Ingeniería en Sistemas'
        )
        db.session.add(student)

        db.session.commit()

        # Devolver solo los IDs para evitar problemas de desvinculación
        return {
            'event_id': event.id,
            'student_id': student.id
        }
