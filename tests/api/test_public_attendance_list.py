"""Tests de la lista de asistencia imprimible (admin y vista pública de Jefes).

La vista pública `/public/attendance-list/<activity_ref>` debe renderizar
exactamente la misma lista que `/api/reports/attendance_list` (admin), porque
ambas comparten `app.services.attendance_list_service.build_attendance_list_context`.
"""

from datetime import datetime


def _seed_activity_with_registration(
    app,
    sample_data,
    name,
    public_slug=None,
    start=None,
    end=None,
):
    """Crea una actividad con un preregistro y devuelve (activity_id, slug)."""
    from app import db
    from app.models.activity import Activity
    from app.models.registration import Registration

    with app.app_context():
        activity = Activity(
            event_id=sample_data["event_id"],
            name=name,
            department="TEST",
            start_datetime=start or datetime(2026, 1, 10, 9, 0, 0),
            end_datetime=end or datetime(2026, 1, 10, 11, 0, 0),
            duration_hours=2.0,
            activity_type="Taller",
            location="Aula 2",
            modality="Presencial",
        )
        if public_slug:
            activity.public_slug = public_slug
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
        return activity.id, activity.public_slug


def _plain(html):
    """Quita las etiquetas <strong> para poder buscar 'Total ... : N'."""
    return html.replace("<strong>", "").replace("</strong>", "")


def test_public_attendance_list_unknown_ref_returns_404(client):
    """La referencia inexistente responde 404 (sin autenticación)."""
    response = client.get("/public/attendance-list/actividad-que-no-existe")

    assert response.status_code == 404


def test_public_attendance_list_renders_without_auth(client, app, sample_data):
    """La vista pública renderiza la lista sin JWT, resolviendo por slug."""
    activity_id, slug = _seed_activity_with_registration(
        app, sample_data, "Taller Impresion Publica", "taller-impresion-publica"
    )

    response = client.get(f"/public/attendance-list/{slug}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Taller Impresion Publica" in html
    # Estudiante del fixture sample_data (Juan Pérez)
    assert "Juan Pérez" in html
    assert "Total de preregistrados: 1" in _plain(html)

    # El ID numérico NO resuelve: no hay fallback (evita enumerar /1, /2, ...)
    response_by_id = client.get(f"/public/attendance-list/{activity_id}")
    assert response_by_id.status_code == 404


def test_public_attendance_list_rejects_numeric_id_enumeration(
    client, app, sample_data
):
    """`/public/attendance-list/<id>` responde 404: la lista solo va por slug.

    La ruta es pública y expone nombre + número de control de todos los
    preregistrados; permitir el ID convirtió el endpoint en un volcado
    enumerable (1, 2, 3, ...).
    """
    activity_id, slug = _seed_activity_with_registration(
        app, sample_data, "Conferencia Por Id", "conferencia-por-id"
    )

    assert client.get(f"/public/attendance-list/{slug}").status_code == 200
    assert client.get(f"/public/attendance-list/{activity_id}").status_code == 404
    # Un ID inexistente también da 404 (misma respuesta, sin revelar si existe)
    assert client.get("/public/attendance-list/999999").status_code == 404


def test_public_attendance_list_activity_without_slug_returns_404(
    client, app, sample_data
):
    """Una actividad sin `public_slug` no es imprimible por esta ruta."""
    activity_id, _ = _seed_activity_with_registration(
        app, sample_data, "Taller Sin Slug", None
    )

    response = client.get(f"/public/attendance-list/{activity_id}")
    assert response.status_code == 404


def test_public_attendance_list_matches_admin_output(
    client, app, auth_headers, sample_data
):
    """Admin y vista pública imprimen la misma lista (fuente compartida)."""
    activity_id, slug = _seed_activity_with_registration(
        app, sample_data, "Conferencia Compartida", "conferencia-compartida"
    )

    admin_html = client.get(
        f"/api/reports/attendance_list?activity_id={activity_id}",
        headers=auth_headers,
    ).get_data(as_text=True)
    public_html = client.get(f"/public/attendance-list/{slug}").get_data(as_text=True)

    assert "Conferencia Compartida" in admin_html
    assert "Juan Pérez" in admin_html
    assert "Juan Pérez" in public_html

    # El total de preregistrados debe coincidir en ambas vistas
    assert "Total de preregistrados: 1" in _plain(admin_html)
    assert "Total de preregistrados: 1" in _plain(public_html)


def test_public_attendance_list_multiday_columns(
    client, app, auth_headers, sample_data
):
    """Una actividad multiday genera una columna de asistencia por día."""
    activity_id, slug = _seed_activity_with_registration(
        app,
        sample_data,
        "Curso Multidia",
        "curso-multidia",
        start=datetime(2026, 1, 10, 9, 0, 0),
        end=datetime(2026, 1, 12, 11, 0, 0),
    )

    response = client.get(f"/public/attendance-list/{slug}")
    assert response.status_code == 200
    public_html = response.get_data(as_text=True)

    # Fechas de las 3 sesiones (10, 11 y 12 de enero de 2026)
    assert "10/01/2026" in public_html
    assert "11/01/2026" in public_html
    assert "12/01/2026" in public_html
    # En multiday NO aparece la columna única "Asistencia"
    assert "Asistencia" not in public_html

    # El admin renderiza las mismas columnas
    admin_html = client.get(
        f"/api/reports/attendance_list?activity_id={activity_id}",
        headers=auth_headers,
    ).get_data(as_text=True)
    assert "11/01/2026" in admin_html
    assert "Asistencia" not in admin_html
