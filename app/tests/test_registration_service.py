# app/tests/test_registration_service.py
import pytest
from datetime import datetime
from app import db
from app.models.activity import Activity
from app.models.student import Student
from app.models.registration import Registration
from app.services.registration_service import is_registration_allowed

# --- Tests para is_registration_allowed ---


def test_is_registration_allowed_magistral(app, sample_data):
    """Test que siempre se permite registro en actividades magistrales."""
    with app.app_context():
        # Crear actividad magistral usando objetos datetime
        activity = Activity(
            event_id=sample_data['event_id'],
            department='TEST',
            name='Magistral sin cupo',
            start_datetime=datetime(2024, 1, 1, 10, 0, 0),  # Objeto datetime
            end_datetime=datetime(2024, 1, 1, 11, 0, 0),   # Objeto datetime
            duration_hours=1.0,
            activity_type='Magistral',
            location='Auditorio',
            modality='Presencial',
            max_capacity=1  # Aunque tenga cupo, magistral siempre permite
        )
        db.session.add(activity)
        db.session.commit()

        allowed = is_registration_allowed(activity.id)
        assert allowed is True


def test_is_registration_allowed_conference_no_capacity_limit(app, sample_data):
    """Test que se permite registro si no hay límite de cupo."""
    with app.app_context():
        activity = Activity(
            event_id=sample_data['event_id'],
            department='TEST',
            name='Conferencia sin limite',
            start_datetime=datetime(2024, 1, 1, 10, 0, 0),
            end_datetime=datetime(2024, 1, 1, 11, 0, 0),
            duration_hours=1.0,
            activity_type='Conferencia',
            location='Sala A',
            modality='Presencial',
            max_capacity=None  # Sin límite
        )
        db.session.add(activity)
        db.session.commit()

        allowed = is_registration_allowed(activity.id)
        assert allowed is True


def test_is_registration_allowed_taller_with_capacity_available(app, sample_data):
    """Test que se permite registro si hay cupo disponible."""
    with app.app_context():
        activity = Activity(
            event_id=sample_data['event_id'],
            department='TEST',
            name='Taller con cupo',
            start_datetime=datetime(2024, 1, 1, 10, 0, 0),
            end_datetime=datetime(2024, 1, 1, 11, 0, 0),
            duration_hours=1.0,
            activity_type='Taller',
            location='Lab 1',
            modality='Presencial',
            max_capacity=3  # Cupo para 3
        )
        db.session.add(activity)
        db.session.flush()  # Obtener ID

        # Crear solo 1 preregistro
        registration = Registration(
            student_id=sample_data['student_id'],
            activity_id=activity.id,
            status='registered'
        )
        db.session.add(registration)
        db.session.commit()

        allowed = is_registration_allowed(activity.id)
        assert allowed is True


def test_is_registration_allowed_curso_capacity_full(app, sample_data):
    """Test que se niega registro si el cupo está lleno."""
    with app.app_context():
        activity = Activity(
            event_id=sample_data['event_id'],
            department='TEST',
            name='Curso lleno',
            start_datetime=datetime(2024, 1, 1, 10, 0, 0),  # Objeto datetime
            end_datetime=datetime(2024, 1, 1, 11, 0, 0),   # Objeto datetime
            duration_hours=1.0,
            activity_type='Curso',
            location='Lab 2',
            modality='Presencial',
            max_capacity=2  # Cupo para 2
        )
        db.session.add(activity)
        db.session.flush()  # Obtener ID

        # Crear 2 preregistros, llenando el cupo
        # Necesitamos crear estudiantes adicionales
        for i in range(2):
            student = Student(
                control_number=f'FULL{i}',
                full_name=f'Estudiante Lleno {i}',
                career='Sistemas'
            )
            db.session.add(student)
            db.session.flush()  # Para obtener el ID del estudiante
            reg = Registration(
                student_id=student.id,
                activity_id=activity.id,
                status='Registrado'
            )
            db.session.add(reg)

        db.session.commit()

        # Opcional: Verificar que los registros se crearon
        regs = Registration.query.filter_by(activity_id=activity.id).all()
        assert len(regs) == 2

        # Intentar registrar a un tercer estudiante (usando el student_id de sample_data)
        allowed = is_registration_allowed(activity.id)
        assert allowed is False, f"Se esperaba False, pero se obtuvo {allowed}. ¿Se crearon correctamente los 2 preregistros?"


def test_is_registration_allowed_activity_not_found(app):
    """Test manejo de error si la actividad no existe."""
    with app.app_context():
        non_existent_id = 99999
        with pytest.raises(ValueError, match="Actividad no encontrada"):
            is_registration_allowed(non_existent_id)
