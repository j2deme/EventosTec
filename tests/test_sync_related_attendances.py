import json
from datetime import datetime, timezone


def test_sync_related_dry_run_and_execute(client, auth_headers, sample_data, app):
    """Verifica dry-run y ejecución real de la sincronización de actividades relacionadas.

    Nueva semántica: la actividad seleccionada en el formulario se interpreta
    como receptora si tiene un enlace saliente (B -> A). En ese caso la
    sincronización toma la actividad hacia la que B apunta como fuente y
    limita el target a B.
    """
    from app import db
    from app.models.activity import Activity
    from app.models.attendance import Attendance
    from app.models.student import Student

    # Crear actividades y asistencias dentro del contexto de la app
    with app.app_context():
        # Actividad fuente A
        a = Activity()
        a.name = "Actividad A"
        a.activity_type = "Magistral"
        a.department = "General"
        a.duration_hours = 1
        a.event_id = sample_data.get("event_id")
        a.start_datetime = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        a.end_datetime = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        a.location = "Sala 1"
        a.modality = "Presencial"
        db.session.add(a)

        # Actividad receptora B (apunta a A)
        b = Activity()
        b.name = "Actividad B"
        b.activity_type = "Magistral"
        b.department = "General"
        b.duration_hours = 1
        b.event_id = sample_data.get("event_id")
        b.start_datetime = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        b.end_datetime = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        b.location = "Sala 1"
        b.modality = "Presencial"
        db.session.add(b)
        db.session.commit()

        # Relacionar B -> A (B apunta a A)
        b.related_activities.append(a)
        db.session.add(b)
        db.session.commit()

        # Crear asistencia en A para el estudiante fixture
        att = Attendance()
        att.student_id = sample_data["student_id"]
        att.activity_id = a.id
        att.check_in_time = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        att.check_out_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        db.session.add(att)
        db.session.commit()
        # Guardar ids antes de salir del contexto para evitar DetachedInstanceError
        a_id = a.id
        b_id = b.id
    # Dry-run: preview only — el admin selecciona B (receptora)
    res = client.post(
        "/api/attendances/sync-related",
        headers=auth_headers,
        data=json.dumps({"source_activity_id": b_id, "dry_run": True}),
        content_type="application/json",
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body.get("dry_run") is True
    summary = body.get("summary")
    assert summary is not None
    assert summary.get("created", 0) == 1

    # No debe existir asistencia en B aún
    with app.app_context():
        exists = Attendance.query.filter_by(
            student_id=sample_data["student_id"], activity_id=b_id
        ).first()
        assert exists is None

    # Ejecutar sincronización real (seleccionando B)
    res2 = client.post(
        "/api/attendances/sync-related",
        headers=auth_headers,
        data=json.dumps({"source_activity_id": b_id, "dry_run": False}),
        content_type="application/json",
    )
    assert res2.status_code in (200, 201)
    body2 = res2.get_json()
    assert body2.get("dry_run") is False
    summary2 = body2.get("summary")
    assert summary2.get("created", 0) >= 1

    # Ahora debe existir asistencia en B
    with app.app_context():
        created = Attendance.query.filter_by(
            student_id=sample_data["student_id"], activity_id=b_id
        ).first()
        assert created is not None

        # Crear otro estudiante y su asistencia en A
        s2 = Student()
        s2.control_number = "87654321"
        s2.full_name = "Ana"
        db.session.add(s2)
        db.session.commit()

        att2 = Attendance()
        att2.student_id = s2.id
        att2.activity_id = a_id
        att2.check_in_time = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        att2.check_out_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        db.session.add(att2)
        db.session.commit()
        # Guardar id del estudiante creado para usar fuera del contexto
        s2_id = s2.id

    # Sincronizar solo para el student fixture (no para s2) seleccionando B
    res3 = client.post(
        "/api/attendances/sync-related",
        headers=auth_headers,
        data=json.dumps(
            {
                "source_activity_id": b_id,
                "student_ids": [sample_data["student_id"]],
                "dry_run": False,
            }
        ),
        content_type="application/json",
    )
    assert res3.status_code in (200, 201)

    with app.app_context():
        exists_s2 = Attendance.query.filter_by(
            student_id=s2_id, activity_id=b_id
        ).first()
        assert exists_s2 is None
