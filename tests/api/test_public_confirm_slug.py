"""POST /api/public/registrations/<id>/confirm aceptando ``activity_id`` slug.

Los frontends públicos (vista de staff ``/public/staff-walkin/<slug>`` y portal
``/public/registrations/<slug>``) envían el ``public_slug`` de la actividad,
porque es el valor que la vista renderiza en ``data-activity-id``.

El endpoint hacía ``int(activity_id)``: con un slug eso lanzaba ``ValueError``
y Flask respondía 500. Como ``activity_service`` genera el slug automáticamente
al crear/actualizar, eso rompía "Confirmar asistencia" y "Marcar Ausente" para
casi todas las actividades. Las otras dos acciones del módulo de staff sí usaban
``resolve_activity_by_id``, de ahí el comportamiento a medias del módulo.

Nota: la ventana de confirmación se controla con ``end_datetime`` +
``public_confirm_window_days`` (30 por defecto), por eso las actividades de
este fichero terminan en el futuro.
"""

from datetime import datetime

from app import db
from app.models.attendance import Attendance
from app.models.registration import Registration


def _seed(app, activity_factory, sample_data, slug, **extra):
    """Actividad con preregistro del estudiante de ``sample_data``.

    Devuelve ``(activity_id, registration_id)``.
    """
    activity = activity_factory(
        event_id=sample_data["event_id"],
        name="Conferencia De Staff",
        activity_type="Magistral",
        public_slug=slug,
        start_datetime=datetime(2030, 3, 10, 9, 0, 0),
        end_datetime=datetime(2030, 3, 10, 11, 0, 0),
        **extra,
    )
    reg = Registration(
        student_id=sample_data["student_id"],
        activity_id=activity.id,
        status="Registrado",
    )
    db.session.add(reg)
    db.session.commit()
    return activity.id, reg.id


def test_confirm_accepts_public_slug(client, app, activity_factory, sample_data):
    """Confirmar con el slug (como lo envía staff-walkin) responde 200."""
    _, reg_id = _seed(app, activity_factory, sample_data, "conferencia-staff")

    resp = client.post(
        f"/api/public/registrations/{reg_id}/confirm",
        json={
            "activity_id": "conferencia-staff",
            "confirm": True,
            "create_attendance": True,
        },
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body["registration"]["attended"] is True
    assert body["registration"]["status"] == "Asistió"
    # Se creó la asistencia correspondiente
    assert (
        Attendance.query.filter_by(
            student_id=sample_data["student_id"],
            activity_id=body["registration"]["activity_id"],
        ).count()
        == 1
    )


def test_confirm_accepts_numeric_activity_id(
    client, app, activity_factory, sample_data
):
    """Regresión: el ID numérico (actividad sin slug) sigue funcionando."""
    activity_id, reg_id = _seed(
        app, activity_factory, sample_data, "slug-que-no-se-usa"
    )

    resp = client.post(
        f"/api/public/registrations/{reg_id}/confirm",
        json={"activity_id": str(activity_id), "confirm": True},
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json()["registration"]["attended"] is True


def test_confirm_without_slug_still_works_by_id(
    client, app, activity_factory, sample_data
):
    """Actividad sin ``public_slug``: la vista envía el ID y debe resolver."""
    activity = activity_factory(
        event_id=sample_data["event_id"],
        name="Sin Slug",
        public_slug=None,
        start_datetime=datetime(2030, 3, 10, 9, 0, 0),
        end_datetime=datetime(2030, 3, 10, 11, 0, 0),
    )
    reg = Registration(
        student_id=sample_data["student_id"],
        activity_id=activity.id,
        status="Registrado",
    )
    db.session.add(reg)
    db.session.commit()

    resp = client.post(
        f"/api/public/registrations/{reg.id}/confirm",
        json={"activity_id": activity.id, "confirm": True},
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)


def test_confirm_unknown_slug_returns_404_not_500(client, app):
    """Un slug inexistente responde 404 (antes: ``int()`` -> ValueError -> 500)."""
    resp = client.post(
        "/api/public/registrations/1/confirm",
        json={"activity_id": "slug-que-no-existe", "confirm": True},
    )

    assert resp.status_code == 404
    assert "Actividad no encontrada" in resp.get_json()["message"]


def test_confirm_mark_absent_by_slug(client, app, activity_factory, sample_data):
    """Marcar Ausente (acción de staff) también va por slug."""
    _, reg_id = _seed(app, activity_factory, sample_data, "conferencia-ausente")

    resp = client.post(
        f"/api/public/registrations/{reg_id}/confirm",
        json={
            "activity_id": "conferencia-ausente",
            "confirm": False,
            "create_attendance": False,
            "mark_absent": True,
        },
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)
    reg = db.session.get(Registration, reg_id)
    assert reg.status == "Ausente"
    assert reg.attended is False
    # Marcar ausente no debe crear asistencia
    assert (
        Attendance.query.filter_by(
            student_id=sample_data["student_id"], activity_id=reg.activity_id
        ).count()
        == 0
    )


def test_confirm_rejects_registration_of_another_activity(
    client, app, activity_factory, sample_data
):
    """El registro debe pertenecer a la actividad indicada (slug incluido)."""
    _, reg_id = _seed(app, activity_factory, sample_data, "conferencia-uno")
    _seed(app, activity_factory, sample_data, "conferencia-dos")

    resp = client.post(
        f"/api/public/registrations/{reg_id}/confirm",
        json={"activity_id": "conferencia-dos", "confirm": True},
    )

    assert resp.status_code == 404
    # El preregistro original queda intacto
    assert db.session.get(Registration, reg_id).attended in (False, None)


def test_confirm_without_activity_id_returns_400(client, app):
    """Validación previa: falta ``activity_id``."""
    resp = client.post("/api/public/registrations/1/confirm", json={"confirm": True})

    assert resp.status_code == 400
