def test_attendance_list_requires_auth(client):
    """Test que attendance_list requiere autenticación."""
    response = client.get("/api/reports/attendance_list?activity_id=1")

    assert response.status_code == 401


def test_attendance_list_requires_activity_id(client, auth_headers):
    """Test que attendance_list requiere activity_id."""
    response = client.get("/api/reports/attendance_list", headers=auth_headers)

    assert response.status_code == 400


def test_attendance_list_activity_not_found(client, auth_headers):
    """Test attendance_list con actividad inexistente."""
    response = client.get(
        "/api/reports/attendance_list?activity_id=999999", headers=auth_headers
    )

    assert response.status_code == 404


def test_attendance_list_renders_with_preregistered(
    client, auth_headers, app, sample_data
):
    """La plantilla se renderiza (200) con los preregistrados de la actividad."""
    from datetime import datetime

    from app import db
    from app.models.activity import Activity
    from app.models.registration import Registration

    with app.app_context():
        activity = Activity(
            event_id=sample_data["event_id"],
            name="Magistral Render",
            department="TEST",
            start_datetime=datetime(2026, 1, 10, 9, 0, 0),
            end_datetime=datetime(2026, 1, 10, 11, 0, 0),
            duration_hours=2.0,
            activity_type="Magistral",
            location="Aula 1",
            modality="Presencial",
        )
        db.session.add(activity)
        db.session.commit()

        db.session.add(
            Registration(
                student_id=sample_data["student_id"],
                activity_id=activity.id,
                status="Registrado",
            )
        )
        db.session.commit()
        activity_id = activity.id

    response = client.get(
        f"/api/reports/attendance_list?activity_id={activity_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Magistral Render" in html
    # Estudiante del fixture sample_data (Juan Pérez)
    assert "Juan Pérez" in html
    assert "Asistencia" in html


def test_participation_matrix_semester_uses_local_reference_date(
    client, auth_headers, app, sample_data
):
    """El semestre se calcula con la referencia en hora local, no en UTC.

    Regresión: ``ref_date`` era ``datetime.now(timezone.utc)`` y las ramas de
    actividad/evento conservaban el aware-UTC de ``localize_naive_datetime()``,
    así que ``ref_date.month``/``.year`` leían el mes en UTC. Un evento del
    31/12 a las 20:00 locales cae al 01/01 en UTC y terminaba en el semestre
    equivocado.
    """
    from datetime import datetime

    from app import db
    from app.models.activity import Activity
    from app.models.event import Event
    from app.models.registration import Registration

    with app.app_context():
        event = Event(
            name="Evento borde de año",
            description="31/12 por la noche",
            start_date=datetime(2026, 12, 31, 20, 0, 0),
            end_date=datetime(2026, 12, 31, 23, 0, 0),
            is_active=True,
        )
        db.session.add(event)
        db.session.flush()

        activity = Activity(
            event_id=event.id,
            department="ISC",
            name="Charla de cierre",
            description="Borde de año",
            start_datetime=datetime(2026, 12, 31, 20, 0, 0),
            end_datetime=datetime(2026, 12, 31, 22, 0, 0),
            duration_hours=2.0,
            activity_type="Conferencia",
            location="Aula 1",
            modality="Presencial",
        )
        db.session.add(activity)
        db.session.flush()

        db.session.add(
            Registration(
                student_id=sample_data["student_id"],
                activity_id=activity.id,
                status="Confirmado",
            )
        )
        db.session.commit()
        event_id = event.id

    # Misma aritmética que el endpoint pero con la referencia en hora local
    # (las columnas datetime guardan wall-time local, no UTC).
    # sample_data: control "12345678" -> generación 12 -> ingreso 2012.
    local_start = datetime(2026, 12, 31, 20, 0, 0)
    ingreso_year = 2000 + 12
    offset = 1 if 8 <= local_start.month <= 12 else 2
    expected_semester = str((local_start.year - ingreso_year) * 2 + offset)

    response = client.get(
        f"/api/reports/participation_matrix?event_id={event_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["semesters"] == [expected_semester]
    assert data["matrix_headers"] == [expected_semester]
    assert data["grandTotal"] == 1


def test_participation_matrix_default_reference_is_local_today(
    client, auth_headers, app, sample_data
):
    """Sin event_id/activity_id la referencia es hoy en APP_TIMEZONE."""
    from datetime import datetime

    from app import db
    from app.models.activity import Activity
    from app.models.event import Event
    from app.models.registration import Registration
    from app.utils.datetime_utils import app_today

    with app.app_context():
        event = Event(
            name="Evento vigente",
            description="Para tener dónde anclar la actividad",
            start_date=datetime(2026, 1, 5, 9, 0, 0),
            end_date=datetime(2026, 1, 5, 17, 0, 0),
            is_active=True,
        )
        db.session.add(event)
        db.session.flush()

        activity = Activity(
            event_id=event.id,
            department="ISC",
            name="Actividad vigente",
            description="Cualquiera",
            start_datetime=datetime(2026, 1, 5, 9, 0, 0),
            end_datetime=datetime(2026, 1, 5, 11, 0, 0),
            duration_hours=2.0,
            activity_type="Taller",
            location="Aula 1",
            modality="Presencial",
        )
        db.session.add(activity)
        db.session.flush()

        db.session.add(
            Registration(
                student_id=sample_data["student_id"],
                activity_id=activity.id,
                status="Confirmado",
            )
        )
        db.session.commit()

        today = app_today()
        ingreso_year = 2000 + 12  # control "12345678" -> generación 12
        offset = 1 if 8 <= today.month <= 12 else 2
        expected_semester = str((today.year - ingreso_year) * 2 + offset)

    response = client.get("/api/reports/participation_matrix", headers=auth_headers)

    assert response.status_code == 200
    data = response.get_json()
    assert data["semesters"] == [expected_semester]
