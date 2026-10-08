import json
from datetime import datetime, timedelta


def test_create_registration(client, auth_headers, sample_data):
    from app import db
    from app.models.activity import Activity

    with client.application.app_context():
        activity = Activity(
            event_id=sample_data["event_id"],
            department="ISC",
            name="Taller de prueba",
            start_datetime=datetime(2024, 1, 1, 10, 0, 0),
            end_datetime=datetime(2024, 1, 1, 11, 0, 0),
            duration_hours=1.0,
            activity_type="Taller",
            location="Laboratorio A",
            modality="Presencial",
            max_capacity=10,
        )
        db.session.add(activity)
        db.session.commit()
        activity_id = activity.id

    registration_data = {
        "student_id": sample_data["student_id"],
        "activity_id": activity_id,
    }

    response = client.post(
        "/api/registrations/", headers=auth_headers, json=registration_data
    )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data["message"] == "Preregistro creado exitosamente"


def _create_activity(client, event_id, name):
    from app import db
    from app.models.activity import Activity

    with client.application.app_context():
        activity = Activity(
            event_id=event_id,
            department="ISC",
            name=name,
            start_datetime=datetime(2024, 1, 1, 10, 0, 0),
            end_datetime=datetime(2024, 1, 1, 11, 0, 0),
            duration_hours=1.0,
            activity_type="Taller",
            location="Laboratorio A",
            modality="Presencial",
            max_capacity=10,
        )
        db.session.add(activity)
        db.session.commit()
        return activity.id


def test_get_registrations_includes_attendance(client, auth_headers, sample_data):
    """`GET /api/registrations` expone la asistencia del estudiante.

    El auto-registro no cambia el `status` de la Registration (sigue
    "Confirmado" hasta el checkout), así que sin este campo el portal no
    tendría forma de mostrar que la asistencia ya quedó tomada.
    """
    from app import db
    from app.models.attendance import Attendance
    from app.models.registration import Registration

    checked_in = _create_activity(client, sample_data["event_id"], "Con check-in")
    without_check_in = _create_activity(client, sample_data["event_id"], "Sin check-in")

    with client.application.app_context():
        for activity_id in (checked_in, without_check_in):
            db.session.add(
                Registration(
                    student_id=sample_data["student_id"],
                    activity_id=activity_id,
                    status="Confirmado",
                    attended=activity_id == checked_in,
                )
            )
        db.session.add(
            Attendance(
                student_id=sample_data["student_id"],
                activity_id=checked_in,
                status="Parcial",
                check_in_time=datetime(2024, 1, 1, 9, 30, 0),
            )
        )
        db.session.commit()

    response = client.get(
        f"/api/registrations/?student_id={sample_data['student_id']}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    rows = {
        row["activity_id"]: row for row in json.loads(response.data)["registrations"]
    }

    opened = rows[checked_in]["attendance"]
    assert opened["status"] == "Parcial"
    assert opened["check_in_time"]
    # El status de la Registration NO cambió hasta el cierre
    assert rows[checked_in]["status"] == "Confirmado"
    assert rows[without_check_in]["attendance"] is None


# --- Orden del listado (parámetro `sort`) -----------------------------------

# Orden cronológico de las actividades creadas por _create_sort_data():
_SORT_CHRONO = ["Charla temprana", "Taller mediodia", "Conferencia tarde"]
# ...que es el contrario al orden de sus fechas de preregistro:
_SORT_BY_REGISTRATION = ["Conferencia tarde", "Taller mediodia", "Charla temprana"]


def _create_sort_data(client, sample_data):
    """Crea 3 actividades cuyo orden cronológico es el contrario al orden de
    sus preregistros, para poder distinguir ambos órdenes en la respuesta.

    Devuelve `{nombre_actividad: activity_id}`.
    """
    from app import db
    from app.models.activity import Activity
    from app.models.registration import Registration

    # (nombre, inicio de la actividad, fecha de preregistro)
    rows = [
        ("Charla temprana", datetime(2024, 3, 10, 9, 0), datetime(2024, 2, 1, 8, 0)),
        ("Taller mediodia", datetime(2024, 3, 10, 13, 0), datetime(2024, 2, 1, 9, 0)),
        (
            "Conferencia tarde",
            datetime(2024, 3, 10, 17, 0),
            datetime(2024, 2, 1, 10, 0),
        ),
    ]
    created = {}
    with client.application.app_context():
        for name, start, reg_date in rows:
            activity = Activity(
                event_id=sample_data["event_id"],
                department="ISC",
                name=name,
                start_datetime=start,
                end_datetime=start + timedelta(hours=1),
                duration_hours=1.0,
                activity_type="Taller",
                location="Aula 1",
                modality="Presencial",
                max_capacity=10,
            )
            db.session.add(activity)
            db.session.flush()
            db.session.add(
                Registration(
                    student_id=sample_data["student_id"],
                    activity_id=activity.id,
                    status="Confirmado",
                    registration_date=reg_date,
                )
            )
            created[name] = activity.id
        db.session.commit()
    return created


def _names_in_response(response):
    """Nombres de actividad del payload, acotados a los creados por el test,
    en el orden en que los devolvió el endpoint."""
    payload = json.loads(response.data)
    wanted = set(_SORT_CHRONO)
    return [
        row["activity"]["name"]
        for row in payload["registrations"]
        if isinstance(row.get("activity"), dict)
        and row["activity"].get("name") in wanted
    ]


def _get_registrations(client, auth_headers, sample_data, extra_query=""):
    response = client.get(
        f"/api/registrations/?student_id={sample_data['student_id']}"
        f"&per_page=50{extra_query}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    return response


def test_get_registrations_default_order_is_registration_date_desc(
    client, auth_headers, sample_data
):
    """Sin parámetro `sort` el orden histórico no cambia.

    El panel de admin no envía `sort`, así que su listado queda exactamente
    como antes (registros más recientes primero).
    """
    _create_sort_data(client, sample_data)

    response = _get_registrations(client, auth_headers, sample_data)

    assert _names_in_response(response) == _SORT_BY_REGISTRATION


def test_get_registrations_sort_by_activity_start_asc(
    client, auth_headers, sample_data
):
    """`sort=activity.start_datetime:asc` ordena cronológicamente.

    Es el orden por defecto del portal del estudiante: la actividad más
    próxima primero entre las futuras.
    """
    _create_sort_data(client, sample_data)

    response = _get_registrations(
        client, auth_headers, sample_data, "&sort=activity.start_datetime:asc"
    )

    assert _names_in_response(response) == _SORT_CHRONO


def test_get_registrations_sort_by_activity_start_desc(
    client, auth_headers, sample_data
):
    _create_sort_data(client, sample_data)

    response = _get_registrations(
        client, auth_headers, sample_data, "&sort=activity.start_datetime:desc"
    )

    assert _names_in_response(response) == list(reversed(_SORT_CHRONO))


def test_get_registrations_sort_by_registration_date_asc(
    client, auth_headers, sample_data
):
    _create_sort_data(client, sample_data)

    response = _get_registrations(
        client, auth_headers, sample_data, "&sort=registration_date:asc"
    )

    assert _names_in_response(response) == list(reversed(_SORT_BY_REGISTRATION))


def test_get_registrations_unknown_sort_falls_back_to_default(
    client, auth_headers, sample_data
):
    """Un `sort` desconocido o con dirección inválida no rompe el listado."""
    _create_sort_data(client, sample_data)

    for bad_sort in ("created_at:asc", "activity.start_datetime:sideways", "name"):
        response = _get_registrations(
            client, auth_headers, sample_data, f"&sort={bad_sort}"
        )
        assert _names_in_response(response) == _SORT_BY_REGISTRATION


def test_get_registrations_sort_combines_with_search_and_event(
    client, auth_headers, sample_data
):
    """`sort` por actividad + `search` + `event_id` conviven sin error.

    El orden usa un alias propio de `activities` porque `search` ya hace su
    propio JOIN con otro alias; en MySQL un JOIN sin alias fallaría con
    "Not unique table/alias" cuando vienen juntos.
    """
    _create_sort_data(client, sample_data)

    response = _get_registrations(
        client,
        auth_headers,
        sample_data,
        "&sort=activity.start_datetime:asc"
        f"&event_id={sample_data['event_id']}&search=Charla",
    )

    assert _names_in_response(response) == ["Charla temprana"]
