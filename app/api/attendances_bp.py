from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from datetime import datetime, timezone
from marshmallow import ValidationError
from app.utils.datetime_utils import db_wall_local, parse_datetime_with_timezone
from app import db
from app.schemas import attendance_schema
from app.models.attendance import Attendance
from app.models.student import Student
from app.models.activity import Activity
from app.utils.auth_helpers import require_admin, get_user_or_403
from app.models.registration import Registration
from app.services.attendance_service import has_session_control
import traceback


attendances_bp = Blueprint("attendances", __name__, url_prefix="/api/attendances")


@attendances_bp.route("/pause", methods=["POST"])
@jwt_required()
@require_admin
def pause_attendance():
    try:
        data = request.get_json() or {}
        student_id = data.get("student_id")
        activity_id = data.get("activity_id")

        attendance = Attendance.query.filter_by(
            student_id=student_id, activity_id=activity_id
        ).first()
        if not attendance:
            return jsonify({"message": "No se encontró registro de asistencia"}), 404

        if not attendance.check_in_time:
            return jsonify({"message": "No se ha registrado check-in"}), 400

        if attendance.check_out_time:
            return jsonify({"message": "Ya se ha registrado check-out"}), 400

        from app.services.attendance_service import pause_attendance as svc_pause

        attendance = svc_pause(attendance.id)
        db.session.add(attendance)
        db.session.commit()

        return (
            jsonify(
                {
                    "message": "Asistencia pausada exitosamente",
                    "attendance": attendance_schema.dump(attendance),
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Error al pausar asistencia", "error": str(e)}), 400


@attendances_bp.route("/resume", methods=["POST"])
@jwt_required()
@require_admin
def resume_attendance():
    try:
        data = request.get_json() or {}
        student_id = data.get("student_id")
        activity_id = data.get("activity_id")

        attendance = Attendance.query.filter_by(
            student_id=student_id, activity_id=activity_id
        ).first()
        if not attendance:
            return jsonify({"message": "No se encontró registro de asistencia"}), 404

        if not attendance.is_paused:
            return jsonify({"message": "La asistencia no está pausada"}), 400

        from app.services.attendance_service import resume_attendance as svc_resume

        attendance = svc_resume(attendance.id)
        db.session.add(attendance)
        db.session.commit()

        return (
            jsonify(
                {
                    "message": "Asistencia reanudada exitosamente",
                    "attendance": attendance_schema.dump(attendance),
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        return (
            jsonify({"message": "Error al reanudar asistencia", "error": str(e)}),
            400,
        )


@attendances_bp.route("/", methods=["GET"])
@jwt_required()
def get_attendances():
    try:
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 10, type=int)
        student_id = request.args.get("student_id", type=int)
        activity_id = request.args.get("activity_id", type=int)
        status = request.args.get("status")
        event_id = request.args.get("event_id", type=int)
        activity_type = request.args.get("activity_type")
        search = request.args.get("search", "").strip()

        user, user_type, err = get_user_or_403()
        if err:
            return err

        if user_type == "student" and user is not None:
            student_id = user.id

        query = Attendance.query
        if student_id:
            query = query.filter_by(student_id=student_id)
        if activity_id:
            query = query.filter_by(activity_id=activity_id)
        if status:
            query = query.filter_by(status=status)

        # Join with Activity if we need to filter by event_id or activity_type
        if event_id or activity_type:
            query = query.join(Activity)
            if event_id:
                query = query.filter(Activity.event_id == event_id)
            if activity_type:
                query = query.filter(Activity.activity_type == activity_type)

        # Join with Student if we need to search by student fields
        if search:
            query = query.join(Student)
            query = query.filter(
                db.or_(
                    Student.full_name.ilike(f"%{search}%"),
                    Student.control_number.ilike(f"%{search}%"),
                )
            )

        query = query.order_by(Attendance.created_at.desc())
        # Mantener una referencia a la consulta sin paginar para cálculos agregados
        base_query = query

        total = base_query.count()
        items = query.limit(per_page).offset((page - 1) * per_page).all()
        pages = (total + per_page - 1) // per_page if per_page else 1

        # Estadísticas agregadas sobre toda la consulta (no solo la página)
        try:
            from datetime import date

            # contar asistencias creadas hoy
            stats_today = base_query.filter(
                db.func.date(Attendance.created_at) == date.today()
            ).count()
        except Exception:
            stats_today = 0

        try:
            # walkins: attendances without a matching registration (left outer join)
            walkins_q = base_query.outerjoin(
                Registration,
                db.and_(
                    Registration.student_id == Attendance.student_id,
                    Registration.activity_id == Attendance.activity_id,
                ),
            )
            walkins = walkins_q.filter(Registration.id is None).count()  # type: ignore
        except Exception:
            walkins = 0

        try:
            # converted: attendances with registration and considered present/registered
            converted_q = base_query.join(
                Registration,
                db.and_(
                    Registration.student_id == Attendance.student_id,
                    Registration.activity_id == Attendance.activity_id,
                ),
            )
            converted = converted_q.filter(
                Attendance.status.in_(
                    [
                        "Asistió",
                        "Parcial",
                        "Registrado",
                        "Confirmado",
                        "present",
                        "registered",
                    ]
                )
            ).count()
        except Exception:
            converted = 0

        try:
            # errors: status 'Ausente' or low percentage (<50)
            errors = base_query.filter(
                db.or_(
                    Attendance.status == "Ausente",
                    Attendance.attendance_percentage < 50,
                )
            ).count()
        except Exception:
            errors = 0

        # Serializar y adjuntar objetos relacionados (student, activity) para
        # facilitar el consumo en el frontend sin múltiples requests.
        result = []
        for att in items:
            try:
                dumped = attendance_schema.dump(att)
                # Asegurar que `d` es un dict concreto para evitar errores de typing
                d = dict(dumped) if isinstance(dumped, dict) else {}
            except Exception:
                # Fallback: usar to_dict si hay problemas con el schema
                d = getattr(att, "to_dict", lambda: {})() or {}

            # Adjuntar student y activity anidados cuando estén disponibles
            try:
                if hasattr(att, "student") and att.student is not None:
                    # to_dict expone full_name y control_number
                    d["student"] = att.student.to_dict()
                    # conveniencia: exponer campos planos que espera el frontend
                    d["student_name"] = att.student.full_name
                    d["student_identifier"] = getattr(att.student, "control_number", "")
            except Exception:
                pass

            try:
                if hasattr(att, "activity") and att.activity is not None:
                    d["activity"] = att.activity.to_dict()
                    d["activity_name"] = att.activity.name
                    # intentar añadir nombre de evento si existe la relación
                    if (
                        hasattr(att.activity, "event")
                        and att.activity.event is not None
                    ):
                        d["event_name"] = getattr(att.activity.event, "name", "")
            except Exception:
                pass

            # Intentar adjuntar información de preregistro (registration)
            try:
                # `Registration` fue importado en el módulo
                from sqlalchemy.orm import joinedload

                registration = (
                    Registration.query.options(
                        joinedload(getattr(Registration, "student")),
                        joinedload(getattr(Registration, "activity")),
                    )
                    .filter_by(student_id=att.student_id, activity_id=att.activity_id)
                    .first()
                )
                if registration:
                    d["registration_id"] = registration.id
                    try:
                        # Preferir la serialización via marshmallow schema para incluir nested objects
                        from app.schemas import registration_schema as _reg_schema

                        d["registration"] = _reg_schema.dump(registration)
                    except Exception:
                        # Fallback to to_dict and try to enrich with nested relations
                        rd = (
                            registration.to_dict()
                            if hasattr(registration, "to_dict")
                            else {}
                        )
                        try:
                            if (
                                hasattr(registration, "student")
                                and registration.student is not None
                            ):
                                rd["student"] = registration.student.to_dict()
                        except Exception:
                            pass
                        try:
                            if (
                                hasattr(registration, "activity")
                                and registration.activity is not None
                            ):
                                rd["activity"] = registration.activity.to_dict()
                                if (
                                    hasattr(registration.activity, "event")
                                    and registration.activity.event is not None
                                ):
                                    rd["activity"]["event"] = (
                                        registration.activity.event.to_dict()
                                    )
                        except Exception:
                            pass
                        d["registration"] = rd
            except Exception:
                # No romper la respuesta si por alguna razón falla la consulta
                pass

            result.append(d)

        return (
            jsonify(
                {
                    "attendances": result,
                    "total": total,
                    "pages": pages,
                    "current_page": page,
                    "stats": {
                        "today": stats_today,
                        "walkins": walkins,
                        "converted": converted,
                        "errors": errors,
                    },
                }
            ),
            200,
        )

    except Exception as e:
        return (
            jsonify({"message": "Error al obtener asistencias", "error": str(e)}),
            500,
        )


@attendances_bp.route("/<int:attendance_id>", methods=["GET"])
@jwt_required()
def get_attendance(attendance_id):
    try:
        attendance = db.session.get(Attendance, attendance_id)
        if not attendance:
            return jsonify({"message": "Asistencia no encontrada"}), 404

        user, user_type, err = get_user_or_403()
        if err:
            return err

        if (
            user_type == "student"
            and user is not None
            and attendance.student_id != user.id
        ):
            return jsonify({"message": "Acceso denegado"}), 403

        return jsonify({"attendance": attendance_schema.dump(attendance)}), 200

    except Exception as e:
        return jsonify({"message": "Error al obtener asistencia", "error": str(e)}), 500


@attendances_bp.route("/<int:attendance_id>", methods=["DELETE"])
@jwt_required()
@require_admin
def delete_attendance(attendance_id):
    try:
        attendance = db.session.get(Attendance, attendance_id)
        if not attendance:
            return jsonify({"message": "Asistencia no encontrada"}), 404

        registration = Registration.query.filter_by(
            student_id=attendance.student_id, activity_id=attendance.activity_id
        ).first()
        if registration:
            registration.attended = False
            registration.confirmation_date = None
            registration.status = "Registrado"
            db.session.add(registration)

        db.session.delete(attendance)
        db.session.commit()

        return jsonify({"message": "Asistencia eliminada exitosamente"}), 200

    except Exception as e:
        db.session.rollback()
        return (
            jsonify({"message": "Error al eliminar asistencia", "error": str(e)}),
            500,
        )


@attendances_bp.route("/register", methods=["POST"])
@jwt_required()
@require_admin
def register_attendance():
    try:
        payload = request.get_json() or {}
        student_id = payload.get("student_id")
        activity_id = payload.get("activity_id")
        mark_present = payload.get("mark_present", False)
        check_in = payload.get("check_in_time")
        check_out = payload.get("check_out_time")

        if not student_id or not activity_id:
            return jsonify({"message": "student_id y activity_id son requeridos"}), 400

        student = db.session.get(Student, student_id)
        if not student:
            return jsonify({"message": "Estudiante no encontrado"}), 404

        activity = db.session.get(Activity, activity_id)
        if not activity:
            return jsonify({"message": "Actividad no encontrada"}), 404

        attendance = Attendance.query.filter_by(
            student_id=student_id, activity_id=activity_id
        ).first()
        now = datetime.now(timezone.utc)
        created = False

        if attendance:
            if check_in:
                try:
                    attendance.check_in_time = parse_datetime_with_timezone(check_in)
                except ValidationError as ve:
                    return (
                        jsonify(
                            {
                                "message": "Formato de check_in_time inválido",
                                "error": str(ve),
                            }
                        ),
                        400,
                    )
                except Exception:
                    attendance.check_in_time = db_wall_local(now)
            if check_out:
                try:
                    attendance.check_out_time = parse_datetime_with_timezone(check_out)
                except ValidationError as ve:
                    return (
                        jsonify(
                            {
                                "message": "Formato de check_out_time inválido",
                                "error": str(ve),
                            }
                        ),
                        400,
                    )
                except Exception:
                    attendance.check_out_time = db_wall_local(now)
            if mark_present:
                # Marcar como asistido y asumir 100% cuando se marca manualmente
                # como presente desde el endpoint. Esto hace que la UI/admin
                # considere la asistencia como completa inmediatamente y
                # permite crear asistencias relacionadas.
                attendance.attendance_percentage = 100.0
                attendance.status = "Asistió"
                # Para conferencias (Magistral/Conferencia), si se marca como
                # presente y no se proporcionó check_in_time en el payload,
                # establecer el check-in en 'now' para permitir cálculos
                # posteriores al realizar el checkout.
                try:
                    if has_session_control(activity) and not attendance.check_in_time:
                        attendance.check_in_time = db_wall_local(now)
                except Exception:
                    # No bloquear si la comprobación falla por alguna razón
                    pass
            db.session.add(attendance)
        else:
            created = True
            if mark_present:
                # Crear asistencia marcada como 'Asistió' pero con porcentaje
                # inicial 100.0 y sin tiempos por defecto; así se considera
                # asistencia completa y se pueden crear relacionadas.
                attendance = Attendance()
                attendance.student_id = student_id
                attendance.activity_id = activity_id
                attendance.attendance_percentage = 100.0
                attendance.status = "Asistió"
                attendance.check_in_time = None
                attendance.check_out_time = None
                # Si la actividad tiene control de sesión (Magistral /
                # Conferencia) y no se envió check_in en el payload, asumimos
                # que el walk-in implica check-in ahora para permitir cálculo
                # de porcentaje al hacer checkout.
                try:
                    if has_session_control(activity) and not check_in:
                        attendance.check_in_time = db_wall_local(now)
                except Exception:
                    pass
                if check_in:
                    try:
                        attendance.check_in_time = parse_datetime_with_timezone(
                            check_in
                        )
                    except ValidationError as ve:
                        return (
                            jsonify(
                                {
                                    "message": "Formato de check_in_time inválido",
                                    "error": str(ve),
                                }
                            ),
                            400,
                        )
                    except Exception:
                        attendance.check_in_time = db_wall_local(now)
                if check_out:
                    try:
                        attendance.check_out_time = parse_datetime_with_timezone(
                            check_out
                        )
                    except ValidationError as ve:
                        return (
                            jsonify(
                                {
                                    "message": "Formato de check_out_time inválido",
                                    "error": str(ve),
                                }
                            ),
                            400,
                        )
                    except Exception:
                        attendance.check_out_time = db_wall_local(now)
                # Persistir la nueva asistencia
                db.session.add(attendance)
            else:
                attendance = Attendance()
                attendance.student_id = student_id
                attendance.activity_id = activity_id
                attendance.check_in_time = None
                attendance.check_out_time = None
                attendance.status = (
                    "Parcial" if check_in and not check_out else "Ausente"
                )
                if check_in:
                    try:
                        attendance.check_in_time = parse_datetime_with_timezone(
                            check_in
                        )
                    except ValidationError as ve:
                        return (
                            jsonify(
                                {
                                    "message": "Formato de check_in_time inválido",
                                    "error": str(ve),
                                }
                            ),
                            400,
                        )
                    except Exception:
                        attendance.check_in_time = db_wall_local(now)
                if check_out:
                    try:
                        attendance.check_out_time = parse_datetime_with_timezone(
                            check_out
                        )
                    except ValidationError as ve:
                        return (
                            jsonify(
                                {
                                    "message": "Formato de check_out_time inválido",
                                    "error": str(ve),
                                }
                            ),
                            400,
                        )
                    except Exception:
                        attendance.check_out_time = db_wall_local(now)
                db.session.add(attendance)

        if mark_present:
            registration = Registration.query.filter_by(
                student_id=student_id, activity_id=activity_id
            ).first()
            if registration:
                registration.attended = True
                registration.status = "Asistió"
                registration.confirmation_date = db.func.now()
                db.session.add(registration)

        # Recalcular porcentaje y estado al hacer checkout. Antes solo se
        # persistía check_out_time y una asistencia creada como 'Parcial'
        # (p. ej. self check-in) nunca se actualizaba a 'Asistió'/'Ausente'.
        # mark_present es un override manual (100%): no se recalcula.
        if check_out and not mark_present:
            # Política de cierre: una pausa vigente (el alumno se fue y no
            # volvió, u olvidaron reanudar) SÍ descuenta hasta el check-out.
            # Solo se apaga el indicador; pause_time se conserva para que el
            # cálculo descuente de pause_time a check_out_time.
            if getattr(attendance, "is_paused", False):
                attendance.is_paused = False
                db.session.add(attendance)
            try:
                db.session.flush()
            except Exception:
                pass
            if getattr(attendance, "check_in_time", None):
                try:
                    from app.services.attendance_service import (
                        calculate_attendance_percentage,
                        sync_registration_status,
                    )

                    # El servicio recalcula attendance_percentage y deriva
                    # status (Asistió >= 80%, Parcial, Ausente) sobre la misma
                    # instancia de la sesión. Se expira el objeto para que lea
                    # los valores persistidos (naive en BD): un check_out
                    # recién parseado (aware, zona UTC) en la misma petición
                    # provoca un sesgo de zona horaria frente al check_in
                    # leído de la BD y la ventana de presencia queda invertida.
                    if attendance.id is not None:
                        db.session.expire(attendance)
                    perc = calculate_attendance_percentage(attendance.id)
                    if perc is not None:
                        db.session.add(attendance)
                        # Cierre definitivo: el resultado pasa a la
                        # preregistración (>= 80% -> 'Asistió', < 80% ->
                        # 'Ausente'). Savepoint para que un error aquí no
                        # descarte el checkout ya calculado.
                        try:
                            with db.session.begin_nested():
                                sync_registration_status(attendance)
                        except Exception:
                            current_app.logger.exception(
                                "Error sincronizando la preregistro de la asistencia %s",
                                getattr(attendance, "id", None),
                            )
                except Exception:
                    current_app.logger.exception(
                        "Error recalculando porcentaje de la asistencia %s",
                        getattr(attendance, "id", None),
                    )

        # Si la actividad tiene actividades relacionadas, crear las asistencias
        # relacionadas SOLO si la asistencia principal quedó marcada como
        # 'Asistió' (es decir, mark_present=True o cálculo posterior que deje ese estado).
        try:
            # Crear asistencias relacionadas SOLO si el porcentaje calculado
            # alcanza el umbral mínimo de presencia (ej. 80%). Esto evita que
            # marcar manualmente como 'Asistió' con attendance_percentage=0 provoque
            # la creación inmediata de asistencias relacionadas.
            if (
                getattr(activity, "related_activities", None)
                and getattr(attendance, "attendance_percentage", 0) >= 80
            ):
                from app.services.attendance_service import create_related_attendances

                try:
                    create_related_attendances(student_id, activity_id)
                except Exception:
                    db.session.rollback()
                    raise
        except Exception:
            # no romper si por alguna razón getattr lanza o la importación falla
            pass

        # Flush to ensure generated fields (id, timestamps) are populated, then commit
        try:
            db.session.flush()
        except Exception:
            # flush may fail in some DB backends; fallback to commit directly
            pass

        db.session.commit()

        try:
            db.session.refresh(attendance)
        except Exception:
            # If refresh fails (detached), ignore; serializer can still read fields
            pass

        status_code = 201 if created else 200
        message = "Asistencia creada" if created else "Asistencia actualizada"
        return (
            jsonify(
                {"message": message, "attendance": attendance_schema.dump(attendance)}
            ),
            status_code,
        )

    except Exception as e:
        db.session.rollback()
        return (
            jsonify({"message": "Error al registrar asistencia", "error": str(e)}),
            500,
        )


@attendances_bp.route("/sync-related", methods=["POST"])
@jwt_required()
@require_admin
def sync_related():
    """Endpoint on-demand para sincronizar asistencias desde una actividad fuente hacia actividades relacionadas.

    Payload esperado JSON:
    {
      "source_activity_id": <int>,
      "student_ids": [<int>, ...],   # opcional
      "dry_run": true|false          # opcional, default false
    }
    """
    try:
        payload = request.get_json() or {}
        source_id = payload.get("source_activity_id")
        student_ids = payload.get("student_ids")
        dry_run = bool(payload.get("dry_run", False))

        if not source_id:
            return jsonify({"message": "source_activity_id es requerido"}), 400

        # Resolver semántica del formulario: si la actividad seleccionada
        # tiene un enlace saliente (es decir, apunta hacia otra actividad),
        # la actividad seleccionada se interpreta como *receptora* y la
        # actividad hacia la que apunta será la *fuente* real. En ese caso
        # limitamos la sincronización solo a la actividad receptora para
        # evitar crear asistencias en otros posibles receptores.
        from app.models.activity import Activity
        from app.services.attendance_service import sync_related_attendances_from_source

        target_activity_ids = None
        # Intentar resolver la actividad seleccionada
        sel_activity = db.session.get(Activity, source_id)
        if sel_activity:
            out_links = list(getattr(sel_activity, "related_activities", []) or [])
            if out_links:
                # La actividad seleccionada apunta a otra -> interpretarla como receptora
                real_source = getattr(out_links[0], "id", None)
                # Limitar targets a la actividad seleccionada
                target_activity_ids = [source_id]
                source_to_use = real_source or source_id
            else:
                source_to_use = source_id
        else:
            source_to_use = source_id

        try:
            summary = sync_related_attendances_from_source(
                source_to_use,
                student_ids=student_ids,
                dry_run=dry_run,
                target_activity_ids=target_activity_ids,
            )
        except ValueError as ve:
            return jsonify({"message": str(ve)}), 404

        # Enviar información de la fuente resuelta y la actividad seleccionada
        try:
            resolved = None
            src_act = db.session.get(Activity, source_to_use)
            if src_act:
                resolved = {
                    "id": getattr(src_act, "id", None),
                    "name": getattr(src_act, "name", None),
                }
        except Exception:
            resolved = None

        selected_info = None
        try:
            sel_act = db.session.get(Activity, source_id)
            if sel_act:
                selected_info = {
                    "id": getattr(sel_act, "id", None),
                    "name": getattr(sel_act, "name", None),
                }
        except Exception:
            selected_info = None

        status_code = 200 if dry_run else 201
        return (
            jsonify(
                {
                    "message": "Sincronizaci\u00f3n completada",
                    "dry_run": dry_run,
                    "summary": summary,
                    "resolved_source": resolved,
                    "selected_activity": selected_info,
                }
            ),
            status_code,
        )

    except Exception as e:
        return (
            jsonify({"message": "Error en sincronizaci\u00f3n", "error": str(e)}),
            500,
        )


@attendances_bp.route("/batch-checkout", methods=["POST"])
@jwt_required()
@require_admin
def batch_checkout():
    """Cierra las asistencias abiertas de una actividad y recalcula su estado.

    - Marca ``check_out_time`` (por defecto "ahora") en las sesiones abiertas.
    - Recalcula ``attendance_percentage``/``status`` (>= 80% -> 'Asistió').
    - **Sincroniza la preregistración**: >= 80% -> 'Asistió', < 80% ->
      'Ausente' (el alumno llegó pero no completó la actividad, así que no
      acredita). Ver ``attendance_service.sync_registration_status``.
    - Crea las asistencias relacionadas de las que alcanzan el umbral.

    Política de pausas: una pausa vigente al cierre **sí descuenta** el
    tiempo hasta el check-out (el alumno que se fue y no volvió no debe
    acreditar); solo se apaga el indicador de pausa.

    Payload::

        {
          "activity_id": <int>,
          "student_ids": [<int>, ...],   # opcional
          "dry_run": true|false          # opcional, default true
        }

    Returns: ``{ processed, updated, related_created, resumed_paused, details }``
    ``details`` incluye ``percentage``, ``related_created`` y
    ``registration_status`` (estado que quedará en la preregistro, si existe).
    """
    try:
        payload = request.get_json() or {}
        activity_id = payload.get("activity_id")
        student_ids = payload.get("student_ids")
        dry_run = bool(payload.get("dry_run", True))

        if not activity_id:
            return jsonify({"message": "activity_id es requerido"}), 400

        from app.services.attendance_service import (
            calculate_attendance_percentage,
            compute_attendance_metrics,
            create_related_attendances,
            sync_registration_status,
        )
        from app.models.attendance import Attendance
        from app.models.activity import Activity

        activity = db.session.get(Activity, activity_id)
        if not activity:
            return jsonify({"message": "Actividad no encontrada"}), 404

        query = Attendance.query.filter_by(activity_id=activity_id)
        if student_ids:
            query = query.filter(Attendance.student_id.in_(student_ids))

        att_list = query.all()

        summary = {
            "processed": 0,
            "updated": 0,
            "related_created": 0,
            "resumed_paused": 0,
            "details": [],
        }

        for att in att_list:
            summary["processed"] += 1
            # If there's no check_in_time, skip (cannot calculate)
            if not att.check_in_time:
                summary["details"].append(
                    {
                        "attendance_id": att.id,
                        "action": "skipped",
                        "reason": "no_check_in",
                    }
                )
                continue

            # If check_out_time missing, set it to now for the purpose of calculation
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc)
            if not att.check_out_time:
                if not dry_run:
                    att.check_out_time = db_wall_local(now)
                # otherwise, emulate for calculation
                emulate_check_out = now
            else:
                emulate_check_out = att.check_out_time

            # Cierre de sesiones pausadas: la pausa vigente SÍ descuenta hasta
            # el check-out (el alumno que se fue y no volvió no debe
            # acreditar). Solo se apaga el indicador de pausa; pause_time se
            # conserva para que el cálculo descuente de pause_time a check_out.
            if getattr(att, "is_paused", False):
                summary["resumed_paused"] += 1
                if not dry_run:
                    att.is_paused = False
                    db.session.add(att)
                    try:
                        db.session.flush()
                    except Exception:
                        pass

            # Calcular porcentaje.
            # - dry_run: cálculo puro, sin tocar la sesión de la BD.
            # - real: se persiste vía el servicio y se cierra la preregistro.
            perc = None
            if dry_run:
                try:
                    metrics = compute_attendance_metrics(
                        att,
                        activity,
                        now=now,
                        check_out_override=emulate_check_out,
                    )
                    perc = metrics[0] if metrics else 0.0
                except Exception:
                    current_app.logger.exception(
                        "batch-checkout: error calculando el dry-run (asistencia %s)",
                        getattr(att, "id", None),
                    )
                    perc = 0.0
            else:
                # Persist check_out time if missing, then calculate via service
                if not att.check_out_time:
                    att.check_out_time = db_wall_local(now)
                db.session.add(att)
                try:
                    db.session.flush()
                except Exception:
                    pass

                perc = calculate_attendance_percentage(att.id)

                # Cierre definitivo: el resultado pasa a la preregistración
                # (>= 80% -> 'Asistió', < 80% -> 'Ausente'). Savepoint para
                # que un error aquí no descarte el checkout ya calculado.
                if perc is not None:
                    try:
                        with db.session.begin_nested():
                            sync_registration_status(att)
                    except Exception:
                        current_app.logger.exception(
                            "batch-checkout: error sincronizando preregistro "
                            "(asistencia %s)",
                            getattr(att, "id", None),
                        )

                # Persist updates from service
                db.session.add(att)
                db.session.commit()
                db.session.refresh(att)

            # If the recalculated percentage meets threshold, create related attendances
            created_related = 0
            if (perc or 0) >= 80:
                # Only create related attendances when not dry_run
                if not dry_run and getattr(activity, "related_activities", None):
                    create_related_attendances(att.student_id, activity_id)
                    created_related = 1

            # Estado que quedará en la preregistración (si existe)
            registration_status = None
            if perc is not None:
                has_registration = Registration.query.filter_by(
                    student_id=att.student_id, activity_id=activity_id
                ).first()
                if has_registration is not None:
                    registration_status = "Asistió" if (perc or 0) >= 80 else "Ausente"

            summary["details"].append(
                {
                    "attendance_id": att.id,
                    "percentage": perc or 0,
                    "related_created": created_related,
                    "registration_status": registration_status,
                }
            )
            summary["updated"] += 1
            summary["related_created"] += created_related

        if not dry_run:
            # commit already performed per-attendance
            pass

        return (
            jsonify(
                {
                    "message": "Batch checkout completado",
                    "dry_run": dry_run,
                    "summary": summary,
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Error en batch checkout", "error": str(e)}), 500


@attendances_bp.route("/batch", methods=["POST"])
@jwt_required()
@require_admin
def batch_upload_attendances():
    """Upload a TXT or XLSX file containing control numbers and create attendances in batch.

    Form data:
      - file: the TXT or XLSX file (required)
      - activity_id: the activity ID (required)
      - dry_run: optional (1/0) default 1 -> if 1 only validate and return report
    """
    try:
        if "file" not in request.files:
            return jsonify({"message": "Falta el archivo."}), 400

        file = request.files["file"]
        activity_id = request.form.get("activity_id")
        dry_run = request.form.get("dry_run", "1")
        dry = str(dry_run).strip() in ("1", "true", "yes")

        if not activity_id:
            return jsonify({"message": "activity_id es requerido"}), 400

        # Determine mode: entry (create) or exit (mark_absent/delete)
        mode = request.form.get("mode", "entry").strip().lower()
        action = request.form.get("action", "mark_absent").strip().lower()

        if mode == "exit":
            from app.services.attendance_service import process_exit_from_file

            report = process_exit_from_file(
                file.stream, activity_id=int(activity_id), dry_run=dry, action=action
            )
        else:
            # default: create attendances (existing behavior)
            from app.services.attendance_service import create_attendances_from_file

            report = create_attendances_from_file(
                file.stream, activity_id=int(activity_id), dry_run=dry
            )

        status_code = 200 if dry else 201
        # Exponer explicitamente si la operación fue dry_run en la respuesta
        return (
            jsonify(
                {"message": "Batch procesado", "report": report, "dry_run": bool(dry)}
            ),
            status_code,
        )

    except Exception as e:
        tb = traceback.format_exc()
        return (
            jsonify(
                {"message": "Error en importación batch", "error": str(e), "trace": tb}
            ),
            500,
        )
