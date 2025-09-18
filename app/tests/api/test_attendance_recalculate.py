import pytest
from datetime import datetime, timezone, timedelta


def test_recalculate_attendance(client, auth_headers, sample_data):
    from app import db
    from app.models.activity import Activity
    from app.models.attendance import Attendance

    with client.application.app_context():
        # Crear actividad de 2 horas via API para respetar serialización/validación
        start = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        end = start + timedelta(hours=2)
        activity_payload = {
            'event_id': sample_data['event_id'],
            'department': 'ISC',
            'name': 'Actividad para recalcular',
            'description': 'desc',
            'start_datetime': start.isoformat(),
            'end_datetime': end.isoformat(),
            'duration_hours': 2.0,
            'activity_type': 'Taller',
            'location': 'Aula X',
            'modality': 'Presencial'
        }

        resp = client.post('/api/activities/',
                           headers=auth_headers, json=activity_payload)
        assert resp.status_code == 201
        act_body = resp.get_json()
        activity_id = act_body['activity']['id']

        # Crear asistencia con check_in y check_out directamente en DB
        att = Attendance()
        att.student_id = sample_data['student_id']
        att.activity_id = activity_id
        att.check_in_time = start
        att.check_out_time = start + timedelta(hours=1)  # asistió 1 hora de 2
        att.attendance_percentage = 0.0
        att.status = 'Asistió'  # marcado manualmente inicialmente
        db.session.add(att)
        db.session.commit()
        att_id = att.id

    # Llamar endpoint de recálculo
    res = client.post(
        f'/api/attendances/{att_id}/recalculate', headers=auth_headers)
    assert res.status_code == 200
    body = res.get_json()
    assert 'attendance' in body
    att_body = body['attendance']
    # Debería haber recalculado al 50% y puesto status 'Parcial' o 'Asistió' según umbral
    assert 'attendance_percentage' in att_body
    assert att_body['attendance_percentage'] == 50.0
    assert att_body['status'] in ('Parcial', 'Asistió')
