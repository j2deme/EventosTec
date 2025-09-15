import pytest
import json
from datetime import datetime


def test_create_registration(client, auth_headers, sample_data):
    from app import db
    from app.models.activity import Activity

    with client.application.app_context():
        activity = Activity(
            event_id=sample_data['event_id'],
            department='ISC',
            name='Taller de prueba',
            start_datetime=datetime(2024, 1, 1, 10, 0, 0),
            end_datetime=datetime(2024, 1, 1, 11, 0, 0),
            duration_hours=1.0,
            activity_type='Taller',
            location='Laboratorio A',
            modality='Presencial',
            max_capacity=10
        )
        db.session.add(activity)
        db.session.commit()
        activity_id = activity.id

    registration_data = {
        'student_id': sample_data['student_id'],
        'activity_id': activity_id
    }

    response = client.post('/api/registrations/',
                           headers=auth_headers,
                           json=registration_data)

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data['message'] == 'Preregistro creado exitosamente'
