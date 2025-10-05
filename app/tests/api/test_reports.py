import pytest
import json
from datetime import datetime, timezone

from app import db
from app.models.event import Event
from app.models.activity import Activity
from app.models.student import Student
from app.models.registration import Registration


def test_preregistrations_by_career_requires_auth(client):
    """Test que preregistrations_by_career requiere autenticación."""
    response = client.get('/api/reports/preregistrations_by_career')
    
    assert response.status_code == 401


def test_preregistrations_by_career_no_filters(client, auth_headers, sample_data, app):
    """Test preregistrations_by_career sin filtros."""
    with app.app_context():
        # Crear estudiante con carrera y número de control
        student2 = Student(
            control_number='20241234',
            full_name='Test Student 2',
            email='test2@example.com',
            career='ISC'
        )
        db.session.add(student2)
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
        
        # Crear registros
        reg1 = Registration(
            student_id=sample_data['student_id'],
            activity_id=activity.id,
            status='Registrado'
        )
        reg2 = Registration(
            student_id=student2.id,
            activity_id=activity.id,
            status='Registrado'
        )
        db.session.add_all([reg1, reg2])
        db.session.commit()
    
    response = client.get('/api/reports/preregistrations_by_career',
                          headers=auth_headers)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'data' in data
    assert isinstance(data['data'], list)
    assert len(data['data']) >= 1


def test_preregistrations_by_career_filter_by_event(client, auth_headers, sample_data, app):
    """Test preregistrations_by_career filtrando por evento."""
    with app.app_context():
        # Crear segundo evento
        event2 = Event(
            name='Segundo Evento',
            description='Evento de prueba 2',
            start_date=datetime(2024, 2, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 2, 5, tzinfo=timezone.utc),
            is_active=True
        )
        db.session.add(event2)
        db.session.commit()
        
        # Crear actividades en diferentes eventos
        activity1 = Activity(
            event_id=sample_data['event_id'],
            department='TEST',
            name='Activity Event 1',
            start_datetime=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            duration_hours=2.0,
            activity_type='Taller',
            location='Aula 101',
            modality='Presencial'
        )
        activity2 = Activity(
            event_id=event2.id,
            department='TEST',
            name='Activity Event 2',
            start_datetime=datetime(2024, 2, 1, 14, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2024, 2, 1, 16, 0, 0, tzinfo=timezone.utc),
            duration_hours=2.0,
            activity_type='Conferencia',
            location='Aula 102',
            modality='Presencial'
        )
        db.session.add_all([activity1, activity2])
        db.session.commit()
        
        # Crear registros
        reg1 = Registration(
            student_id=sample_data['student_id'],
            activity_id=activity1.id,
            status='Registrado'
        )
        reg2 = Registration(
            student_id=sample_data['student_id'],
            activity_id=activity2.id,
            status='Registrado'
        )
        db.session.add_all([reg1, reg2])
        db.session.commit()
        
        event1_id = sample_data['event_id']
    
    # Filtrar por primer evento
    response = client.get(f'/api/reports/preregistrations_by_career?event_id={event1_id}',
                          headers=auth_headers)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'data' in data
    # Debe haber al menos un registro del evento 1
    assert len(data['data']) >= 1


def test_preregistrations_by_career_filter_by_activity(client, auth_headers, sample_data, app):
    """Test preregistrations_by_career filtrando por actividad."""
    with app.app_context():
        # Crear estudiante con datos estructurados
        student2 = Student(
            control_number='20241234',
            full_name='Test Student 2',
            email='test2@example.com',
            career='IIA'
        )
        db.session.add(student2)
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
        
        # Crear registros
        reg = Registration(
            student_id=student2.id,
            activity_id=activity.id,
            status='Registrado'
        )
        db.session.add(reg)
        db.session.commit()
        
        activity_id = activity.id
    
    response = client.get(f'/api/reports/preregistrations_by_career?activity_id={activity_id}',
                          headers=auth_headers)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'data' in data
    assert len(data['data']) >= 1
    # Verificar estructura de respuesta
    for item in data['data']:
        assert 'career' in item
        assert 'generation' in item
        assert 'count' in item


def test_preregistrations_by_career_groups_by_career_and_generation(client, auth_headers, sample_data, app):
    """Test que preregistrations_by_career agrupa correctamente por carrera y generación."""
    with app.app_context():
        # Crear estudiantes de diferentes carreras y generaciones
        students = [
            Student(control_number='20241001', full_name='S1', email='s1@test.com', career='ISC'),
            Student(control_number='20241002', full_name='S2', email='s2@test.com', career='ISC'),
            Student(control_number='20231003', full_name='S3', email='s3@test.com', career='IIA'),
        ]
        for s in students:
            db.session.add(s)
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
        
        # Crear registros para todos
        for s in students:
            reg = Registration(
                student_id=s.id,
                activity_id=activity.id,
                status='Registrado'
            )
            db.session.add(reg)
        db.session.commit()
    
    response = client.get('/api/reports/preregistrations_by_career',
                          headers=auth_headers)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'data' in data
    # Debe haber múltiples grupos (ISC-2024, IIA-2023, etc.)
    assert len(data['data']) >= 2
    
    # Verificar que hay agrupación por carrera
    careers = [item['career'] for item in data['data']]
    assert 'ISC' in careers or 'IIA' in careers


def test_attendance_list_requires_auth(client):
    """Test que attendance_list requiere autenticación."""
    response = client.get('/api/reports/attendance_list?activity_id=1')
    
    assert response.status_code == 401


def test_attendance_list_requires_activity_id(client, auth_headers):
    """Test que attendance_list requiere activity_id."""
    response = client.get('/api/reports/attendance_list',
                          headers=auth_headers)
    
    assert response.status_code == 400


def test_attendance_list_activity_not_found(client, auth_headers):
    """Test attendance_list con actividad inexistente."""
    response = client.get('/api/reports/attendance_list?activity_id=999999',
                          headers=auth_headers)
    
    assert response.status_code == 404
