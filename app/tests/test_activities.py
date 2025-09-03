import pytest
import json
from datetime import datetime


def test_create_activity(client, auth_headers, sample_data):
    """Test de creación de actividad"""
    activity_data = {
        'event_id': sample_data['event_id'],
        'department': 'ISC',
        'name': 'Conferencia de prueba',
        'description': 'Descripción',
        'start_datetime': '2024-01-01T10:00:00',
        'end_datetime': '2024-01-01T11:00:00',
        'duration_hours': 1.0,
        'activity_type': 'Conferencia',
        'location': 'Auditorio A',
        'modality': 'Presencial',
        'max_capacity': 50
    }

    response = client.post('/api/activities/',
                           headers=auth_headers,
                           json=activity_data)

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data['activity']['name'] == 'Conferencia de prueba'


def test_create_activity_invalid_event(client, auth_headers):
    """Test de creación de actividad con evento inválido"""
    activity_data = {
        'event_id': 99999,  # ID que no existe
        'department': 'ISC',
        'name': 'Conferencia de prueba',
        'start_datetime': '2024-01-01T10:00:00',
        'end_datetime': '2024-01-01T11:00:00',
        'duration_hours': 1.0,
        'activity_type': 'Conferencia',
        'location': 'Auditorio A',
        'modality': 'Presencial'
    }

    response = client.post('/api/activities/',
                           headers=auth_headers,
                           json=activity_data)

    assert response.status_code == 404
