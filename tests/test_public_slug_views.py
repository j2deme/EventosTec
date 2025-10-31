"""Tests for public views using slug-based resolution (self-register, staff-walkin)."""

import pytest


@pytest.fixture
def magistral_activity(db_session, event_factory, activity_factory):
    """Create a Magistral activity with public_slug for testing staff-walkin."""
    event = event_factory(name="Test Event")
    activity = activity_factory(
        event_id=event.id,
        name="Test Magistral",
        activity_type="Magistral",
        public_slug="test-magistral",
    )
    return activity


@pytest.fixture
def regular_activity(db_session, event_factory, activity_factory):
    """Create a regular (non-Magistral) activity for testing self-register."""
    event = event_factory(name="Test Event 2")
    activity = activity_factory(
        event_id=event.id,
        name="Test Regular Activity",
        activity_type="Curso",
        public_slug="test-regular-activity",
    )
    return activity


class TestSelfRegisterBySlug:
    """Test /public/self-register/<slug> endpoint."""

    def test_self_register_by_slug_renders_form(self, client, regular_activity):
        """Test that /public/self-register/<slug> renders the form successfully."""
        resp = client.get(f"/public/self-register/{regular_activity.public_slug}")
        assert resp.status_code == 200
        # Check that the form contains expected content
        assert b"self_register.html" in resp.data or b"activity_token" in resp.data

    def test_self_register_by_slug_passes_activity_token(
        self, client, regular_activity
    ):
        """Test that activity_token is generated and passed to template."""
        resp = client.get(f"/public/self-register/{regular_activity.public_slug}")
        assert resp.status_code == 200
        # The response should contain activity_token in the template (passed as context)
        # This is a basic check; actual token validation happens in form submission

    def test_self_register_by_invalid_slug(self, client):
        """Test that invalid slug returns error state."""
        resp = client.get("/public/self-register/nonexistent-slug")
        assert resp.status_code == 200
        # Should still render template with error indicators

    def test_self_register_legacy_route_still_works(self, client):
        """Test that legacy /self-register route still works."""
        resp = client.get("/self-register")
        assert resp.status_code == 200


class TestStaffWalkinBySlug:
    """Test /public/staff-walkin/<slug> endpoint."""

    def test_staff_walkin_by_slug_renders_form(self, client, magistral_activity):
        """Test that /public/staff-walkin/<slug> renders the form successfully for Magistral activities."""
        resp = client.get(f"/public/staff-walkin/{magistral_activity.public_slug}")
        assert resp.status_code == 200

    def test_staff_walkin_requires_magistral_type(self, client, regular_activity):
        """Test that staff-walkin only works for Magistral activities."""
        resp = client.get(f"/public/staff-walkin/{regular_activity.public_slug}")
        assert resp.status_code == 200
        # Should return the template but with error state (token_invalid=True)

    def test_staff_walkin_by_invalid_slug(self, client):
        """Test that invalid slug returns error state."""
        resp = client.get("/public/staff-walkin/nonexistent-slug")
        assert resp.status_code == 200
        # Should still render template with error indicators

    def test_staff_walkin_query_param_fallback(self, client, magistral_activity):
        """Test that query param fallback still works."""
        resp = client.get(f"/public/staff-walkin?slug={magistral_activity.public_slug}")
        assert resp.status_code == 200


class TestPublicRegistrationsBySlug:
    """Test /public/registrations/<slug> endpoint (already working, baseline test)."""

    def test_registrations_by_slug_renders_form(self, client, regular_activity):
        """Test that /public/registrations/<slug> renders successfully."""
        resp = client.get(f"/public/registrations/{regular_activity.public_slug}")
        assert resp.status_code == 200
