import pytest
import json
from datetime import datetime, timezone

from app import db
from app.models.event import Event
from app.models.activity import Activity
from app.models.attendance import Attendance
from app.models.student import Student
from app.models.registration import Registration


def test_get_stats_no_active_events(client):
    """Test obtener estadísticas sin eventos activos."""
    response = client.get('/api/stats/')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'total_activities' in data
    assert 'total_registrations' in data
    assert 'total_attendances' in data
    assert 'active_events' in data
    assert 'total_students' in data
    assert 'today_attendances' in data
    assert data['active_events'] == 0
    assert data['total_activities'] == 0
    assert data['total_registrations'] == 0
    assert data['total_attendances'] == 0


def test_get_stats_with_single_active_event(client, sample_data, app):
    """Test obtener estadísticas con un evento activo."""
    with app.app_context():
        # El sample_data ya crea un evento, aseguremos que esté activo
        event = db.session.get(Event, sample_data['event_id'])
        event.is_active = True
        db.session.commit()
        
        # Crear actividad adicional
        activity = Activity(
            event_id=event.id,
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
        
        # Crear registro
        registration = Registration(
            student_id=sample_data['student_id'],
            activity_id=activity.id,
            status='Registrado'
        )
        db.session.add(registration)
        db.session.commit()
        
        # Crear asistencia de hoy
        attendance = Attendance(
            student_id=sample_data['student_id'],
            activity_id=activity.id,
            check_in_time=datetime.now(timezone.utc),
            status='Asistió',
            attendance_percentage=100.0
        )
        db.session.add(attendance)
        db.session.commit()
    
    response = client.get('/api/stats/')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['active_events'] >= 1
    assert data['total_activities'] >= 1
    assert data['total_registrations'] >= 1
    assert data['total_attendances'] >= 1
    assert data['today_attendances'] >= 1
    assert data['total_students'] >= 1


def test_get_stats_with_multiple_active_events(client, sample_data, app):
    """Test obtener estadísticas con múltiples eventos activos."""
    with app.app_context():
        # Crear segundo evento activo
        event2 = Event(
            name='Segundo Evento',
            description='Evento de prueba 2',
            start_date=datetime(2024, 2, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 2, 5, tzinfo=timezone.utc),
            is_active=True
        )
        db.session.add(event2)
        db.session.commit()
        
        # Asegurar que el primer evento también esté activo
        event1 = db.session.get(Event, sample_data['event_id'])
        event1.is_active = True
        db.session.commit()
        
        # Crear actividades para ambos eventos
        activity1 = Activity(
            event_id=event1.id,
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
        
        # Crear registros para ambas actividades
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
    
    response = client.get('/api/stats/')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['active_events'] >= 2
    # Los totales deben ser la suma de ambos eventos
    assert data['total_activities'] >= 2
    assert data['total_registrations'] >= 2


def test_get_stats_today_attendances_only_counts_today(client, sample_data, app):
    """Test que today_attendances solo cuenta asistencias de hoy."""
    with app.app_context():
        event = db.session.get(Event, sample_data['event_id'])
        event.is_active = True
        db.session.commit()
        
        # Crear dos actividades diferentes para evitar constraint de (student_id, activity_id) único
        activity1 = Activity(
            event_id=event.id,
            department='TEST',
            name='Test Activity 1',
            start_datetime=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            duration_hours=2.0,
            activity_type='Taller',
            location='Aula 101',
            modality='Presencial'
        )
        activity2 = Activity(
            event_id=event.id,
            department='TEST',
            name='Test Activity 2',
            start_datetime=datetime(2024, 1, 2, 10, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
            duration_hours=2.0,
            activity_type='Conferencia',
            location='Aula 102',
            modality='Presencial'
        )
        db.session.add_all([activity1, activity2])
        db.session.commit()
        
        # Crear asistencia de hoy
        att_today = Attendance(
            student_id=sample_data['student_id'],
            activity_id=activity1.id,
            check_in_time=datetime.now(timezone.utc),
            status='Asistió',
            attendance_percentage=100.0
        )
        db.session.add(att_today)
        db.session.flush()
        
        # Crear asistencia de ayer usando activity2
        att_yesterday = Attendance(
            student_id=sample_data['student_id'],
            activity_id=activity2.id,
            check_in_time=datetime(2024, 1, 2, 10, 0, 0, tzinfo=timezone.utc),
            status='Asistió',
            attendance_percentage=100.0
        )
        db.session.add(att_yesterday)
        db.session.flush()
        
        # Modificar created_at para simular asistencia de ayer
        from datetime import timedelta
        att_yesterday.created_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.session.commit()
        
        # Contar asistencias de hoy en la base de datos
        today = datetime.now().date()
        today_count = Attendance.query.filter(
            db.func.date(Attendance.created_at) == today
        ).count()
    
    response = client.get('/api/stats/')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    # today_attendances debe contar solo las de hoy
    assert data['today_attendances'] == today_count
    # Pero total_attendances debe incluir todas
    assert data['total_attendances'] >= 2
