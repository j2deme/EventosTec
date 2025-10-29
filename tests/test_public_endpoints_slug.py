import json


def test_public_registration_resolves_by_public_slug(client, db_session, activity_factory, event_factory):
    # Crear evento y actividad con public_slug
    event = event_factory(name="Evento X")
    activity = activity_factory(
        event_id=event.id, name="Actividad X", public_slug="actividad-x")

    # Llamar al endpoint público que debería resolver por slug
    resp = client.get(f"/public/registrations/{activity.public_slug}")
    assert resp.status_code == 200


def test_public_registration_token_fallback(client, db_session, activity_factory):
    # Crear actividad sin public_slug y con token
    activity = activity_factory(public_slug=None)
    # Simular token generation (service ya probado por separado)
    token = "p:12345"

    # Endpoint con token debe seguir funcionando
    resp = client.get(f"/public/registrations/{token}")
    # Dependiendo de la implementación, puede redirigir o devolver 200
    assert resp.status_code in (200, 302)
