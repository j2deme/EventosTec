import pytest
import json
from datetime import datetime


def test_create_event(client, auth_headers):
    """Test de creación de evento"""
    event_data = {
        'name': 'Nuevo Evento',
        'description': 'Descripción del evento',
        'start_date': '2024-01-01T09:00:00',
        'end_date': '2024-01-01T17:00:00',
        'is_active': True
    }

    response = client.post('/api/events/',
                           headers=auth_headers,
                           json=event_data)

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data['event']['name'] == 'Nuevo Evento'


def test_get_events(client):
    """Test de obtención de eventos"""
    response = client.get('/api/events/')

    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'events' in data


def test_get_event_by_id(client, sample_data):
    """Test de obtención de evento por ID"""
    event_id = sample_data['event_id']

    response = client.get(f'/api/events/{event_id}')

    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'event' in data
