import json
from app import db
from app.models.activity import Activity
from app.models.registration import Registration
from app.models.attendance import Attendance
from datetime import datetime, timezone


def test_delete_attendance_reverts_registration(client, auth_headers, sample_data, app):
    with app.app_context():
        # Crear actividad
        activity = Activity(
            name='Actividad Test',
            event_id=sample_data['event_id'],
            department='Departamento Test',
            start_datetime=datetime(2024, 1, 1, 10, 0, 0),
            end_datetime=datetime(2024, 1, 1, 12, 0, 0),
            duration_hours=2.0,
            activity_type='Taller',
            location='Aula 1',
            modality='Presencial',
            max_capacity=50
        )
        db.session.add(activity)
        db.session.commit()

        # Crear preregistro y marcar attended True
        registration = Registration(
            student_id=sample_data['student_id'],
            activity_id=activity.id,
            status='Asistió',
            attended=True,
            confirmation_date=db.func.now()
        )
        db.session.add(registration)
        db.session.commit()

        # Crear attendance asociado
        attendance = Attendance(
            student_id=sample_data['student_id'],
            activity_id=activity.id,
            attendance_percentage=100.0,
            status='Asistió',
            check_in_time=datetime.now(timezone.utc),
            check_out_time=datetime.now(timezone.utc)
        )
        db.session.add(attendance)
        db.session.commit()

        # Llamar al endpoint DELETE
        res = client.delete(
            f"/api/attendances/{attendance.id}", headers=auth_headers)
        assert res.status_code == 200
        data = json.loads(res.data)
        assert data['message'] == 'Asistencia eliminada exitosamente'

        # Verificar que el attendance fue borrado
        att = db.session.get(Attendance, attendance.id)
        assert att is None

        # Verificar que el preregistro fue revertido a 'Registrado' y attended False
        reg = db.session.get(Registration, registration.id)
        assert reg is not None
        assert reg.attended is False
        assert reg.confirmation_date is None
        assert reg.status == 'Registrado'


def test_delete_attendance_not_found_returns_404(client, auth_headers, app):
    # Intentar borrar un attendance que no existe
    res = client.delete('/api/attendances/9999', headers=auth_headers)
    assert res.status_code == 404
    data = json.loads(res.data)
    assert 'Asistencia no encontrada' in data.get('message', '')
