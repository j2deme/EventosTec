from datetime import datetime, timezone

from app import db


def _utcnow():
    """Fecha/hora actual en UTC sin tzinfo (naive), consistente con `exp` JWT."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class RevokedToken(db.Model):
    """Tokens JWT revocados (logout) para el blocklist de Flask-JWT-Extended.

    Solo se guarda el `jti` mientras el token sigue vigente; las filas se
    purgan oportunamente una vez vencido `exp` porque el token ya es inválido
    por propio vencimiento.
    """

    __tablename__ = "revoked_tokens"

    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), nullable=False, unique=True, index=True)
    revoked_at = db.Column(db.DateTime, default=_utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)

    def __repr__(self):
        return f"<RevokedToken {self.jti}>"
