from flask import Blueprint, request, jsonify, render_template
from flask_jwt_extended import jwt_required
from datetime import timedelta
from app import db
from app.utils.auth_helpers import require_admin
from app.models.registration import Registration
from app.models.activity import Activity
from app.models.event import Event
from app.models.student import Student
from sqlalchemy import func

reports_bp = Blueprint('reports', __name__, url_prefix='/api/reports')


@reports_bp.route('/preregistrations_by_career', methods=['GET'])
@jwt_required()
@require_admin
def preregistrations_by_career():
    """Devuelve conteos de preregistros agrupados por carrera y generación.

    Query params:
      - event_id (int, optional)
      - activity_id (int, optional)

    Generation se deriva del `control_number` tomando los 2 o 4 primeros dígitos según formato.
    """
    try:
        event_id = request.args.get('event_id', type=int)
        activity_id = request.args.get('activity_id', type=int)

        query = db.session.query(
            Student.career.label('career'),
            func.substr(Student.control_number, 1, 4).label('generation'),
            func.count(Registration.id).label('count')
        ).join(Registration, Registration.student_id == Student.id)

        if activity_id:
            query = query.filter(Registration.activity_id == activity_id)
        elif event_id:
            query = query.join(Activity, Activity.id == Registration.activity_id).filter(
                Activity.event_id == event_id)

        query = query.group_by('career', 'generation')

        results = query.all()

        data = []
        for row in results:
            data.append({
                'career': row.career or 'Sin Especificar',
                'generation': (row.generation or '')[:4],
                'count': int(row.count)
            })

        return jsonify({'data': data}), 200
    except Exception as e:
        return jsonify({'message': 'Error al generar estadísticas', 'error': str(e)}), 500


# Ruta HTML imprimible para lista de asistentes (admin)
@reports_bp.route('/attendance_list', methods=['GET'])
@jwt_required()
@require_admin
def attendance_list():
    """Renderiza una página imprimible con la lista de preregistrados para una actividad.

    Query params:
      - activity_id (required)
      - show_generation (bool, optional)
    """
    activity_id = request.args.get('activity_id', type=int)
    if not activity_id:
        return "activity_id es requerido", 400

    activity = db.session.get(Activity, activity_id)
    if not activity:
        return "Actividad no encontrada", 404

    event = db.session.get(Event, activity.event_id)

    # Obtener preregistros ordenados por apellido/nombre (student.full_name)
    regs = db.session.query(Registration).filter(
        Registration.activity_id == activity_id).join(Student).order_by(Student.full_name).all()

    students = []
    for r in regs:
        # Cargar explícitamente el estudiante para evitar supuestos del ORM en el analizador estático
        s = db.session.get(Student, r.student_id)
        if not s:
            continue
        students.append({
            'id': s.id,
            'full_name': s.full_name,
            'control_number': s.control_number,
            'career': s.career,
        })

    # Determine if activity spans multiple days
    multi_day = False
    try:
        start = activity.start_datetime
        end = activity.end_datetime
        if start and end and start.date() != end.date():
            multi_day = True
            # build list of dates inclusive
            delta = (end.date() - start.date()).days
            dates = [start.date() + timedelta(days=i)
                     for i in range(delta + 1)]
        else:
            dates = [start.date()]
    except Exception:
        dates = []

    return render_template('admin/reports/attendance_list.html', event=event, activity=activity, students=students, dates=dates, multi_day=multi_day)


@reports_bp.route('/participation_matrix', methods=['GET'])
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

        event_id = request.args.get('event_id', type=int)
        activity_id = request.args.get('activity_id', type=int)

        # Obtener los preregistros con datos relevantes
        q = db.session.query(Registration, Student).join(
            Student, Registration.student_id == Student.id)

        if activity_id:
            q = q.filter(Registration.activity_id == activity_id)
        elif event_id:
            # join Activity to filter by event
            q = q.join(Activity, Activity.id == Registration.activity_id).filter(
                Activity.event_id == event_id)

        rows = q.all()

        # Determinar la fecha de referencia para calcular semestre
        from datetime import datetime

        ref_date = datetime.utcnow()
        if activity_id:
            try:
                act = db.session.get(Activity, activity_id)
                if act and getattr(act, 'start_datetime', None):
                    ref_date = act.start_datetime
            except Exception:
                pass
        elif event_id:
            try:
                ev = db.session.get(Event, event_id)
                if ev and getattr(ev, 'start_date', None):
                    ref_date = ev.start_date
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
            if getattr(reg, 'status', None) in ('Ausente', 'Cancelado'):
                continue

            career = (student.career or 'Sin Especificar')
            cn = student.control_number or ''
            m = re.search(r"(\d{2})", cn)
            gen = m.group(1) if m else ''

            # Calcular semestre estimado a partir de la generación y la fecha de referencia
            semester = ''
            if gen:
                try:
                    gy = int(gen)
                    ingreso_year = 2000 + gy
                    month = getattr(ref_date, 'month', datetime.utcnow().month)
                    # Definimos: semestre 1 = Ago-Dic del año de ingreso; semestre 2 = Ene-Jun siguiente
                    event_sem_offset = 1 if 8 <= month <= 12 else 2
                    years_since = max(0, ref_date.year - ingreso_year)
                    sem_number = years_since * 2 + event_sem_offset
                    semester = str(sem_number)
                except Exception:
                    semester = ''

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

        generations = sorted(
            [g for g in generations_set if g != ''], key=gen_key)
        if '' in generations_set:
            generations.insert(0, '')

        careers = sorted(careers_set)

        # Ordenar semestres numéricamente
        semesters = sorted(
            [s for s in semesters_set if s != ''], key=lambda x: int(x))

        return jsonify({
            'careers': careers,
            'generations': generations,
            'matrix': matrix,
            'semesters': semesters,
            'matrix_semester': matrix_semester
        }), 200
    except Exception as e:
        return jsonify({'message': 'Error al generar la matriz de participación', 'error': str(e)}), 500
