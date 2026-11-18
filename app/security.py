"""Password hashing (Argon2id), signed sessions and CSRF tokens."""

import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .config import settings

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:  # noqa: BLE001 — a malformed hash must not grant access
        return False


def client_ip(request) -> str | None:
    """Real client address, honouring a reverse proxy (nginx, Cloudflare)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    return request.client.host if request.client else None


# ==========================================================================
#  Dashboard session
# ==========================================================================
#  The session is a signed cookie, not an encrypted one: its contents are
#  readable but cannot be forged without the secret key. Only the user id
#  goes in, so there is nothing sensitive to read.

SESSION_COOKIE = "ccpa_session"
CSRF_COOKIE = "ccpa_csrf"
SESSION_MAX_AGE = 60 * 60 * 12  # 12 hours


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key, salt="admin-session")


def create_session_token(user_id: str) -> str:
    return _serializer().dumps({"uid": user_id})


def read_session_token(token: str | None) -> str | None:
    """Return the user id, or None if the cookie is invalid or expired."""
    if not token:
        return None
    try:
        payload = _serializer().loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    return payload.get("uid")


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def csrf_matches(cookie: str | None, submitted: str | None) -> bool:
    """Double-submit pattern: the cookie token must equal the form token.

    Compared in constant time so the value cannot be probed byte by byte.
    """
    if not cookie or not submitted:
        return False
    return hmac.compare_digest(cookie, submitted)
