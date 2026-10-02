from app import db


class CreditOverride(db.Model):
    """Override manual de crédito complementario por estudiante.

    decision:
      - "include": forzar la inclusión en la lista de créditos complementarios
        aunque la regla derivada (earliest-crossing) lo excluya o no alcance
        el umbral de 10 h.
      - "exclude": omitir al estudiante de la lista de créditos.

    Un estudiante puede tener como máximo una fila (unique en student_id).
    La tabla se crea con la migración aditiva 20261001_add_credit_overrides
    (solo CREATE TABLE).
    """

    __tablename__ = "credit_overrides"

    DECISION_INCLUDE = "include"
    DECISION_EXCLUDE = "exclude"
    VALID_DECISIONS = (DECISION_INCLUDE, DECISION_EXCLUDE)

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer, db.ForeignKey("students.id"), nullable=False, unique=True
    )
    decision = db.Column(db.String(10), nullable=False)
    reason = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        server_default=db.func.now(),
        onupdate=db.func.now(),
        nullable=False,
    )

    student = db.relationship(
        "Student", backref=db.backref("credit_override", uselist=False)
    )

    def __repr__(self):
        return f"<CreditOverride Student:{self.student_id} {self.decision}>"

    def to_dict(self):
        return {
            "student_id": self.student_id,
            "decision": self.decision,
            "reason": self.reason,
        }
