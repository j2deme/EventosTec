from datetime import datetime, timedelta
import json

from app import db
from app.models.activity import Activity


def create_activity_for_event(app, event_id, **kwargs):
    # valores por defecto
    defaults = {
        'department': 'CS',
        'name': 'Actividad prueba',
        'description': 'Desc',
        'start_datetime': datetime.utcnow(),
        'end_datetime': datetime.utcnow() + timedelta(hours=1),
        'duration_hours': 1.0,
        'activity_type': 'Magistral',
        'location': 'Aula 1',
        'modality': 'Presencial',
        'max_capacity': 100,
    }
    defaults.update(kwargs)
    activity = Activity(event_id=event_id, **defaults)
    db.session.add(activity)
    db.session.commit()
    return activity


def test_activities_include_magistral_by_default(app, client, sample_data):
    with app.app_context():
        # Crear una actividad magistral y otra taller
        m = create_activity_for_event(
            app, sample_data['event_id'], activity_type='Magistral', name='Magistral 1')
        t = create_activity_for_event(
            app, sample_data['event_id'], activity_type='Taller', name='Taller 1')

        # Llamada sin for_student -> debería incluir magistral
        resp = client.get(
            f"/api/activities/?event_id={sample_data['event_id']}&per_page=10")
        assert resp.status_code == 200
        data = resp.get_json()
        types = [a['activity_type'] for a in data.get('activities', [])]
        assert 'Magistral' in types
        assert 'Taller' in types


def test_activities_exclude_magistral_for_student(app, client, sample_data):
    with app.app_context():
        # Crear actividades
        m = create_activity_for_event(
            app, sample_data['event_id'], activity_type='Magistral', name='Magistral 2')
        t = create_activity_for_event(
            app, sample_data['event_id'], activity_type='Taller', name='Taller 2')

        # Llamada con for_student=true -> magistral debe estar excluida
        resp = client.get(
            f"/api/activities/?event_id={sample_data['event_id']}&per_page=10&for_student=true")
        assert resp.status_code == 200
        data = resp.get_json()
        types = [a['activity_type'] for a in data.get('activities', [])]
        assert 'Magistral' not in types
        assert 'Taller' in types


def test_exclude_types_query_param(app, client, sample_data):
    with app.app_context():
        # Crear varias actividades de distintos tipos
        m = create_activity_for_event(
            app, sample_data['event_id'], activity_type='Magistral', name='Magistral 3')
        c = create_activity_for_event(
            app, sample_data['event_id'], activity_type='Conferencia', name='Conf 1')
        t = create_activity_for_event(
            app, sample_data['event_id'], activity_type='Taller', name='Taller 3')

        # Excluir explícitamente 'Conferencia' y 'Taller'
        resp = client.get(
            f"/api/activities/?event_id={sample_data['event_id']}&per_page=10&exclude_types=Conferencia,Taller")
        assert resp.status_code == 200
        data = resp.get_json()
        types = [a['activity_type'] for a in data.get('activities', [])]
        assert 'Conferencia' not in types
        assert 'Taller' not in types
        # Magistral permanece porque no se pasó for_student
        assert 'Magistral' in types
