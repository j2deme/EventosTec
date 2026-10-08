from flask import Blueprint, request, jsonify, render_template, current_app
from flask import Response
from flask_jwt_extended import jwt_required
from datetime import datetime
from app import db
from app.utils.auth_helpers import require_admin
from app.utils.datetime_utils import (
    app_timezone_info,
    db_now_local,
    localize_naive_datetime,
)
from app.services.attendance_list_service import build_attendance_list_context
from app.models.registration import Registration
from app.models.activity import Activity
from app.models.event import Event
from app.models.student import Student
from sqlalchemy import func
from typing import Any, List

reports_bp = Blueprint("reports", __name__, url_prefix="/api/reports")


# Ruta HTML imprimible para lista de asistentes (admin)
@reports_bp.route("/attendance_list", methods=["GET"])
@jwt_required()
@require_admin
def attendance_list():
    """Renderiza una página imprimible con la lista de preregistrados para una actividad.

    Query params:
      - activity_id (required)
      - show_generation (bool, optional)
    """
    activity_id = request.args.get("activity_id", type=int)
    if not activity_id:
        return "activity_id es requerido", 400

    activity = db.session.get(Activity, activity_id)
    if not activity:
        return "Actividad no encontrada", 404

    # El contexto (lista, orden y detección multiday) lo construye el servicio
    # compartido: es el mismo que usa la vista pública de Jefes de Carrera
    # (/public/attendance-list/<ref>), para que ambas impriman idénticas.
    context = build_attendance_list_context(activity)

    return render_template("admin/reports/attendance_list.html", **context)


@reports_bp.route("/participation_matrix", methods=["GET"])
@jwt_required()
@require_admin
def participation_matrix():
    """Devuelve una matriz de participación (filas: carrera, columnas: generación) con conteos.

    Query params:
      - event_id (int, optional)
      - activity_id (int, optional)

    Regla para generación: se extraen los primeros dos dígitos que aparezcan en el `control_number`.
    Si no se encuentran dígitos, se toma la cadena vacía.
    """
    try:
        import re

        event_id = request.args.get("event_id", type=int)
        activity_id = request.args.get("activity_id", type=int)

        # Obtener los preregistros con datos relevantes
        q = db.session.query(Registration, Student).join(
            Student, Registration.student_id == Student.id
        )

        if activity_id:
            q = q.filter(Registration.activity_id == activity_id)
        elif event_id:
            # join Activity to filter by event
            q = q.join(Activity, Activity.id == Registration.activity_id).filter(
                Activity.event_id == event_id
            )

        rows = q.all()

        # Determinar la fecha de referencia para calcular semestre.
        # Siempre en hora local de la app: con `datetime.now(timezone.utc)` el
        # corte de mes/año caía a las 18:00 h locales y, cerca de un cambio de
        # mes o de año, un evento de la tarde se clasificaba en el semestre
        # equivocado.
        app_tz = current_app.config.get("APP_TIMEZONE", "America/Mexico_City")
        app_tz_info = app_timezone_info(app_tz)
        ref_date = datetime.now(app_tz_info)
        if activity_id:
            try:
                act = db.session.get(Activity, activity_id)
                if act and getattr(act, "start_datetime", None):
                    rd = localize_naive_datetime(act.start_datetime, app_tz)
                    if rd is not None:
                        ref_date = rd.astimezone(app_tz_info)
            except Exception:
                pass
        elif event_id:
            try:
                ev = db.session.get(Event, event_id)
                if ev and getattr(ev, "start_date", None):
                    rd = localize_naive_datetime(ev.start_date, app_tz)
                    if rd is not None:
                        ref_date = rd.astimezone(app_tz_info)
            except Exception:
                pass

        # Agregar conteos por career/generation pero contando estudiantes únicos
        # Excluir registros con status 'Ausente' o 'Cancelado'
        unique_sets = {}  # { career: { gen: set(student_id) } }
        careers_set = set()
        generations_set = set()
        matrix_semester_sets = {}

        for reg, student in rows:
            # Excluir estados no participativos
            if getattr(reg, "status", None) in ("Ausente", "Cancelado"):
                continue

            career = student.career or "Sin Especificar"
            cn = student.control_number or ""
            m = re.search(r"(\d{2})", cn)
            gen = m.group(1) if m else ""

            # Calcular semestre estimado a partir de la generación y la fecha de referencia
            semester = ""
            if gen:
                try:
                    gy = int(gen)
                    ingreso_year = 2000 + gy
                    month = ref_date.month
                    # Definimos: semestre 1 = Ago-Dic del año de ingreso; semestre 2 = Ene-Jun siguiente
                    event_sem_offset = 1 if 8 <= month <= 12 else 2
                    years_since = max(0, ref_date.year - ingreso_year)
                    sem_number = years_since * 2 + event_sem_offset
                    semester = str(sem_number)
                except Exception:
                    semester = ""

            careers_set.add(career)
            generations_set.add(gen)

            unique_sets.setdefault(career, {})
            unique_sets[career].setdefault(gen, set())
            unique_sets[career][gen].add(student.id)

            # También almacenar por semestre en una estructura similar
            # matrix_semester_sets: { career: { semester: set(student_id) } }
            if semester:
                matrix_semester_sets.setdefault(career, {})
                matrix_semester_sets[career].setdefault(semester, set())
                matrix_semester_sets[career][semester].add(student.id)

        # Convertir sets a contadores
        matrix = {}
        for career, gens in unique_sets.items():
            matrix[career] = {}
            for gen, students_set in gens.items():
                matrix[career][gen] = len(students_set)

        # Convertir sets de semestres a contadores (si existen)
        matrix_semester = {}
        semesters_set = set()
        for career, sems in matrix_semester_sets.items():
            matrix_semester[career] = {}
            for sem, students_set in sems.items():
                matrix_semester[career][sem] = len(students_set)
                semesters_set.add(sem)

        # Ordenar generaciones numéricamente cuando sea posible
        def gen_key(g):
            try:
                return int(g)
            except Exception:
                return 0

        generations = sorted([g for g in generations_set if g != ""], key=gen_key)
        if "" in generations_set:
            generations.insert(0, "")

        careers = sorted(careers_set)

        # Ordenar semestres numéricamente
        semesters = sorted([s for s in semesters_set if s != ""], key=lambda x: int(x))

        # **NUEVO: Calcular rowSubtotals y columnSubtotals en el backend**
        # rowSubtotals: suma de cada fila (por carrera)
        # columnSubtotals: suma de cada columna (por semestre)
        rowSubtotals = {}
        columnSubtotals = {}
        grandTotal = 0

        if semesters:
            # Usar matrix_semester si hay semestres
            for career in careers:
                row_sum = 0
                for sem in semesters:
                    val = matrix_semester.get(career, {}).get(sem, 0)
                    row_sum += val
                    columnSubtotals.setdefault(sem, 0)
                    columnSubtotals[sem] += val
                rowSubtotals[career] = row_sum
                grandTotal += row_sum
        else:
            # Usar matrix si solo hay generaciones
            for career in careers:
                row_sum = 0
                for gen in generations:
                    val = matrix.get(career, {}).get(gen, 0)
                    row_sum += val
                    columnSubtotals.setdefault(gen, 0)
                    columnSubtotals[gen] += val
                rowSubtotals[career] = row_sum
                grandTotal += row_sum

        # Build a simple tabular structure for easier rendering in the UI
        # headers: list of semester/generation labels (strings)
        # rows: list of arrays -> [ career, v1, v2, ..., subtotal ]
        # footer: array -> [ 'Total', c1, c2, ..., grandTotal ]
        matrix_headers = semesters if semesters else generations
        matrix_rows = []
        for career in careers:
            row = [career]
            if matrix_headers:
                for h in matrix_headers:
                    # prefer semester matrix when available, fallback to generation matrix
                    v = (
                        matrix_semester.get(career, {}).get(h)
                        if matrix_semester
                        else None
                    )
                    if v is None:
                        v = matrix.get(career, {}).get(h, 0)
                    row.append(v or 0)
            # append subtotal per career
            row.append(rowSubtotals.get(career, 0))
            matrix_rows.append(row)

        # annotated as List[Any] so static analyzers (Pylance) accept mixed types
        matrix_footer: List[Any] = ["Total"]
        if matrix_headers:
            for h in matrix_headers:
                matrix_footer.append(columnSubtotals.get(h, 0))
        matrix_footer.append(grandTotal)

        return jsonify(
            {
                "careers": careers,
                "generations": generations,
                "matrix": matrix,
                "semesters": semesters,
                "matrix_semester": matrix_semester,
                "rowSubtotals": rowSubtotals,
                "columnSubtotals": columnSubtotals,
                "grandTotal": grandTotal,
                # simplified table structure for frontend
                "matrix_headers": matrix_headers,
                "matrix_rows": matrix_rows,
                "matrix_footer": matrix_footer,
            }
        ), 200
    except Exception as e:
        return jsonify(
            {"message": "Error al generar la matriz de participación", "error": str(e)}
        ), 500


@reports_bp.route("/activity_fill", methods=["GET"])
@jwt_required()
@require_admin
def activity_fill():
    """Devuelve porcentaje de llenado por actividad.

    Query params:
      - event_id (int, optional)
      - activity_id (int, optional)
      - include_unlimited (bool, optional)
    """
    try:
        event_id = request.args.get("event_id", type=int)
        activity_id = request.args.get("activity_id", type=int)
        department = request.args.get("department", type=str)
        include_unlimited = request.args.get("include_unlimited", "0") in (
            "1",
            "true",
            "True",
        )

        # Subquery: conteo de preregistros válidos por actividad
        counts_q = (
            db.session.query(
                Registration.activity_id.label("aid"),
                func.count(Registration.id).label("registered"),
            )
            .filter(~Registration.status.in_(["Ausente", "Cancelado"]))
            .group_by(Registration.activity_id)
            .subquery()
        )

        q = db.session.query(
            Activity.id.label("id"),
            Activity.name.label("name"),
            Activity.modality.label("modality"),
            Activity.event_id.label("event_id"),
            func.coalesce(counts_q.c.registered, 0).label("current_registrations"),
            Activity.max_capacity.label("capacity"),
        ).outerjoin(counts_q, counts_q.c.aid == Activity.id)

        # join event for name
        q = q.outerjoin(Event, Event.id == Activity.event_id).add_columns(
            Event.name.label("event_name")
        )

        if event_id:
            q = q.filter(Activity.event_id == event_id)
        if activity_id:
            q = q.filter(Activity.id == activity_id)
        if department:
            # compare case-insensitive and trimmed to be more tolerant
            try:
                dept_val = department.strip().lower()
                q = q.filter(func.lower(Activity.department) == dept_val)
            except Exception:
                q = q.filter(Activity.department == department)

        results = []
        for row in q.all():
            # row contains activity columns and event_name
            aid = row.id
            name = row.name
            modality = row.modality
            event_name = row.event_name
            capacity = row.capacity
            current = int(row.current_registrations or 0)

            if capacity is None:
                percent = None
                status = "unlimited"
            else:
                try:
                    percent = round((current / float(capacity)) * 100.0, 1)
                except Exception:
                    percent = 0.0
                if current == 0:
                    status = "empty"
                elif current >= capacity:
                    status = "full"
                else:
                    status = "available"

            # Optionally filter out unlimited activities
            if capacity is None and not include_unlimited:
                # skip
                continue

            results.append(
                {
                    "id": aid,
                    "name": name,
                    "modality": modality,
                    "event_id": row.event_id,
                    "event_name": event_name,
                    "capacity": capacity,
                    "current_registrations": current,
                    "percent": percent,
                    "status": status,
                }
            )

        # Include applied filters in response for easier debugging in UI
        applied_filters = {
            "event_id": event_id,
            "activity_id": activity_id,
            "department": department,
            "department_normalized": dept_val if "dept_val" in locals() else None,
        }

        return jsonify({"activities": results, "applied_filters": applied_filters}), 200
    except Exception as e:
        return jsonify(
            {"message": "Error generando reporte de llenado", "error": str(e)}
        ), 500


@reports_bp.route("/event_registrations_txt", methods=["GET"])
@jwt_required()
@require_admin
def event_registrations_txt():
    """Genera y devuelve un .txt con la lista única de estudiantes inscritos en un evento.

    Query params:
      - event_id (int, required)

    Se excluyen registros con status 'Ausente' o 'Cancelado'.
    """
    try:
        event_id = request.args.get("event_id", type=int)
        if not event_id:
            return jsonify({"message": "event_id es requerido"}), 400

        event = db.session.get(Event, event_id)
        if not event:
            return jsonify({"message": "Evento no encontrado"}), 404

        # Consultar estudiantes únicos que tengan preregistros (excluyendo Ausente/Cancelado)
        q = (
            db.session.query(Student)
            .join(Registration, Registration.student_id == Student.id)
            .join(Activity, Activity.id == Registration.activity_id)
            .filter(
                Activity.event_id == event_id,
                ~Registration.status.in_(["Ausente", "Cancelado"]),
            )
            .distinct(Student.id)
            .order_by(Student.full_name)
        )

        students = q.all()

        # Construir contenido de texto: una línea por estudiante con SOLO el número de control
        lines = []
        for s in students:
            cn = (s.control_number or "").strip()
            if not cn:
                # omitimos entradas sin número de control
                continue
            lines.append(f"{cn}")

        content = "\n".join(lines)

        # Generar filename seguro (timestamp en hora local de la app)
        ts = db_now_local().strftime("%Y%m%dT%H%M%S")
        safe_event_name = (event.name or "evento").replace(" ", "_").replace("/", "_")
        filename = f"{safe_event_name}_{ts}.txt"

        resp = Response(content, mimetype="text/plain; charset=utf-8")
        resp.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp
    except Exception as e:
        return jsonify({"message": "Error generando archivo", "error": str(e)}), 500


@reports_bp.route("/hours_compliance", methods=["GET"])
@jwt_required()
@require_admin
def hours_compliance():
    """Devuelve un reporte de cumplimiento de horas por estudiante en un evento.

    Query params:
      - event_id (int, required): ID del evento
      - career (str, optional): Filtrar por carrera/programa educativo
      - search (str, optional): Buscar por número de control o nombre
      - min_hours (float, optional): Horas mínimas acumuladas (default: 0)

    Retorna lista de estudiantes con horas acumuladas basadas en participaciones confirmadas.
    """
    try:
        event_id = request.args.get("event_id", type=int)
        if not event_id:
            return jsonify({"message": "event_id es requerido"}), 400

        event = db.session.get(Event, event_id)
        if not event:
            return jsonify({"message": "Evento no encontrado"}), 404

        career = request.args.get("career", type=str)
        search = request.args.get("search", type=str)
        min_hours = request.args.get("min_hours", type=float, default=0)

        # Cálculo unificado de horas (fuente única de verdad):
        # Registration (Confirmado/Asistió) + Attendance (Asistió), con dedup
        # por actividad y redondeo a 2 decimales antes de comparar umbrales.
        from app.services.hours_service import compute_student_hours

        students = [
            {
                "id": s["id"],
                "control_number": s["control_number"],
                "full_name": s["full_name"],
                "career": s["career"] or "Sin especificar",
                "total_hours": s["total_hours"],
            }
            for s in compute_student_hours(
                event_ids=[event_id],
                career=career,
                search=search,
                min_hours=min_hours,
            )
        ]

        return jsonify(
            {"students": students, "event": {"id": event.id, "name": event.name}}
        ), 200
    except Exception as e:
        current_app.logger.error(f"Error generando reporte de horas: {str(e)}")
        return jsonify({"message": "Error generando reporte de horas"}), 500


@reports_bp.route("/hours_compliance_excel", methods=["GET"])
@jwt_required()
@require_admin
def hours_compliance_excel():
    """Genera archivo Excel con el reporte de cumplimiento de horas.

    Query params: (mismos que /hours_compliance)
      - event_id (int, required)
      - career (str, optional)
      - search (str, optional)
      - min_hours (float, optional)
    """
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment

        # Pylance static typing: import Worksheet to annotate wb.active
        from openpyxl.worksheet.worksheet import Worksheet
        from typing import cast
        import re

        event_id = request.args.get("event_id", type=int)
        if not event_id:
            return jsonify({"message": "event_id es requerido"}), 400

        event = db.session.get(Event, event_id)
        if not event:
            return jsonify({"message": "Evento no encontrado"}), 404

        career = request.args.get("career", type=str)
        search = request.args.get("search", type=str)
        min_hours = request.args.get("min_hours", type=float, default=0)

        # Cálculo unificado de horas (misma fuente que /hours_compliance)
        from app.services.hours_service import compute_student_hours

        results = [
            {
                "control_number": s["control_number"],
                "full_name": s["full_name"],
                "career": s["career"] or "Sin especificar",
                "total_hours": s["total_hours"],
            }
            for s in compute_student_hours(
                event_ids=[event_id],
                career=career,
                search=search,
                min_hours=min_hours,
            )
        ]

        # Crear workbook
        wb = Workbook()
        # cast wb.active to Worksheet so static analyzer knows it's not None
        ws = cast(Worksheet, wb.active)
        ws.title = "Cumplimiento de Horas"

        # Encabezados
        headers = [
            "ID",
            "Número de Control",
            "Nombre Completo",
            "Carrera",
            "Horas Acumuladas",
        ]
        ws.append(headers)

        # Estilo para encabezados
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center")

        # Agregar datos
        for idx, row in enumerate(results, start=1):
            ws.append(
                [
                    idx,
                    row.get("control_number"),
                    row.get("full_name"),
                    row.get("career") or "Sin especificar",
                    round(float(row.get("total_hours") or 0), 2),
                ]
            )

        # Ajustar ancho de columnas
        ws.column_dimensions["A"].width = 8
        ws.column_dimensions["B"].width = 18
        ws.column_dimensions["C"].width = 35
        ws.column_dimensions["D"].width = 30
        ws.column_dimensions["E"].width = 18

        # Generar filename con slug del evento y timestamp (hora local)
        ts = db_now_local().strftime("%Y%m%dT%H%M%S")
        # Crear slug del nombre del evento
        event_slug = re.sub(r"[^\w\s-]", "", event.name.lower())
        event_slug = re.sub(r"[-\s]+", "-", event_slug).strip("-")
        filename = f"{event_slug}_{ts}.xlsx"

        # Guardar en memoria
        from io import BytesIO

        output = BytesIO()
        wb.save(output)
        output.seek(0)

        resp = Response(
            output.getvalue(),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        resp.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp
    except Exception as e:
        current_app.logger.error(f"Error generando archivo Excel: {str(e)}")
        return jsonify({"message": "Error generando archivo Excel"}), 500


@reports_bp.route("/student_participations/<int:student_id>", methods=["GET"])
@jwt_required()
@require_admin
def student_participations(student_id):
    """Devuelve el detalle de participaciones confirmadas de un estudiante en un evento.

    Path params:
      - student_id (int): ID del estudiante

    Query params:
      - event_id (int, required): ID del evento

    Retorna lista de actividades con participación confirmada, ordenadas cronológicamente.
    """
    try:
        event_id = request.args.get("event_id", type=int)
        if not event_id:
            return jsonify({"message": "event_id es requerido"}), 400

        student = db.session.get(Student, student_id)
        if not student:
            return jsonify({"message": "Estudiante no encontrado"}), 404

        # Consultar actividades con participación confirmada (Registration)
        reg_q = (
            db.session.query(
                Activity.id,
                Activity.name,
                Activity.start_datetime,
                Activity.end_datetime,
                Activity.duration_hours,
                Activity.activity_type,
                Activity.location,
                Registration.status,
                Registration.confirmation_date,
            )
            .join(Registration, Registration.activity_id == Activity.id)
            .filter(
                Activity.event_id == event_id,
                Registration.student_id == student_id,
                Registration.status.in_(["Confirmado", "Asistió"]),
            )
        )

        reg_results = reg_q.all()

        # Consultar asistencias (walk-ins) desde Attendance
        from app.models.attendance import Attendance

        att_q = (
            db.session.query(
                Activity.id,
                Activity.name,
                Activity.start_datetime,
                Activity.end_datetime,
                Activity.duration_hours,
                Activity.activity_type,
                Activity.location,
                Attendance.status,
            )
            .join(Attendance, Attendance.activity_id == Activity.id)
            .filter(
                Activity.event_id == event_id,
                Attendance.student_id == student_id,
                Attendance.status == "Asistió",
            )
        )

        att_results = att_q.all()

        # Unir ambos conjuntos evitando duplicados por actividad
        parts_map = {}

        for row in reg_results:
            aid = getattr(row, "id", None)
            parts_map[aid] = {
                "id": aid,
                "name": row.name,
                "start_datetime": row.start_datetime.isoformat()
                if row.start_datetime
                else None,
                "end_datetime": row.end_datetime.isoformat()
                if row.end_datetime
                else None,
                "duration_hours": float(row.duration_hours or 0),
                "activity_type": row.activity_type,
                "location": row.location,
                "status": row.status,
                "confirmation_date": row.confirmation_date.isoformat()
                if row.confirmation_date
                else None,
            }

        for row in att_results:
            aid = getattr(row, "id", None)
            # si ya existe por preregistro, no sobreescribir (evita doble entrada)
            if aid in parts_map:
                continue
            parts_map[aid] = {
                "id": aid,
                "name": row.name,
                "start_datetime": row.start_datetime.isoformat()
                if row.start_datetime
                else None,
                "end_datetime": row.end_datetime.isoformat()
                if row.end_datetime
                else None,
                "duration_hours": float(row.duration_hours or 0),
                "activity_type": row.activity_type,
                "location": row.location,
                # Attendance: usar status y no tenemos confirmation_date por defecto
                "status": getattr(row, "status", "Asistió"),
                "confirmation_date": None,
            }

        # Ordenar participaciones cronológicamente por start_datetime
        participations = sorted(
            list(parts_map.values()),
            key=lambda x: x.get("start_datetime") or "",
        )

        return jsonify(
            {
                "student": {
                    "id": student.id,
                    "control_number": student.control_number,
                    "full_name": student.full_name,
                    "career": student.career,
                },
                "participations": participations,
            }
        ), 200
    except Exception as e:
        current_app.logger.error(f"Error obteniendo participaciones: {str(e)}")
        return jsonify({"message": "Error obteniendo participaciones"}), 500
