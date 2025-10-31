from app import db
from app.models.attendance import Attendance
from app.models.student import Student
from flask_jwt_extended import create_access_token
from datetime import datetime, timezone


def create_student_and_token(
    app, client, control_number="20250001", full_name="Alumno Test"
):
    with app.app_context():
        student = Student()
        student.control_number = control_number
        student.full_name = full_name
        student.career = "Ingeniería"
        db.session.add(student)
        db.session.commit()
        # Crear token usando el student.id como identidad JWT
        token = create_access_token(identity=str(student.id))
        return student, {"Authorization": f"Bearer {token}"}


def test_student_sees_only_their_attendances(app, client):
    # Preparar dos estudiantes y varias asistencias
    with app.app_context():
        s1 = Student()
        s1.control_number = "1001"
        s1.full_name = "Alumno Uno"
        s1.career = "X"

        s2 = Student()
        s2.control_number = "1002"
        s2.full_name = "Alumno Dos"
        s2.career = "Y"
        db.session.add_all([s1, s2])
        db.session.commit()

        # Crear attendances: uno para s1 y uno para s2
        a1 = Attendance()
        a1.student_id = s1.id
        a1.activity_id = 1
        a1.check_in_time = datetime.now(timezone.utc)
        a1.status = "Parcial"

        a2 = Attendance()
        a2.student_id = s2.id
        a2.activity_id = 1
        a2.check_in_time = datetime.now(timezone.utc)
        a2.status = "Parcial"

    db.session.add_all([a1, a2])
    db.session.commit()

    # Crear token para s1 (usar student.id como identidad) dentro del app context
    token = create_access_token(identity=str(s1.id))
    headers = {"Authorization": f"Bearer {token}"}

    # Llamar al endpoint de listado con headers de estudiante (ruta con slash)
    resp = client.get("/api/attendances/", headers=headers, follow_redirects=True)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "attendances" in data
    assert isinstance(data["attendances"], list)
    # Debe devolver sólo la asistencia del estudiante s1
    assert len(data["attendances"]) == 1
    assert data["attendances"][0]["student_id"] == s1.id


def test_student_cannot_access_other_attendance_by_id(app, client):
    with app.app_context():
        s1 = Student()
        s1.control_number = "2001"
        s1.full_name = "Alumno A"
        s1.career = "X"

        s2 = Student()
        s2.control_number = "2002"
        s2.full_name = "Alumno B"
        s2.career = "Y"
        db.session.add_all([s1, s2])
        db.session.commit()

        a = Attendance()
        a.student_id = s2.id
        a.activity_id = 10
        a.check_in_time = datetime.now(timezone.utc)
        a.status = "Parcial"
        db.session.add(a)
        db.session.commit()

        # Crear token para alumno s1 (usar student id)
        token = create_access_token(identity=str(s1.id))
        headers = {"Authorization": f"Bearer {token}"}

        # Intentar obtener la asistencia de s2 usando el token de s1
        resp = client.get(
            f"/api/attendances/{a.id}", headers=headers, follow_redirects=True
        )
        assert resp.status_code == 403


def test_student_with_no_attendances_returns_empty_list(app, client):
    with app.app_context():
        s, headers = create_student_and_token(
            app, client, control_number="3001", full_name="Sin Asist"
        )
        # No se crean attendances
        resp = client.get("/api/attendances/", headers=headers, follow_redirects=True)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "attendances" in data
        assert isinstance(data["attendances"], list)
        assert len(data["attendances"]) == 0


def test_admin_can_view_all_attendances_and_pause_resume_endpoints(
    app, client, auth_headers
):
    # auth_headers es del admin (fixture)
    with app.app_context():
        # crear dos estudiantes y sus attendances
        s1 = Student()
        s1.control_number = "4001"
        s1.full_name = "Admin Uno"
        s1.career = "Z"

        s2 = Student()
        s2.control_number = "4002"
        s2.full_name = "Admin Dos"
        s2.career = "Z"

        db.session.add_all([s1, s2])
        db.session.commit()

        a1 = Attendance()
        a1.student_id = s1.id
        a1.activity_id = 11
        a1.check_in_time = datetime.now(timezone.utc)
        a1.status = "Parcial"

        a2 = Attendance()
        a2.student_id = s2.id
        a2.activity_id = 12
        a2.check_in_time = datetime.now(timezone.utc)
        a2.status = "Parcial"

        db.session.add_all([a1, a2])
        db.session.commit()

        # Admin lista todas
        resp = client.get(
            "/api/attendances/", headers=auth_headers, follow_redirects=True
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] >= 2

        # Probar endpoint pause (admin)
        resp_pause = client.post(
            "/api/attendances/pause",
            json={"student_id": s1.id, "activity_id": a1.activity_id},
            headers=auth_headers,
        )
        assert resp_pause.status_code == 200
        payload = resp_pause.get_json()
        assert "attendance" in payload
        assert payload["attendance"]["is_paused"] is True

        # Probar endpoint resume (admin)
        resp_resume = client.post(
            "/api/attendances/resume",
            json={"student_id": s1.id, "activity_id": a1.activity_id},
            headers=auth_headers,
        )
        assert resp_resume.status_code == 200
        payload2 = resp_resume.get_json()
        assert "attendance" in payload2
        assert payload2["attendance"]["is_paused"] is False
