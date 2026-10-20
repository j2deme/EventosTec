"""Guard contra N+1 en los listados del panel de admin.

Motivo: medido contra la BD de producción el día de la etiqueta v1.0.0, el
listado de estudiantes hacía **99 consultas** por página de 25 filas (~12 s) y
el de asistencias **113** (~13 s); el de preregistros, 71, y la lista
imprimible, 39. El coste crece LINEALMENTE con las filas devueltas, y una
carga perezosa reintroducida por accidente no rompe nada visible: solo
ralentiza el panel en silencio, y nadie se entera hasta que hay producción
encima.

Por eso aquí se fija un PRESUPUESTO de consultas por petición. El presupuesto
es constante, no proporcional a las filas: con las 10 filas de este test,
cargar bien las relaciones cuesta ~8 consultas, y el mismo código con N+1 se
iría a 20 o más. Si alguien añade un atributo anidado a un schema sin
precargarlo, este test avisa.
"""

from datetime import datetime

import pytest
from sqlalchemy import event

from app import db
from app.models.activity import Activity
from app.models.attendance import Attendance
from app.models.event import Event
from app.models.registration import Registration
from app.models.student import Student

NUM_FILAS = 10


@pytest.fixture
def pagina_llena(app):
    """Crea NUM_FILAS estudiantes, cada uno con preregistro y asistencia."""
    with app.app_context():
        evento = Event(
            name="Evento presupuesto",
            start_date=datetime(2026, 1, 1, 9, 0, 0),
            end_date=datetime(2026, 1, 3, 17, 0, 0),
            is_active=True,
        )
        db.session.add(evento)
        db.session.flush()

        actividad = Activity(
            event_id=evento.id,
            department="ISC",
            name="Actividad presupuesto",
            start_datetime=datetime(2026, 1, 2, 10, 0, 0),
            end_datetime=datetime(2026, 1, 2, 12, 0, 0),
            duration_hours=2.0,
            activity_type="Taller",
            location="Salón 1",
            modality="Presencial",
        )
        db.session.add(actividad)
        db.session.flush()

        for i in range(NUM_FILAS):
            estudiante = Student(
                control_number=f"2669{i:04d}",
                full_name=f"Estudiante Presupuesto {i:02d}",
                career="Ingeniería en Desarrollo de Aplicaciones",
                email=f"2669{i:04d}@tecvalles.mx",
            )
            db.session.add(estudiante)
            db.session.flush()

            db.session.add(
                Registration(
                    student_id=estudiante.id,
                    activity_id=actividad.id,
                    status="Confirmado",
                )
            )
            db.session.add(
                Attendance(
                    student_id=estudiante.id,
                    activity_id=actividad.id,
                    check_in_time=datetime(2026, 1, 2, 10, 0, 0),
                    check_out_time=datetime(2026, 1, 2, 12, 0, 0),
                    attendance_percentage=100.0,
                    status="Asistió",
                )
            )

        db.session.commit()
        return {"event_id": evento.id, "activity_id": actividad.id}


@pytest.fixture
def contar_consultas(app):
    """Devuelve una función que ejecuta una petición y cuenta sus consultas."""

    def _medir(client, path, headers=None):
        statements: list[str] = []

        def _after(conn, cursor, statement, params, context, executemany):
            statements.append(statement)

        engine = db.engine
        event.listen(engine, "after_cursor_execute", _after)
        try:
            response = client.get(path, headers=headers or {})
        finally:
            event.remove(engine, "after_cursor_execute", _after)

        return response, len(statements)

    return _medir


@pytest.mark.parametrize(
    "path, presupuesto, campo_filas",
    [
        # Medidos con la corrección aplicada: 7, 9 y 8 consultas respectivamente
        # contra producción (páginas de 25-50 filas). El presupuesto deja margen
        # para que una consulta de más no rompa el test, pero no para un N+1.
        ("/api/students/?per_page=10", 12, "students"),
        ("/api/attendances/?page=1&per_page=10", 15, "attendances"),
        ("/api/registrations/?page=1&per_page=10", 12, "registrations"),
    ],
)
def test_listado_admin_cabe_en_el_presupuesto_de_consultas(
    client, auth_headers, contar_consultas, pagina_llena, path, presupuesto, campo_filas
):
    """Un listado de admin debe salir en un número CONSTANTE de consultas."""
    response, consultas = contar_consultas(client, path, auth_headers)

    assert response.status_code == 200, response.get_data(as_text=True)[:300]

    filas = response.get_json().get(campo_filas) or []
    assert len(filas) == NUM_FILAS, (
        f"{path} devolvió {len(filas)} filas y se esperaban {NUM_FILAS}: "
        "la carga ansiosa no puede perder datos"
    )

    assert consultas <= presupuesto, (
        f"{path} hizo {consultas} consultas SQL para {NUM_FILAS} filas "
        f"(presupuesto: {presupuesto}). Es el síntoma clásico de N+1: una "
        "consulta por fila en vez de precargar la relación con "
        "selectinload/joinedload."
    )


def test_lista_imprimible_cabe_en_el_presupuesto_de_consultas(
    client, auth_headers, contar_consultas, pagina_llena
):
    """La lista imprimible también consultaba un estudiante por fila."""
    activity_id = pagina_llena["activity_id"]

    response, consultas = contar_consultas(
        client, f"/api/reports/attendance_list?activity_id={activity_id}", auth_headers
    )

    assert response.status_code == 200, response.get_data(as_text=True)[:300]
    html = response.get_data(as_text=True)
    assert "Estudiante Presupuesto 00" in html, "la lista no incluye a los estudiantes"

    assert consultas <= 10, (
        f"attendance_list hizo {consultas} consultas para {NUM_FILAS} filas "
        "(presupuesto: 10); un estudiante por consulta es N+1."
    )


def test_listado_de_estudiantes_con_filtros_tambien_respeta_el_presupuesto(
    client, auth_headers, contar_consultas, pagina_llena
):
    """Las rutas con filtro (búsqueda, evento, actividad) también estaban
    tocadas por el mismo patrón y son las que más se usan desde el panel."""
    for path in (
        "/api/students/?per_page=10&search=Presupuesto",
        f"/api/students/?per_page=10&event_id={pagina_llena['event_id']}",
        f"/api/students/?per_page=10&activity_id={pagina_llena['activity_id']}",
    ):
        response, consultas = contar_consultas(client, path, auth_headers)
        assert response.status_code == 200, path
        assert consultas <= 12, f"{path} hizo {consultas} consultas (presupuesto: 12)"
