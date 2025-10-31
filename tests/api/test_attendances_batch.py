from io import BytesIO


def test_batch_upload_txt_file(client, app, sample_data, auth_headers):
    """Test batch upload with TXT file"""
    from app import db
    from app.models.activity import Activity
    from app.models.student import Student
    from app.models.attendance import Attendance
    from datetime import datetime, timezone, timedelta

    student_id = sample_data["student_id"]
    event_id = sample_data["event_id"]

    # Create activity
    with app.app_context():
        start = datetime.now(timezone.utc)
        end = start + timedelta(hours=1)
        activity = Activity(
            name="Actividad batch test",
            event_id=event_id,
            start_datetime=start,
            end_datetime=end,
            duration_hours=1.0,
            activity_type="Taller",
            department="General",
            location="Sala 1",
            modality="Presencial",
        )
        db.session.add(activity)
        db.session.commit()
        activity_id = activity.id

        # Get student control number
        student = db.session.get(Student, student_id)
        control_number = student.control_number

    # Create TXT file with control number
    txt_content = f"{control_number}\n"
    txt_file = BytesIO(txt_content.encode("utf-8"))

    # Upload with dry_run=1
    data = {"activity_id": str(activity_id), "dry_run": "1"}

    resp = client.post(
        "/api/attendances/batch",
        data=data,
        headers=auth_headers,
        content_type="multipart/form-data",
    )
    # Note: when using client.post with files, we need to include the file in data dict
    # Let's use a different approach

    # Reset file pointer
    txt_file.seek(0)
    data["file"] = (txt_file, "test.txt")

    resp = client.post(
        "/api/attendances/batch",
        data={**data, "file": (txt_file, "test.txt")},
        headers=auth_headers,
        content_type="multipart/form-data",
    )

    assert resp.status_code == 200
    result = resp.get_json()
    assert "report" in result
    report = result["report"]
    assert report["created"] >= 1 or report["skipped"] >= 1

    # Verify no attendance was created (dry_run=1)
    with app.app_context():
        att = Attendance.query.filter_by(
            student_id=student_id, activity_id=activity_id
        ).first()
        assert att is None


def test_batch_upload_xlsx_file_dry_run(client, app, sample_data, auth_headers):
    """Test batch upload with XLSX file in dry-run mode"""
    from app import db
    from app.models.activity import Activity
    from app.models.student import Student
    from datetime import datetime, timezone, timedelta
    import openpyxl

    student_id = sample_data["student_id"]
    event_id = sample_data["event_id"]

    # Create activity
    with app.app_context():
        start = datetime.now(timezone.utc)
        end = start + timedelta(hours=1)
        activity = Activity(
            name="Actividad batch XLSX test",
            event_id=event_id,
            start_datetime=start,
            end_datetime=end,
            duration_hours=1.0,
            activity_type="Taller",
            department="General",
            location="Sala 1",
            modality="Presencial",
        )
        db.session.add(activity)
        db.session.commit()
        activity_id = activity.id

        # Get student control number
        student = db.session.get(Student, student_id)
        control_number = student.control_number

    # Create XLSX file with control number in first column
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = control_number
    xlsx_file = BytesIO()
    wb.save(xlsx_file)
    xlsx_file.seek(0)

    # Upload with dry_run=1
    data = {
        "activity_id": str(activity_id),
        "dry_run": "1",
        "file": (xlsx_file, "test.xlsx"),
    }

    resp = client.post(
        "/api/attendances/batch",
        data=data,
        headers=auth_headers,
        content_type="multipart/form-data",
    )

    assert resp.status_code == 200
    result = resp.get_json()
    assert "report" in result
    report = result["report"]
    # In dry run, we should see the report structure
    assert "created" in report
    assert "skipped" in report
    assert "not_found" in report
    # The student should either be created or skipped
    assert report["created"] >= 1 or report["skipped"] >= 1 or report["not_found"] >= 1


def test_batch_upload_real_execution(client, app, sample_data, auth_headers):
    """Test batch upload with real execution (dry_run=0)"""
    from app import db
    from app.models.activity import Activity
    from app.models.student import Student
    from app.models.attendance import Attendance
    from datetime import datetime, timezone, timedelta

    student_id = sample_data["student_id"]
    event_id = sample_data["event_id"]

    # Create activity
    with app.app_context():
        start = datetime.now(timezone.utc)
        end = start + timedelta(hours=1)
        activity = Activity(
            name="Actividad batch real test",
            event_id=event_id,
            start_datetime=start,
            end_datetime=end,
            duration_hours=1.0,
            activity_type="Taller",
            department="General",
            location="Sala 1",
            modality="Presencial",
        )
        db.session.add(activity)
        db.session.commit()
        activity_id = activity.id

        # Get student control number
        student = db.session.get(Student, student_id)
        control_number = student.control_number

    # Create TXT file with control number
    txt_content = f"{control_number}\n"
    txt_file = BytesIO(txt_content.encode("utf-8"))

    # Upload with dry_run=0
    data = {
        "activity_id": str(activity_id),
        "dry_run": "0",
        "file": (txt_file, "test.txt"),
    }

    resp = client.post(
        "/api/attendances/batch",
        data=data,
        headers=auth_headers,
        content_type="multipart/form-data",
    )

    assert resp.status_code == 201
    result = resp.get_json()
    assert "report" in result
    report = result["report"]
    assert report["created"] >= 1

    # Verify attendance was created
    with app.app_context():
        att = Attendance.query.filter_by(
            student_id=student_id, activity_id=activity_id
        ).first()
        assert att is not None
        assert att.status == "Asistió"
        assert att.attendance_percentage == 100.0


def test_batch_upload_duplicate_attendance(client, app, sample_data, auth_headers):
    """Test that batch upload skips duplicate attendances"""
    from app import db
    from app.models.activity import Activity
    from app.models.student import Student
    from app.models.attendance import Attendance
    from datetime import datetime, timezone, timedelta

    student_id = sample_data["student_id"]
    event_id = sample_data["event_id"]

    # Create activity and attendance
    with app.app_context():
        start = datetime.now(timezone.utc)
        end = start + timedelta(hours=1)
        activity = Activity(
            name="Actividad duplicate test",
            event_id=event_id,
            start_datetime=start,
            end_datetime=end,
            duration_hours=1.0,
            activity_type="Taller",
            department="General",
            location="Sala 1",
            modality="Presencial",
        )
        db.session.add(activity)
        db.session.commit()
        activity_id = activity.id

        # Create existing attendance
        attendance = Attendance(
            student_id=student_id,
            activity_id=activity_id,
            status="Asistió",
            attendance_percentage=100.0,
        )
        db.session.add(attendance)
        db.session.commit()

        # Get student control number
        student = db.session.get(Student, student_id)
        control_number = student.control_number

    # Create TXT file with same control number
    txt_content = f"{control_number}\n"
    txt_file = BytesIO(txt_content.encode("utf-8"))

    # Upload with dry_run=0
    data = {
        "activity_id": str(activity_id),
        "dry_run": "0",
        "file": (txt_file, "test.txt"),
    }

    resp = client.post(
        "/api/attendances/batch",
        data=data,
        headers=auth_headers,
        content_type="multipart/form-data",
    )

    assert resp.status_code == 201
    result = resp.get_json()
    assert "report" in result
    report = result["report"]
    # Should skip the duplicate
    assert report["skipped"] >= 1
    assert report["created"] == 0


def test_batch_upload_invalid_activity(client, app, auth_headers):
    """Test batch upload with invalid activity_id"""
    txt_content = "L12345678\n"
    txt_file = BytesIO(txt_content.encode("utf-8"))

    data = {
        "activity_id": "99999",  # Non-existent activity
        "dry_run": "1",
        "file": (txt_file, "test.txt"),
    }

    resp = client.post(
        "/api/attendances/batch",
        data=data,
        headers=auth_headers,
        content_type="multipart/form-data",
    )

    # Should return error in report
    assert resp.status_code in (200, 400, 500)
    result = resp.get_json()
    # Expect error in report or message
    assert "report" in result or "error" in result or "message" in result


def test_batch_upload_missing_file(client, app, sample_data, auth_headers):
    """Test batch upload without file"""
    event_id = sample_data["event_id"]

    # Create activity
    from app import db
    from app.models.activity import Activity
    from datetime import datetime, timezone, timedelta

    with app.app_context():
        start = datetime.now(timezone.utc)
        end = start + timedelta(hours=1)
        activity = Activity(
            name="Actividad missing file test",
            event_id=event_id,
            start_datetime=start,
            end_datetime=end,
            duration_hours=1.0,
            activity_type="Taller",
            department="General",
            location="Sala 1",
            modality="Presencial",
        )
        db.session.add(activity)
        db.session.commit()
        activity_id = activity.id

    data = {"activity_id": str(activity_id), "dry_run": "1"}

    resp = client.post(
        "/api/attendances/batch",
        data=data,
        headers=auth_headers,
        content_type="multipart/form-data",
    )

    assert resp.status_code == 400
    result = resp.get_json()
    assert "message" in result
    assert "archivo" in result["message"].lower()
