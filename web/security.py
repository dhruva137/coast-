"""Input hardening helpers for the COAST console.

Additive utilities — body caps, lat/lon validation, rate limits, and
path-safe joins for figures/APK roots. Import from handlers; keep UI code thin.
"""

from __future__ import annotations

import math
import re
import threading
import time
from pathlib import Path
from typing import Any

# POST bodies that are not tiny JSON frames are not part of the pairing contract.
MAX_BODY_BYTES = 262_144
# Hard cap on concurrent paired devices per process (DoS / memory bound).
MAX_DEVICES = 32
MAX_INGEST_POINTS = 400
# Speed: reject absurd values rather than clamping into a plausible track.
MAX_SPEED_MPS = 120.0  # ~430 km/h — above any demo bike, finite and bounded
MAX_ACC_M = 10_000.0
ALLOWED_MODES = frozenset({"GNSS", "IDR", "HOLD"})
# Phone mints 6-digit codes; console may still mint longer URL-safe tokens.
TOKEN_RE = re.compile(r"^(\d{6}|[A-Za-z0-9_-]{6,64})$")
FIGURE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".json"})


class RateLimiter:
    """Simple in-memory token bucket keyed by a string (usually client IP).

    Enough for a demo LAN: no Redis, no persistence across restarts.
    """

    def __init__(self, *, rate: float, per_s: float, burst: float | None = None) -> None:
        self.rate = float(rate)
        self.per_s = float(per_s)
        self.burst = float(burst if burst is not None else rate)
        self._lock = threading.Lock()
        self._buckets: dict[str, tuple[float, float]] = {}  # key -> (tokens, last_t)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        refill = self.rate / self.per_s
        with self._lock:
            tokens, last = self._buckets.get(key, (self.burst, now))
            tokens = min(self.burst, tokens + (now - last) * refill)
            if tokens < 1.0:
                self._buckets[key] = (tokens, now)
                return False
            self._buckets[key] = (tokens - 1.0, now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()


def parse_content_length(headers: Any, *, max_bytes: int = MAX_BODY_BYTES) -> tuple[int | None, str | None]:
    """Return (length, error). length may be 0 for empty bodies.

    Rejects missing/invalid Content-Length when a body is expected by the caller
    checking length separately; here we only enforce the upper bound and parse.
    """
    raw = headers.get("Content-Length") if headers is not None else None
    if raw is None or raw == "":
        return 0, None
    try:
        length = int(raw)
    except (TypeError, ValueError):
        return None, "invalid Content-Length"
    if length < 0:
        return None, "invalid Content-Length"
    if length > max_bytes:
        return None, f"body too large (max {max_bytes} bytes)"
    return length, None


def require_json_content_type(headers: Any) -> str | None:
    """Return an error string if Content-Type is present and not JSON."""
    if headers is None:
        return None
    ct = (headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if not ct:
        # Some phone stacks omit the header; length + json.loads still gates us.
        return None
    if ct not in ("application/json", "text/json"):
        return "Content-Type must be application/json"
    return None


def validate_lat_lon(lat: Any, lon: Any) -> tuple[float, float] | str:
    """Strict lat/lon: numeric, finite, in range. Returns (lat, lon) or error."""
    try:
        la = float(lat)
        lo = float(lon)
    except (TypeError, ValueError):
        return "lat/lon required and must be numeric"
    if not (math.isfinite(la) and math.isfinite(lo)):
        return "lat/lon must be finite"
    if not (-90.0 <= la <= 90.0 and -180.0 <= lo <= 180.0):
        return "lat/lon out of range"
    return (la, lo)


def validate_token(token: Any) -> tuple[str | None, str | None]:
    """Return (token, None) on success or (None, error)."""
    t = str(token or "").strip()
    if not t:
        return None, "missing token"
    if not TOKEN_RE.fullmatch(t):
        return None, "invalid token"
    return t, None


def validate_mode(mode: Any) -> tuple[str | None, str | None]:
    """Allowlist only; reject unknown modes (do not coerce)."""
    m = str(mode if mode is not None else "GNSS").strip().upper()
    if m not in ALLOWED_MODES:
        return None, f"mode must be one of {sorted(ALLOWED_MODES)}"
    return m, None


def validate_speed_mps(speed: Any) -> tuple[float | None, str | None]:
    if speed is None or speed == "":
        return 0.0, None
    try:
        v = float(speed)
    except (TypeError, ValueError):
        return None, "speed_mps must be numeric"
    if not math.isfinite(v) or v < 0.0 or v > MAX_SPEED_MPS:
        return None, f"speed_mps out of range [0, {MAX_SPEED_MPS}]"
    return v, None


def validate_acc_m(acc: Any) -> tuple[float | None, str | None]:
    """Return (value, None). value may be None when acc is omitted."""
    if acc is None or acc == "":
        return None, None
    try:
        v = float(acc)
    except (TypeError, ValueError):
        return None, "acc_m must be numeric"
    if not math.isfinite(v) or v < 0.0 or v > MAX_ACC_M:
        return None, f"acc_m out of range [0, {MAX_ACC_M}]"
    return v, None


def _optional_client_time(raw: Any) -> float | None:
    """Unix seconds from the phone. Rejects far-future / ancient stamps."""
    if raw is None or raw == "":
        return None
    try:
        t = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(t):
        return None
    if t > 1e12:
        t = t / 1000.0
    now = time.time()
    if t > now + 120.0 or (now - t) > 7 * 86400:
        return None
    return t


def validate_ingest_payload(payload: dict[str, Any]) -> dict[str, Any] | str:
    """Validate a pairing ingest object. Returns cleaned fields or an error string."""
    token, err = validate_token(payload.get("token"))
    if err:
        return err

    ll = validate_lat_lon(payload.get("lat"), payload.get("lon"))
    if isinstance(ll, str):
        return ll
    lat, lon = ll

    mode, err = validate_mode(payload.get("mode"))
    if err:
        return err

    speed, err = validate_speed_mps(payload.get("speed_mps"))
    if err:
        return err

    acc, err = validate_acc_m(payload.get("acc_m"))
    if err:
        return err

    queued = payload.get("queued") in (True, 1, "1", "true", "True")
    t_client = _optional_client_time(payload.get("t") if payload.get("t") is not None else payload.get("t_client"))
    return {
        "token": token,
        "lat": lat,
        "lon": lon,
        "mode": mode,
        "speed_mps": speed,
        "acc_m": acc,
        "queued": queued,
        "t_client": t_client,
    }


def validate_ingest_batch(payload: dict[str, Any]) -> dict[str, Any] | str:
    """Validate a store-and-forward flush: token + points[]."""
    token, err = validate_token(payload.get("token"))
    if err:
        return err
    points = payload.get("points")
    if not isinstance(points, list) or not points:
        return "empty points"
    if len(points) > MAX_INGEST_POINTS:
        return f"too many points (max {MAX_INGEST_POINTS})"
    cleaned: list[dict[str, Any]] = []
    for p in points:
        if not isinstance(p, dict):
            return "bad point"
        one = validate_ingest_payload({**p, "token": token})
        if isinstance(one, str):
            return one
        cleaned.append(one)
    return {"token": token, "points": cleaned}


def is_under(path: Path, root: Path) -> bool:
    """True if resolved ``path`` is the same as or inside resolved ``root``."""
    try:
        path = path.resolve()
        root = root.resolve()
        path.relative_to(root)
        return True
    except (OSError, ValueError):
        return False


def safe_join(root: Path, *parts: str) -> Path | None:
    """Join ``parts`` under ``root`` and verify the result stays inside ``root``.

    Rejects empty names, absolute segments, ``..``, and null bytes. Returns
    None on any unsafe input — callers should 400, not coerce.
    """
    if not parts:
        return None
    for part in parts:
        if not part or not isinstance(part, str):
            return None
        if "\x00" in part:
            return None
        # Disallow path separators and drive-absolute tricks before join.
        if "/" in part or "\\" in part:
            return None
        if part in (".", "..") or part.startswith(".."):
            return None
        p = Path(part)
        if p.is_absolute():
            return None
    try:
        candidate = root.joinpath(*parts)
        resolved = candidate.resolve()
        root_resolved = root.resolve()
        resolved.relative_to(root_resolved)
        return resolved
    except (OSError, ValueError):
        return None


def safe_file_under(root: Path, name: str, *, allowed_suffixes: frozenset[str] | None = FIGURE_SUFFIXES) -> Path | None:
    """Resolve a single basename under ``root`` for static figure serving."""
    fp = safe_join(root, name)
    if fp is None:
        return None
    if allowed_suffixes is not None and fp.suffix.lower() not in allowed_suffixes:
        return None
    if not fp.is_file():
        return None
    return fp


def assert_path_in_roots(path: Path, roots: list[Path]) -> bool:
    """True if ``path`` resolves under at least one of ``roots``."""
    try:
        resolved = path.resolve()
    except OSError:
        return False
    for root in roots:
        if is_under(resolved, root):
            return True
    return False
