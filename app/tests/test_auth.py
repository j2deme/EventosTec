import pytest
import json


def test_admin_login(client):
    """Test de login de administrador"""
    # Crear usuario de prueba
    from app import db
    from app.models.user import User

    with client.application.app_context():  # Corregido
        user = User(username='testuser', email='test@test.com', role='Admin')
        user.set_password('testpass')
        db.session.add(user)
        db.session.commit()

    # Test login exitoso
    response = client.post('/api/auth/login',
                           json={'username': 'testuser', 'password': 'testpass'})

    assert response.status_code == 200


def test_admin_login_invalid_credentials(client):
    """Test de login con credenciales inválidas"""
    response = client.post('/api/auth/login',
                           json={'username': 'nonexistent', 'password': 'wrongpass'})

    assert response.status_code == 401


def test_student_login_external_api_mock(client, mocker):
    """Test de login de estudiante (mockeando API externa)"""
    # Mockear la respuesta de la API externa
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    # El endpoint externo del código espera un JSON con 'success' y 'data'
    mock_response.json.return_value = {'success': True, 'data': {'name': 'Juan Pérez', 'career': {'name': 'Sistemas'}, 'email': 'juan@example.com'}}

    # El código hace requests.post, no get
    mocker.patch('requests.post', return_value=mock_response)

    response = client.post('/api/auth/student-login',
                           json={'control_number': '12345678', 'password': 'testpass'})

    assert response.status_code == 200
