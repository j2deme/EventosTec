# app/tests/test_integration_flows.py
import pytest
from datetime import datetime
from app import db
from app.models.activity import Activity
from app.models.attendance import Attendance

# Asegúrate de que esta función exista
from app.services.attendance_service import create_related_attendances


def test_full_attendance_flow_with_pause(app, sample_data):
    """Test de un flujo completo de asistencia con pausa."""
    with app.app_context():
        # Crear actividad
        activity = Activity(
            event_id=sample_data["event_id"],
            department="TEST",
            name="Flujo completo con pausa",
            start_datetime=datetime(2024, 1, 1, 10, 0, 0),
            end_datetime=datetime(2024, 1, 1, 11, 0, 0),
            duration_hours=1.0,
            activity_type="Magistral",
            location="Auditorio Test",
            modality="Presencial",
        )
        db.session.add(activity)
        db.session.commit()

        student_id = sample_data["student_id"]
        activity_id = activity.id

        # 1. Crear registro de asistencia (simulando check-in)
        attendance = Attendance(
            student_id=student_id,
            activity_id=activity_id,
            check_in_time=datetime(2024, 1, 1, 10, 0, 0),
        )
        db.session.add(attendance)
        db.session.commit()

        # 2. Pausa
        from app.services.attendance_service import pause_attendance

        attendance = pause_attendance(attendance.id)
        assert attendance.is_paused is True

        # 3. Reanuda
        from app.services.attendance_service import resume_attendance

        attendance = resume_attendance(attendance.id)
        assert attendance.is_paused is False

        # 4. Check-out
        attendance.check_out_time = datetime(2024, 1, 1, 11, 0, 0)
        db.session.commit()

        # 5. Calcular porcentaje (esto también se hace en check_out normalmente)
        from app.services.attendance_service import calculate_attendance_percentage

        percentage = calculate_attendance_percentage(attendance.id)

        # Verificar resultado final
        assert percentage is not None
        # Ajusta la assertion según tu lógica
        assert attendance.status in ["Asistió", "Parcial"]


# --- Test para asistencias relacionadas ---
# Este test requiere que la relación esté correctamente configurada en el modelo
# y que la función create_related_attendances esté implementada.


def test_create_related_attendances(app, sample_data):
    """Test que al asistir a una actividad, se crean asistencias para las relacionadas."""
    with app.app_context():
        # Crear dos actividades magistrales
        activity_a = Activity(
            event_id=sample_data["event_id"],
            department="TEST",
            name="Magistral A",
            start_datetime=datetime(2024, 1, 1, 10, 0, 0),
            end_datetime=datetime(2024, 1, 1, 11, 0, 0),
            duration_hours=1.0,
            activity_type="Magistral",
            location="Auditorio A",
            modality="Presencial",
        )
        activity_b = Activity(
            event_id=sample_data["event_id"],
            department="TEST",
            name="Magistral B",
            start_datetime=datetime(2024, 1, 1, 11, 30, 0),
            end_datetime=datetime(2024, 1, 1, 12, 30, 0),
            duration_hours=1.0,
            activity_type="Magistral",
            location="Auditorio B",
            modality="Presencial",
        )
        db.session.add_all([activity_a, activity_b])
        db.session.flush()  # Para obtener los IDs

        # --- Configurar la relación ---
        # Suponiendo que tu modelo tiene una relación many-to-many como:
        # related_activities = db.relationship(
        #     'Activity',
        #     secondary='activity_relations',
        #     primaryjoin='Activity.id==activity_relations.c.activity_id',
        #     secondaryjoin='Activity.id==activity_relations.c.related_activity_id',
        #     backref='related_to_activities'
        # )
        # Y la tabla de asociación activity_relations existe.
        # Para agregar la relación, simplemente la agregamos a la lista:
        activity_a.related_activities.append(activity_b)
        db.session.commit()

        student_id = sample_data["student_id"]
        activity_a_id = activity_a.id

        # Crear asistencia principal a A (simulando un check-in/check-out completo)
        attendance_a = Attendance(
            student_id=student_id,
            activity_id=activity_a_id,
            check_in_time=datetime(2024, 1, 1, 10, 0, 0),
            check_out_time=datetime(2024, 1, 1, 11, 0, 0),
            attendance_percentage=100.0,
            status="Asistió",
        )
        db.session.add(attendance_a)
        db.session.commit()

        # --- Llamar a la función que crea asistencias relacionadas ---
        # Asumimos que la función existe y funciona así.
        # Si hay un error aquí, revisa la implementación de create_related_attendances
        try:
            create_related_attendances(student_id, activity_a_id)
            # No necesitamos hacer commit explícito si la función lo hace
            # pero es bueno asegurarse de que los cambios son visibles
            db.session.commit()
        except Exception as e:
            pytest.fail(f"Error al crear asistencias relacionadas: {e}")

        # Verificar que se creó la asistencia para B
        attendance_b = (
            db.session.query(Attendance)
            .filter_by(student_id=student_id, activity_id=activity_b.id)
            .first()
        )

        assert attendance_b is not None, (
            "No se creó la asistencia para la actividad relacionada B"
        )
        # Verificar que se haya marcado como asistida automáticamente
        # Ajusta estas assertions según la lógica de tu implementación
        assert attendance_b.attendance_percentage == 100.0
        assert attendance_b.status == "Asistió"
