from itsdangerous import URLSafeSerializer, BadSignature
from flask import current_app
import hmac
import hashlib
import base64

SALT = "activity-token"
SQIDS_PREFIX = "s:"  # prefix for sqids-based short tokens
DEFAULT_PREFIX = "d:"  # prefix for default itsdangerous tokens
PUBLIC_PREFIX = "p:"
SALT_PUBLIC = "public-activity-token"
SALT_PUBLIC_EVENT = "public-event-token"


def _serializer():
    secret = current_app.config.get("SECRET_KEY", "fallback-key")
    return URLSafeSerializer(secret, salt=SALT)


def _hmac_sign(data: bytes) -> str:
    secret = current_app.config.get("SECRET_KEY", "fallback-key")
    sig = hmac.new(secret.encode("utf-8"), data, digestmod=hashlib.sha256).digest()
    # truncate signature to configurable length (bytes)
    trunc = int(current_app.config.get("TOKEN_SIG_TRUNC", 8))
    sig_trunc = sig[:trunc]
    return base64.urlsafe_b64encode(sig_trunc).rstrip(b"=").decode("ascii")


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
    use_sqids = bool(current_app.config.get("ENABLE_SQIDS", False))
    if use_sqids:
        try:
            from sqids import Sqids

            sq = (
                Sqids()
            )  # default alphabet/params; can be configured via app config later
            sqid = sq.encode([int(activity_id)])
            sig = _hmac_sign(sqid.encode("utf-8"))
            return SQIDS_PREFIX + f"{sqid}.{sig}"
        except Exception:
            # fallback to default
            pass

    s = _serializer()
    return DEFAULT_PREFIX + s.dumps(str(activity_id))


def verify_activity_token(token: str):
    """Verify token and return (activity_id, None) on success or (None, 'invalid') on failure."""
    if not token:
        return None, "invalid"

    # sqids-based token
    if token.startswith(SQIDS_PREFIX):
        try:
            body = token[len(SQIDS_PREFIX) :]
            if "." not in body:
                return None, "invalid"
            sqid, sig = body.split(".", 1)
            try:
                from sqids import Sqids

                sq = Sqids()
                vals = sq.decode(sqid)
                if not vals:
                    return None, "invalid"
                # verify signature
                if not _hmac_verify(sqid.encode("utf-8"), sig):
                    return None, "invalid"
                return int(vals[0]), None
            except Exception:
                return None, "invalid"
        except Exception:
            return None, "invalid"

    # default itsdangerous serialized token
    if token.startswith(DEFAULT_PREFIX):
        raw = token[len(DEFAULT_PREFIX) :]
        s = _serializer()
        try:
            val = s.loads(raw)
            return int(val), None
        except BadSignature:
            return None, "invalid"
        except Exception:
            return None, "invalid"

    # Backwards-compat: if no prefix present, try default serializer
    try:
        s = _serializer()
        val = s.loads(token)
        return int(val), None
    except Exception:
        return None, "invalid"


def _public_serializer():
    secret = current_app.config.get("SECRET_KEY", "fallback-key")
    return URLSafeSerializer(secret, salt=SALT_PUBLIC)


def generate_public_token(activity_id: int) -> str:
    """Generate a token for public chief access distinct from self-register tokens."""
    s = _public_serializer()
    return PUBLIC_PREFIX + s.dumps(str(activity_id))


def verify_public_token(token: str):
    if not token:
        return None, "invalid"
    if token.startswith(PUBLIC_PREFIX):
        raw = token[len(PUBLIC_PREFIX) :]
        s = _public_serializer()
        try:
            val = s.loads(raw)
            return int(val), None
        except BadSignature:
            return None, "invalid"
        except Exception:
            return None, "invalid"
    return None, "invalid"


def _public_event_serializer():
    secret = current_app.config.get("SECRET_KEY", "fallback-key")
    return URLSafeSerializer(secret, salt=SALT_PUBLIC_EVENT)


def generate_public_event_token(event_id: int) -> str:
    """Generate a token for event-level chief access."""
    s = _public_event_serializer()
    return "pe:" + s.dumps(str(event_id))


def verify_public_event_token(token: str):
    if not token:
        return None, "invalid"
    if token.startswith("pe:"):
        raw = token[len("pe:") :]
        s = _public_event_serializer()
        try:
            val = s.loads(raw)
            return int(val), None
        except BadSignature:
            return None, "invalid"
        except Exception:
            return None, "invalid"
    return None, "invalid"
