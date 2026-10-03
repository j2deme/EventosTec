from app import db


class CreditGrant(db.Model):
    """Historial de créditos complementarios otorgados (Fase 3).

    Cada fila registra que un evento fue "gastado" por un estudiante al
    acreditar su crédito complementario (>= 10 h). Un evento gastado ya no
    puede volver a usarse para acumular horas en evaluaciones futuras: si el
    estudiante junta 10 h frescas en otros eventos, acredita OTRO crédito.

    - student_id + event_id: un evento solo se gasta una vez (unicidad como
      red de seguridad contra doble otorgamiento).
    - batch_id: agrupa los grants de una misma acción de otorgamiento (una
      confirmación del admin). Se genera en la aplicación; no hay tabla de
      lotes.
    - granted_by: usuario admin que confirmó el otorgamiento (nullable: el
      usuario pudo ser eliminado después).

    La tabla se crea con la migración aditiva 20261002_add_credit_grants
    (solo CREATE TABLE), encadenada a 20261001_add_credit_overrides.
    """

    __tablename__ = "credit_grants"

    __table_args__ = (
        db.UniqueConstraint(
            "student_id", "event_id", name="uq_credit_grants_student_event"
        ),
        db.Index("ix_credit_grants_batch_id", "batch_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer, db.ForeignKey("students.id"), nullable=False, index=True
    )
    event_id = db.Column(
        db.Integer, db.ForeignKey("events.id"), nullable=False, index=True
    )
    batch_id = db.Column(db.String(36), nullable=False)
    granted_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    granted_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    note = db.Column(db.String(255), nullable=True)

    student = db.relationship(
        "Student", backref=db.backref("credit_grants", lazy="dynamic")
    )
    event = db.relationship(
        "Event", backref=db.backref("credit_grants", lazy="dynamic")
    )

    def __repr__(self):
        return f"<CreditGrant Student:{self.student_id} Event:{self.event_id}>"

    def to_dict(self):
        return {
            "id": self.id,
            "student_id": self.student_id,
            "event_id": self.event_id,
            "batch_id": self.batch_id,
            "granted_by": self.granted_by,
            "granted_at": self.granted_at,
            "note": self.note,
        }
