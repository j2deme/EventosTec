def test_root_shows_login_page(client):
    resp = client.get("/")
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert "<form" in text or "Login" in text or "username" in text.lower()


def test_students_search_short_query_returns_empty(client):
    resp = client.get("/api/students/search?q=a")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert data == []
