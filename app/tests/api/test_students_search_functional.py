import pytest


def test_students_search_returns_matches(client, app, sample_data):
    from app import db
    from app.models.student import Student

    with app.app_context():
        s = Student(control_number='99999999',
                    full_name='Test Student Search', career='Test')
        db.session.add(s)
        db.session.commit()
        sid = s.id

    resp = client.get('/api/students/search?q=Test')
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert any(item.get('full_name') == 'Test Student Search' for item in data)
