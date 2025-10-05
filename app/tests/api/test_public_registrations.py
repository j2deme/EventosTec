import pytest
import json
from datetime import datetime, timezone, timedelta

from app import db
from app.models.activity import Activity
from app.models.registration import Registration
from app.models.attendance import Attendance
from app.models.student import Student
from app.utils.token_utils import generate_public_token


def test_walkin_creates_student_and_attendance(client, sample_data, app):
    """Test que walkin crea estudiante y asistencia cuando no existen."""
    with app.app_context():
        activity = Activity(
            event_id=sample_data['event_id'],
            department='TEST',
            name='Test Activity',
            start_datetime=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            duration_hours=2.0,
            activity_type='Taller',
            location='Aula 101',
            modality='Presencial'
        )
        db.session.add(activity)
        db.session.commit()
        
        token = generate_public_token(activity.id)
        activity_id = activity.id
    
    payload = {
        'token': token,
        'control_number': 'L20999999',
        'full_name': 'Nuevo Alumno',
        'email': 'nuevo@test.com',
        'career': 'ISC'
    }
    
    response = client.post('/api/public/registrations/walkin', json=payload)
    
    assert response.status_code == 201
    data = json.loads(response.data)
    assert 'attendance' in data
    assert 'student' in data
    
    # Verificar que el estudiante fue creado
    with app.app_context():
        student = Student.query.filter_by(control_number='L20999999').first()
        assert student is not None
        assert student.full_name == 'Nuevo Alumno'
        
        # Verificar que la asistencia fue creada
        attendance = Attendance.query.filter_by(
            student_id=student.id,
            activity_id=activity_id
        ).first()
        assert attendance is not None
        assert attendance.status == 'Asistió'


def test_walkin_reuses_existing_student(client, sample_data, app):
    """Test que walkin reutiliza estudiante existente."""
    with app.app_context():
        # Crear estudiante
        student = Student(
            control_number='L20888888',
            full_name='Estudiante Existente',
            email='existente@test.com',
            career='ISC'
        )
        db.session.add(student)
        db.session.commit()
        
        activity = Activity(
            event_id=sample_data['event_id'],
            department='TEST',
            name='Test Activity',
            start_datetime=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            duration_hours=2.0,
            activity_type='Taller',
            location='Aula 101',
            modality='Presencial'
        )
        db.session.add(activity)
        db.session.commit()
        
        token = generate_public_token(activity.id)
        student_id = student.id
        activity_id = activity.id
    
    payload = {
        'token': token,
        'control_number': 'L20888888',
        'full_name': 'Estudiante Existente',
        'email': 'existente@test.com',
        'career': 'ISC'
    }
    
    response = client.post('/api/public/registrations/walkin', json=payload)
    
    assert response.status_code == 201
    data = json.loads(response.data)
    assert 'student' in data
    assert data['student']['id'] == student_id
    
    # Verificar que no se creó otro estudiante
    with app.app_context():
        count = Student.query.filter_by(control_number='L20888888').count()
        assert count == 1


def test_walkin_returns_409_if_attendance_exists(client, sample_data, app):
    """Test que walkin retorna 409 si ya existe asistencia."""
    with app.app_context():
        student = Student(
            control_number='L20777777',
            full_name='Alumno Duplicado',
            email='duplicado@test.com',
            career='ISC'
        )
        db.session.add(student)
        db.session.commit()
        
        activity = Activity(
            event_id=sample_data['event_id'],
            department='TEST',
            name='Test Activity',
            start_datetime=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            duration_hours=2.0,
            activity_type='Taller',
            location='Aula 101',
            modality='Presencial'
        )
        db.session.add(activity)
        db.session.commit()
        
        # Crear asistencia previa
        attendance = Attendance(
            student_id=student.id,
            activity_id=activity.id,
            check_in_time=datetime.now(timezone.utc),
            status='Asistió'
        )
        db.session.add(attendance)
        db.session.commit()
        
        token = generate_public_token(activity.id)
    
    payload = {
        'token': token,
        'control_number': 'L20777777',
        'full_name': 'Alumno Duplicado',
        'email': 'duplicado@test.com',
        'career': 'ISC'
    }
    
    response = client.post('/api/public/registrations/walkin', json=payload)
    
    assert response.status_code == 409
    data = json.loads(response.data)
    assert 'Ya existe una asistencia' in data['message']


def test_walkin_invalid_token(client):
    """Test walkin con token inválido."""
    payload = {
        'token': 'invalid_token',
        'control_number': 'L20999999',
        'full_name': 'Test',
        'email': 'test@test.com',
        'career': 'ISC'
    }
    
    response = client.post('/api/public/registrations/walkin', json=payload)
    
    assert response.status_code == 403


def test_confirm_registration_with_create_attendance(client, sample_data, app):
    """Test confirmar registro y crear asistencia."""
    with app.app_context():
        activity = Activity(
            event_id=sample_data['event_id'],
            department='TEST',
            name='Test Activity',
            start_datetime=datetime.now(timezone.utc) - timedelta(hours=1),
            end_datetime=datetime.now(timezone.utc) + timedelta(hours=1),
            duration_hours=2.0,
            activity_type='Taller',
            location='Aula 101',
            modality='Presencial'
        )
        db.session.add(activity)
        db.session.commit()
        
        # Crear registro sin confirmar
        reg = Registration(
            student_id=sample_data['student_id'],
            activity_id=activity.id,
            status='Registrado',
            attended=False
        )
        db.session.add(reg)
        db.session.commit()
        
        reg_id = reg.id
        activity_id = activity.id
    
    payload = {
        'confirm': True,
        'create_attendance': True
    }
    
    response = client.post(f'/api/public/registrations/{reg_id}/confirm', json=payload)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'attendance_id' in data
    assert data['attendance_id'] is not None
    
    # Verificar que se creó la asistencia
    with app.app_context():
        attendance = Attendance.query.filter_by(
            student_id=sample_data['student_id'],
            activity_id=activity_id
        ).first()
        assert attendance is not None
        assert attendance.status == 'Asistió'
        
        # Verificar que el registro fue actualizado
        reg = db.session.get(Registration, reg_id)
        assert reg.attended is True
        assert reg.status == 'Asistió'


def test_confirm_registration_without_create_attendance(client, sample_data, app):
    """Test confirmar registro sin crear asistencia."""
    with app.app_context():
        activity = Activity(
            event_id=sample_data['event_id'],
            department='TEST',
            name='Test Activity',
            start_datetime=datetime.now(timezone.utc) - timedelta(hours=1),
            end_datetime=datetime.now(timezone.utc) + timedelta(hours=1),
            duration_hours=2.0,
            activity_type='Taller',
            location='Aula 101',
            modality='Presencial'
        )
        db.session.add(activity)
        db.session.commit()
        
        reg = Registration(
            student_id=sample_data['student_id'],
            activity_id=activity.id,
            status='Registrado',
            attended=False
        )
        db.session.add(reg)
        db.session.commit()
        
        reg_id = reg.id
        student_id = sample_data['student_id']
        activity_id = activity.id
    
    payload = {
        'confirm': True,
        'create_attendance': False
    }
    
    response = client.post(f'/api/public/registrations/{reg_id}/confirm', json=payload)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    
    # Verificar que NO se creó asistencia
    with app.app_context():
        attendance = Attendance.query.filter_by(
            student_id=student_id,
            activity_id=activity_id
        ).first()
        assert attendance is None
        
        # Pero el registro sí fue actualizado
        reg = db.session.get(Registration, reg_id)
        assert reg.attended is True


def test_confirm_registration_unconfirm(client, sample_data, app):
    """Test desconfirmar un registro."""
    with app.app_context():
        activity = Activity(
            event_id=sample_data['event_id'],
            department='TEST',
            name='Test Activity',
            start_datetime=datetime.now(timezone.utc) - timedelta(hours=1),
            end_datetime=datetime.now(timezone.utc) + timedelta(hours=1),
            duration_hours=2.0,
            activity_type='Taller',
            location='Aula 101',
            modality='Presencial'
        )
        db.session.add(activity)
        db.session.commit()
        
        # Crear registro confirmado
        reg = Registration(
            student_id=sample_data['student_id'],
            activity_id=activity.id,
            status='Asistió',
            attended=True,
            confirmation_date=datetime.now(timezone.utc)
        )
        db.session.add(reg)
        db.session.commit()
        
        reg_id = reg.id
    
    payload = {
        'confirm': False
    }
    
    response = client.post(f'/api/public/registrations/{reg_id}/confirm', json=payload)
    
    assert response.status_code == 200
    
    # Verificar que el registro fue desconfirmado
    with app.app_context():
        reg = db.session.get(Registration, reg_id)
        assert reg.attended is False
        assert reg.status == 'Registrado'
        assert reg.confirmation_date is None


def test_confirm_registration_expired_window(client, sample_data, app):
    """Test confirmar registro fuera de la ventana de confirmación."""
    with app.app_context():
        # Crear actividad que terminó hace más de 30 días
        activity = Activity(
            event_id=sample_data['event_id'],
            department='TEST',
            name='Test Activity',
            start_datetime=datetime.now(timezone.utc) - timedelta(days=50),
            end_datetime=datetime.now(timezone.utc) - timedelta(days=49),
            duration_hours=2.0,
            activity_type='Taller',
            location='Aula 101',
            modality='Presencial'
        )
        db.session.add(activity)
        db.session.commit()
        
        reg = Registration(
            student_id=sample_data['student_id'],
            activity_id=activity.id,
            status='Registrado',
            attended=False
        )
        db.session.add(reg)
        db.session.commit()
        
        reg_id = reg.id
    
    payload = {
        'confirm': True,
        'create_attendance': True
    }
    
    response = client.post(f'/api/public/registrations/{reg_id}/confirm', json=payload)
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'ventana de confirmación ha expirado' in data['message']


def test_toggle_attendance(client, sample_data, app):
    """Test toggle attendance status."""
    with app.app_context():
        activity = Activity(
            event_id=sample_data['event_id'],
            department='TEST',
            name='Test Activity',
            start_datetime=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            duration_hours=2.0,
            activity_type='Taller',
            location='Aula 101',
            modality='Presencial'
        )
        db.session.add(activity)
        db.session.commit()
        
        # Crear asistencia
        attendance = Attendance(
            student_id=sample_data['student_id'],
            activity_id=activity.id,
            check_in_time=datetime.now(timezone.utc),
            status='Asistió',
            attendance_percentage=100.0
        )
        db.session.add(attendance)
        db.session.commit()
        
        attendance_id = attendance.id
        original_status = attendance.status
    
    response = client.post(f'/api/public/attendances/{attendance_id}/toggle', json={})
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'attendance' in data
    
    # Verificar que el status cambió
    with app.app_context():
        att = db.session.get(Attendance, attendance_id)
        assert att.status != original_status


def test_toggle_attendance_not_found(client):
    """Test toggle attendance con ID inexistente."""
    response = client.post('/api/public/attendances/999999/toggle', json={})
    
    assert response.status_code == 404
