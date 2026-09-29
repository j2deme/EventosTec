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
