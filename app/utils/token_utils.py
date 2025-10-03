from itsdangerous import URLSafeSerializer, BadSignature
from flask import current_app

SALT = 'activity-token'


def _serializer():
    secret = current_app.config.get('SECRET_KEY', 'fallback-key')
    return URLSafeSerializer(secret, salt=SALT)


def generate_activity_token(activity_id: int) -> str:
    s = _serializer()
    # stable token per activity (no timestamp)
    return s.dumps(str(activity_id))


def verify_activity_token(token: str):
    s = _serializer()
    try:
        val = s.loads(token)
        return int(val), None
    except BadSignature:
        return None, 'invalid'
    except Exception:
        return None, 'invalid'
