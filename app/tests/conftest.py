# app/tests/conftest.py
from app.models.student import Student
from app.models.activity import Activity
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
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

    with app.app_context():
        db.create_all()
        yield app
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
        token = create_access_token(identity=str(user.id))
        return {'Authorization': f'Bearer {token}'}


@pytest.fixture
def sample_data(app):
    """Datos de prueba"""
    with app.app_context():
        # Crear evento de prueba con objetos datetime
        event = Event(
            name='Evento de prueba',
            description='Descripción del evento',
            start_date=datetime(2024, 1, 1, 9, 0, 0),
            end_date=datetime(2024, 1, 1, 17, 0, 0),
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

        return {
            'event_id': event.id,
            'student_id': student.id
        }
