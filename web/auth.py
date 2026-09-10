"""Operator passcode auth for the COAST console.

Single shared passcode (no user accounts). Hash comes from ``web/operator.txt``
or ``COAST_OPERATOR_HASH``. If neither is set, the console runs in open mode —
no default password is invented.

Hashing prefers Argon2id when the ``argon2`` package is installed; otherwise
PBKDF2-HMAC-SHA256 with ≥600k iterations (stdlib only).
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import threading
import time
from pathlib import Path

try:
    from argon2 import PasswordHasher
    from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError

    _HAS_ARGON2 = True
    _ARGON2 = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=2)
except ImportError:  # pragma: no cover - depends on optional dep
    _HAS_ARGON2 = False
    _ARGON2 = None

# --- public constants -------------------------------------------------------

COOKIE_NAME = "coast_operator"
COOKIE_SAMESITE = "Strict"
IDLE_TIMEOUT_S = 30 * 60
PBKDF2_ITERATIONS = 600_000
PBKDF2_PREFIX = "pbkdf2_sha256"
RATE_LIMIT_MAX = 5
RATE_LIMIT_WINDOW_S = 60.0

OPERATOR_FILE = Path(__file__).resolve().parent / "operator.txt"
ENV_HASH = "COAST_OPERATOR_HASH"

# --- module state -----------------------------------------------------------

_lock = threading.Lock()
_operator_hash: str | None = None
_open_mode: bool = True
_sessions: dict[str, float] = {}  # token -> last_seen monotonic
_attempts: dict[str, list[float]] = {}  # ip -> attempt timestamps


def _read_configured_hash() -> str | None:
    env = os.environ.get(ENV_HASH, "").strip()
    if env:
        return env
    try:
        text = OPERATOR_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return text or None


def reload_config() -> None:
    """Re-read hash from env / operator.txt. Call after test env changes."""
    global _operator_hash, _open_mode
    with _lock:
        h = _read_configured_hash()
        _operator_hash = h
        _open_mode = h is None


def reset_state() -> None:
    """Clear sessions and rate-limit buckets (tests)."""
    with _lock:
        _sessions.clear()
        _attempts.clear()


# Load once at import.
reload_config()


# --- hashing ----------------------------------------------------------------

def hash_passcode(password: str) -> str:
    """Hash a passcode for storage in operator.txt / COAST_OPERATOR_HASH."""
    if _HAS_ARGON2 and _ARGON2 is not None:
        return _ARGON2.hash(password)
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return f"{PBKDF2_PREFIX}${PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def _verify_pbkdf2(password: str, stored: str) -> bool:
    parts = stored.split("$")
    if len(parts) != 4 or parts[0] != PBKDF2_PREFIX:
        return False
    try:
        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        expected = bytes.fromhex(parts[3])
    except ValueError:
        return False
    if iterations < PBKDF2_ITERATIONS:
        return False
    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual, expected)


def _verify_argon2(password: str, stored: str) -> bool:
    assert _ARGON2 is not None
    try:
        return bool(_ARGON2.verify(stored, password))
    except (VerifyMismatchError, VerificationError, InvalidHash):
        return False


# --- public API -------------------------------------------------------------

def is_open_mode() -> bool:
    """True when no operator hash is configured (file or env)."""
    with _lock:
        return _open_mode


def verify_passcode(pw: str) -> bool:
    """Constant-time verify against the configured hash. False in open mode."""
    with _lock:
        stored = _operator_hash
        open_mode = _open_mode
    if open_mode or stored is None:
        return False
    if not isinstance(pw, str):
        return False
    if stored.startswith("$argon2"):
        if not _HAS_ARGON2:
            return False
        return _verify_argon2(pw, stored)
    if stored.startswith(f"{PBKDF2_PREFIX}$"):
        return _verify_pbkdf2(pw, stored)
    # Unknown format — reject without raising.
    return False


def create_session() -> str:
    """Mint a session token (32 random bytes, url-safe). Idle clock starts now."""
    token = secrets.token_urlsafe(32)
    now = time.monotonic()
    with _lock:
        _sessions[token] = now
    return token


def validate_session(cookie: str | None) -> bool:
    """True if cookie names a live session; refreshes idle timeout on success."""
    if not cookie or not isinstance(cookie, str):
        return False
    now = time.monotonic()
    with _lock:
        last = _sessions.get(cookie)
        if last is None:
            return False
        if (now - last) > IDLE_TIMEOUT_S:
            del _sessions[cookie]
            return False
        _sessions[cookie] = now
        return True


def clear_session(cookie: str | None = None) -> None:
    """Drop one session, or all sessions if cookie is None."""
    with _lock:
        if cookie is None:
            _sessions.clear()
            return
        _sessions.pop(cookie, None)


def check_rate_limit(ip: str) -> bool:
    """Record a login attempt for ``ip``.

    Returns True if the attempt is allowed, False if the rate limit has tripped.
    """
    if not ip:
        ip = "unknown"
    now = time.monotonic()
    with _lock:
        bucket = _attempts.setdefault(ip, [])
        # Drop timestamps outside the window.
        cutoff = now - RATE_LIMIT_WINDOW_S
        bucket[:] = [t for t in bucket if t >= cutoff]
        if len(bucket) >= RATE_LIMIT_MAX:
            return False
        bucket.append(now)
        return True


def session_cookie_header(token: str, *, clear: bool = False) -> str:
    """Build a Set-Cookie header value (HttpOnly, SameSite=Strict)."""
    if clear:
        return (
            f"{COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; SameSite={COOKIE_SAMESITE}"
        )
    return (
        f"{COOKIE_NAME}={token}; Path=/; HttpOnly; SameSite={COOKIE_SAMESITE}"
    )


def parse_session_cookie(cookie_header: str | None) -> str | None:
    """Extract our session token from a Cookie request header."""
    if not cookie_header:
        return None
    for part in cookie_header.split(";"):
        name, _, value = part.strip().partition("=")
        if name == COOKIE_NAME:
            return value or None
    return None


# Re-export for tests that assert constant-time compare is available.
compare_digest = hmac.compare_digest

__all__ = [
    "COOKIE_NAME",
    "COOKIE_SAMESITE",
    "IDLE_TIMEOUT_S",
    "PBKDF2_ITERATIONS",
    "RATE_LIMIT_MAX",
    "RATE_LIMIT_WINDOW_S",
    "check_rate_limit",
    "clear_session",
    "compare_digest",
    "create_session",
    "hash_passcode",
    "is_open_mode",
    "parse_session_cookie",
    "reload_config",
    "reset_state",
    "session_cookie_header",
    "validate_session",
    "verify_passcode",
]
