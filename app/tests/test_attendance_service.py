# app/tests/test_attendance_service.py
import pytest
from datetime import datetime, timedelta, timezone
from app import db
from app.models.activity import Activity
from app.models.attendance import Attendance
from app.models.student import Student
from app.services.attendance_service import (
    calculate_attendance_percentage,
    pause_attendance,
    resume_attendance,
    calculate_net_duration_seconds
)

# --- Fixtures específicos para estos tests ---
# Creamos fixtures que crean y devuelven objetos DENTRO del contexto de uso


@pytest.fixture
def setup_attendance_test_data(app, sample_data):
    """Crea un estudiante, una actividad y una asistencia para tests de asistencia."""
    with app.app_context():
        # El estudiante y evento ya existen gracias a sample_data
        # Creamos una nueva actividad para este test específico
        activity = Activity(
            event_id=sample_data['event_id'],
            department='TEST',
            name='Actividad de Prueba para Asistencia',
            description='Descripción de prueba',
            start_datetime=datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc),
            duration_hours=1.0,
            activity_type='Magistral',
            location='Auditorio de Prueba',
            modality='Presencial'
        )
        db.session.add(activity)
        db.session.flush()  # Para obtener activity.id sin hacer commit

        # Creamos la asistencia
        attendance = Attendance(
            student_id=sample_data['student_id'],
            activity_id=activity.id
        )
        db.session.add(attendance)
        db.session.commit()

        # Devolvemos los IDs para usarlos en los tests
        return {
            'student_id': sample_data['student_id'],
            'activity_id': activity.id,
            'attendance_id': attendance.id
        }

# --- Tests para calculate_attendance_percentage ---


def test_calculate_attendance_percentage_full_attendance(app, setup_attendance_test_data):
    """Test calcular porcentaje para asistencia completa."""
    with app.app_context():
        attendance_id = setup_attendance_test_data['attendance_id']

        # Simular check-in y check-out completos
        attendance = db.session.get(Attendance, attendance_id)
        attendance.check_in_time = datetime(
            2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        attendance.check_out_time = datetime(
            2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc)  # 1 hora exacta
        db.session.commit()

        # Calcular porcentaje
        percentage = calculate_attendance_percentage(attendance_id)

        # Verificar resultados
        assert percentage == 100.0
        updated_attendance = db.session.get(Attendance, attendance_id)
        assert updated_attendance.attendance_percentage == 100.0
        assert updated_attendance.status == 'Asistió'


def test_calculate_attendance_percentage_partial_attendance(app, setup_attendance_test_data):
    """Test calcular porcentaje para asistencia parcial."""
    with app.app_context():
        attendance_id = setup_attendance_test_data['attendance_id']

        attendance = db.session.get(Attendance, attendance_id)
        attendance.check_in_time = datetime(
            2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        attendance.check_out_time = datetime(
            2024, 1, 1, 10, 30, 0, tzinfo=timezone.utc)  # 30 minutos
        db.session.commit()

        percentage = calculate_attendance_percentage(attendance_id)

        assert percentage == 50.0
        updated_attendance = db.session.get(Attendance, attendance_id)
        assert updated_attendance.attendance_percentage == 50.0
        # Ajusta la assertion según tu lógica de umbral
        assert updated_attendance.status in ['Parcial', 'Asistió']

# --- Tests para pause_attendance y resume_attendance ---


def test_pause_attendance_valid(app, setup_attendance_test_data):
    """Test pausar una asistencia válida."""
    with app.app_context():
        attendance_id = setup_attendance_test_data['attendance_id']

        attendance = db.session.get(Attendance, attendance_id)
        attendance.check_in_time = datetime(
            2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        db.session.commit()

        paused_attendance = pause_attendance(attendance_id)

        assert paused_attendance.is_paused is True
        assert paused_attendance.pause_time is not None


def test_resume_attendance_valid(app, setup_attendance_test_data):
    """Test reanudar una asistencia pausada."""
    with app.app_context():
        attendance_id = setup_attendance_test_data['attendance_id']

        attendance = db.session.get(Attendance, attendance_id)
        attendance.check_in_time = datetime(
            2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        attendance.is_paused = True
        attendance.pause_time = datetime(
            2024, 1, 1, 10, 15, 0, tzinfo=timezone.utc)
        db.session.commit()

        resumed_attendance = resume_attendance(attendance_id)

        assert resumed_attendance.is_paused is False
        assert resumed_attendance.resume_time is not None

# --- Tests para calculate_net_duration_seconds ---


def test_calculate_net_duration_seconds_no_pauses(app, setup_attendance_test_data):
    """Test calcular duración neta sin pausas."""
    with app.app_context():
        attendance_id = setup_attendance_test_data['attendance_id']

        attendance = db.session.get(Attendance, attendance_id)
        attendance.check_in_time = datetime(
            2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        attendance.check_out_time = datetime(
            2024, 1, 1, 10, 30, 0, tzinfo=timezone.utc)  # 30 minutos

        net_duration = calculate_net_duration_seconds(attendance)

        expected_duration = 30 * 60  # 30 minutos en segundos
        assert net_duration == expected_duration

# --- Tests de integración para calculate_attendance_percentage con pausas ---


def test_calculate_attendance_percentage_with_pauses(app, setup_attendance_test_data):
    """Test calcular porcentaje considerando pausas."""
    with app.app_context():
        attendance_id = setup_attendance_test_data['attendance_id']

        attendance = db.session.get(Attendance, attendance_id)
        attendance.check_in_time = datetime(
            2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        attendance.pause_time = datetime(
            2024, 1, 1, 10, 20, 0, tzinfo=timezone.utc)  # Pausa a los 20 mins
        attendance.resume_time = datetime(
            2024, 1, 1, 10, 35, 0, tzinfo=timezone.utc)  # Reanuda a los 35 mins
        attendance.check_out_time = datetime(
            2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc)  # Termina a la 1hr
        db.session.commit()

        percentage = calculate_attendance_percentage(attendance_id)

        # Duración esperada: 3600 seg
        # Tiempo pausado: 15 minutos = 900 segundos
        # Duración neta: 3600 - 900 = 2700 segundos
        # Porcentaje: (2700 / 3600) * 100 = 75.0
        assert round(percentage, 2) == 75.0
        updated_attendance = db.session.get(Attendance, attendance_id)
        assert round(updated_attendance.attendance_percentage, 2) == 75.0
        # Ajusta según tu lógica de umbral
        assert updated_attendance.status in ['Parcial', 'Asistió']

# --- Tests para errores ---


def test_pause_attendance_already_paused(app, setup_attendance_test_data):
    """Test intentar pausar una asistencia ya pausada."""
    with app.app_context():
        attendance_id = setup_attendance_test_data['attendance_id']

        attendance = db.session.get(Attendance, attendance_id)
        attendance.check_in_time = datetime(
            2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        attendance.is_paused = True
        attendance.pause_time = datetime(
            2024, 1, 1, 10, 15, 0, tzinfo=timezone.utc)
        db.session.commit()

        with pytest.raises(ValueError, match="La asistencia ya está pausada"):
            pause_attendance(attendance_id)


def test_resume_attendance_not_paused(app, setup_attendance_test_data):
    """Test intentar reanudar una asistencia no pausada."""
    with app.app_context():
        attendance_id = setup_attendance_test_data['attendance_id']

        attendance = db.session.get(Attendance, attendance_id)
        attendance.check_in_time = datetime(
            2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        # No se pausa
        db.session.commit()

        with pytest.raises(ValueError, match="La asistencia no está pausada"):
            resume_attendance(attendance_id)
