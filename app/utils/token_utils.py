from itsdangerous import URLSafeSerializer, BadSignature
from flask import current_app
import hmac
import hashlib
import base64

SALT = 'activity-token'
SQIDS_PREFIX = 's:'  # prefix for sqids-based short tokens
DEFAULT_PREFIX = 'd:'  # prefix for default itsdangerous tokens


def _serializer():
    secret = current_app.config.get('SECRET_KEY', 'fallback-key')
    return URLSafeSerializer(secret, salt=SALT)


def _hmac_sign(data: bytes) -> str:
    secret = current_app.config.get('SECRET_KEY', 'fallback-key')
    sig = hmac.new(secret.encode('utf-8'), data,
                   digestmod=hashlib.sha256).digest()
    # truncate signature to configurable length (bytes)
    trunc = int(current_app.config.get('TOKEN_SIG_TRUNC', 8))
    sig_trunc = sig[:trunc]
    return base64.urlsafe_b64encode(sig_trunc).rstrip(b'=').decode('ascii')


def _hmac_verify(data: bytes, sigb64: str) -> bool:
    try:
        expected = _hmac_sign(data)
        # constant time comparison
        return hmac.compare_digest(expected, sigb64)
    except Exception:
        return False


def generate_activity_token(activity_id: int) -> str:
    """Generate a token for activity_id.

    Behavior:
    - If config ENABLE_SQIDS is True and sqids package is available, generate a compact token:
        's:' + <sqid> + '.' + <sig>
      where sig is a truncated HMAC over the sqid payload to prevent forgery.
    - Otherwise fall back to itsdangerous serializer with prefix 'd:'.
    """
    use_sqids = bool(current_app.config.get('ENABLE_SQIDS', False))
    if use_sqids:
        try:
            from sqids import Sqids

            sq = Sqids()  # default alphabet/params; can be configured via app config later
            sqid = sq.encode([int(activity_id)])
            sig = _hmac_sign(sqid.encode('utf-8'))
            return SQIDS_PREFIX + f"{sqid}.{sig}"
        except Exception:
            # fallback to default
            pass

    s = _serializer()
    return DEFAULT_PREFIX + s.dumps(str(activity_id))


def verify_activity_token(token: str):
    """Verify token and return (activity_id, None) on success or (None, 'invalid') on failure."""
    if not token:
        return None, 'invalid'

    # sqids-based token
    if token.startswith(SQIDS_PREFIX):
        try:
            body = token[len(SQIDS_PREFIX):]
            if '.' not in body:
                return None, 'invalid'
            sqid, sig = body.split('.', 1)
            try:
                from sqids import Sqids

                sq = Sqids()
                vals = sq.decode(sqid)
                if not vals:
                    return None, 'invalid'
                # verify signature
                if not _hmac_verify(sqid.encode('utf-8'), sig):
                    return None, 'invalid'
                return int(vals[0]), None
            except Exception:
                return None, 'invalid'
        except Exception:
            return None, 'invalid'

    # default itsdangerous serialized token
    if token.startswith(DEFAULT_PREFIX):
        raw = token[len(DEFAULT_PREFIX):]
        s = _serializer()
        try:
            val = s.loads(raw)
            return int(val), None
        except BadSignature:
            return None, 'invalid'
        except Exception:
            return None, 'invalid'

    # Backwards-compat: if no prefix present, try default serializer
    try:
        s = _serializer()
        val = s.loads(token)
        return int(val), None
    except Exception:
        return None, 'invalid'
