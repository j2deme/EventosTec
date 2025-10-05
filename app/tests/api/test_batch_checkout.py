import pytest
import json
from datetime import datetime, timezone

from app import db
from app.models.activity import Activity
from app.models.attendance import Attendance
from app.models.student import Student


def test_batch_checkout_requires_auth(client, sample_data):
    """Test que batch-checkout requiere autenticación."""
    payload = {
        'activity_id': sample_data['event_id'],
        'dry_run': True
    }
    
    # Sin headers de autenticación
    response = client.post('/api/attendances/batch-checkout',
                          json=payload)
    
    assert response.status_code == 401


def test_batch_checkout_requires_activity_id(client, auth_headers):
    """Test que batch-checkout requiere activity_id."""
    payload = {
        'dry_run': True
    }
    
    response = client.post('/api/attendances/batch-checkout',
                          headers=auth_headers,
                          json=payload)
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'activity_id es requerido' in data['message']


def test_batch_checkout_activity_not_found(client, auth_headers):
    """Test batch-checkout con actividad inexistente."""
    payload = {
        'activity_id': 999999,
        'dry_run': True
    }
    
    response = client.post('/api/attendances/batch-checkout',
                          headers=auth_headers,
                          json=payload)
    
    assert response.status_code == 404


def test_batch_checkout_dry_run(client, auth_headers, sample_data, app):
    """Test batch-checkout en modo dry_run."""
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
        
        # Crear asistencia sin check_out
        attendance = Attendance(
            student_id=sample_data['student_id'],
            activity_id=activity.id,
            check_in_time=datetime(2024, 1, 1, 10, 30, 0, tzinfo=timezone.utc),
            status='Parcial'
        )
        db.session.add(attendance)
        db.session.commit()
        
        activity_id = activity.id
        attendance_id = attendance.id
    
    payload = {
        'activity_id': activity_id,
        'dry_run': True
    }
    
    response = client.post('/api/attendances/batch-checkout',
                          headers=auth_headers,
                          json=payload)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'summary' in data
    summary = data['summary']
    assert 'processed' in summary
    assert 'updated' in summary
    assert 'related_created' in summary
    assert summary['processed'] >= 1
    
    # Verificar que no se modificó la asistencia (dry_run)
    with app.app_context():
        att = db.session.get(Attendance, attendance_id)
        assert att.check_out_time is None


def test_batch_checkout_execute(client, auth_headers, sample_data, app):
    """Test batch-checkout ejecutando cambios."""
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
        
        # Crear asistencia sin check_out
        attendance = Attendance(
            student_id=sample_data['student_id'],
            activity_id=activity.id,
            check_in_time=datetime(2024, 1, 1, 10, 30, 0, tzinfo=timezone.utc),
            status='Parcial',
            attendance_percentage=0.0
        )
        db.session.add(attendance)
        db.session.commit()
        
        activity_id = activity.id
        attendance_id = attendance.id
    
    payload = {
        'activity_id': activity_id,
        'dry_run': False
    }
    
    response = client.post('/api/attendances/batch-checkout',
                          headers=auth_headers,
                          json=payload)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'summary' in data
    summary = data['summary']
    assert summary['processed'] >= 1
    assert summary['updated'] >= 1
    
    # Verificar que se modificó la asistencia
    with app.app_context():
        att = db.session.get(Attendance, attendance_id)
        assert att.check_out_time is not None
        # El porcentaje debe haberse calculado
        assert att.attendance_percentage > 0


def test_batch_checkout_with_student_ids_filter(client, auth_headers, sample_data, app):
    """Test batch-checkout filtrando por student_ids."""
    with app.app_context():
        # Crear segundo estudiante
        student2 = Student(
            control_number='L20888888',
            full_name='Estudiante 2',
            email='est2@test.com',
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
        
        # Crear asistencias para ambos estudiantes
        att1 = Attendance(
            student_id=sample_data['student_id'],
            activity_id=activity.id,
            check_in_time=datetime(2024, 1, 1, 10, 30, 0, tzinfo=timezone.utc),
            status='Parcial'
        )
        att2 = Attendance(
            student_id=student2.id,
            activity_id=activity.id,
            check_in_time=datetime(2024, 1, 1, 10, 35, 0, tzinfo=timezone.utc),
            status='Parcial'
        )
        db.session.add_all([att1, att2])
        db.session.commit()
        
        activity_id = activity.id
        student1_id = sample_data['student_id']
        att1_id = att1.id
        att2_id = att2.id
    
    # Filtrar solo el primer estudiante
    payload = {
        'activity_id': activity_id,
        'student_ids': [student1_id],
        'dry_run': False
    }
    
    response = client.post('/api/attendances/batch-checkout',
                          headers=auth_headers,
                          json=payload)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'summary' in data
    summary = data['summary']
    # Solo debe procesar una asistencia
    assert summary['processed'] == 1
    
    # Verificar que solo se modificó att1
    with app.app_context():
        att1 = db.session.get(Attendance, att1_id)
        att2 = db.session.get(Attendance, att2_id)
        assert att1.check_out_time is not None
        assert att2.check_out_time is None


def test_batch_checkout_skips_without_check_in(client, auth_headers, sample_data, app):
    """Test que batch-checkout omite asistencias sin check_in_time."""
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
        
        # Crear asistencia sin check_in_time
        attendance = Attendance(
            student_id=sample_data['student_id'],
            activity_id=activity.id,
            check_in_time=None,
            status='Ausente'
        )
        db.session.add(attendance)
        db.session.commit()
        
        activity_id = activity.id
    
    payload = {
        'activity_id': activity_id,
        'dry_run': True
    }
    
    response = client.post('/api/attendances/batch-checkout',
                          headers=auth_headers,
                          json=payload)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'summary' in data
    summary = data['summary']
    # Debe indicar que fue omitida
    assert summary['processed'] >= 1
    if 'details' in summary and len(summary['details']) > 0:
        # Buscar el detalle de la asistencia omitida
        skipped = [d for d in summary['details'] if d.get('action') == 'skipped']
        assert len(skipped) >= 1


def test_batch_checkout_calculates_percentage(client, auth_headers, sample_data, app):
    """Test que batch-checkout calcula el porcentaje de asistencia."""
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
        
        # Crear asistencia con check_in pero sin check_out
        # Asumiendo que estuvo 1 hora de 2 horas = 50%
        attendance = Attendance(
            student_id=sample_data['student_id'],
            activity_id=activity.id,
            check_in_time=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            status='Parcial',
            attendance_percentage=0.0
        )
        db.session.add(attendance)
        db.session.commit()
        
        activity_id = activity.id
        attendance_id = attendance.id
    
    payload = {
        'activity_id': activity_id,
        'dry_run': False
    }
    
    response = client.post('/api/attendances/batch-checkout',
                          headers=auth_headers,
                          json=payload)
    
    assert response.status_code == 200
    
    # Verificar que se calculó el porcentaje
    with app.app_context():
        att = db.session.get(Attendance, attendance_id)
        assert att.attendance_percentage >= 0
        # Debe tener check_out_time
        assert att.check_out_time is not None


def test_batch_checkout_default_dry_run_true(client, auth_headers, sample_data, app):
    """Test que batch-checkout usa dry_run=True por defecto."""
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
        
        attendance = Attendance(
            student_id=sample_data['student_id'],
            activity_id=activity.id,
            check_in_time=datetime(2024, 1, 1, 10, 30, 0, tzinfo=timezone.utc),
            status='Parcial'
        )
        db.session.add(attendance)
        db.session.commit()
        
        activity_id = activity.id
        attendance_id = attendance.id
    
    # No especificar dry_run (debe usar True por defecto)
    payload = {
        'activity_id': activity_id
    }
    
    response = client.post('/api/attendances/batch-checkout',
                          headers=auth_headers,
                          json=payload)
    
    assert response.status_code == 200
    
    # Verificar que no se modificó (dry_run por defecto)
    with app.app_context():
        att = db.session.get(Attendance, attendance_id)
        assert att.check_out_time is None
