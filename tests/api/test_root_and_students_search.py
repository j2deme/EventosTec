def test_root_shows_login_page(client):
    resp = client.get("/")
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert "<form" in text or "Login" in text or "username" in text.lower()
