from app import db
from sqlalchemy import event


def _now_local_default():
    """Default de `created_at`/`updated_at`: hora local naive.

    Las columnas `datetime` guardan wall time local (ver `docs/TIMEZONE_FIX.md`).
    `db.func.now()` usa el reloj del servidor MySQL (UTC en producción), y como
    la "Fecha registro" de asistencias se muestra en el admin, salía 6 h
    adelantada (13:19 reales → 19:19 en pantalla). El import se hace dentro de
    la función para evitar ciclos al cargar los modelos.
    """
    from app.utils.datetime_utils import db_now_local

    return db_now_local()


class Attendance(db.Model):
    __tablename__ = "attendances"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey("activities.id"), nullable=False)

    # Solo lo necesario para conferencias magistrales
    check_in_time = db.Column(db.DateTime)
    # Llegada real del estudiante: se congela en el primer check-in y no se
    # toca nunca más. NO sirve usar check_in_time para medir el retraso,
    # porque resume_attendance() lo desplaza al plegar cada pausa (ver
    # attendance_service._arrival_utc).
    arrival_time = db.Column(db.DateTime, nullable=True)
    check_out_time = db.Column(db.DateTime, nullable=True)
    is_paused = db.Column(db.Boolean, default=False)
    pause_time = db.Column(db.DateTime, nullable=True)
    resume_time = db.Column(db.DateTime, nullable=True)

    # Campos calculados
    attendance_percentage = db.Column(db.Float, default=0.0)
    status = db.Column(db.Enum("Asistió", "Parcial", "Ausente"), default="Ausente")
    created_at = db.Column(
        db.DateTime,
        # Calculado en Python (hora local). `server_default` queda solo como
        # respaldo para INSERTs hechos con SQL crudo.
        default=_now_local_default,
        server_default=db.func.now(),
        nullable=False,
    )
    updated_at = db.Column(
        db.DateTime,
        default=_now_local_default,
        server_default=db.func.now(),
        onupdate=_now_local_default,
        nullable=False,
    )

    # Índice compuesto
    __table_args__ = (
        db.UniqueConstraint(
            "student_id", "activity_id", name="unique_student_activity"
        ),
    )

    def __repr__(self):
        return f"<Attendance Student:{self.student_id} Activity:{self.activity_id}>"

    def to_dict(self):
        from app.utils.datetime_utils import safe_iso

        return {
            "id": self.id,
            "student_id": self.student_id,
            "activity_id": self.activity_id,
            "check_in_time": safe_iso(self.check_in_time),
            "arrival_time": safe_iso(self.arrival_time),
            "check_out_time": safe_iso(self.check_out_time),
            "is_paused": self.is_paused,
            "pause_time": safe_iso(self.pause_time),
            "resume_time": safe_iso(self.resume_time),
            "attendance_percentage": self.attendance_percentage,
            "status": self.status,
            "created_at": safe_iso(self.created_at),
            "updated_at": safe_iso(self.updated_at),
        }


def _freeze_arrival_time(target):
    """Congela la llegada real del estudiante en su primer check-in.

    Cubre de una sola vez los ~14 puntos del código que asignan
    ``check_in_time`` (self check-in, walk-ins, subida batch, edición del
    admin…). Sólo se llena si está vacía: los pliegues posteriores de pausa
    (``resume_attendance`` desplaza ``check_in_time``) no deben tocarla, y una
    corrección manual del check-in conserva la primera llegada.

    Se copia **sin convertir** para que quede con la misma forma que
    ``check_in_time`` (naive wall time local o aware): así `_ensure_utc()` la
    interpreta igual a ambas.
    """
    if target.arrival_time is None and target.check_in_time is not None:
        target.arrival_time = target.check_in_time


@event.listens_for(Attendance, "before_insert")
def _arrival_time_on_insert(mapper, connection, target):
    _freeze_arrival_time(target)


@event.listens_for(Attendance, "before_update")
def _arrival_time_on_update(mapper, connection, target):
    _freeze_arrival_time(target)
