"""In-memory pairing mailboxes with optional JSONL / snapshot persistence.

A mailbox is keyed by a short-lived nonce token. The phone writes points;
the console reads them. Nothing here is a device identifier — IMEI,
advertising IDs, and similar keys are rejected rather than stored.
"""

from __future__ import annotations

import json
import math
import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_TTL_S = 2 * 60 * 60
MAX_POINTS = 4000
MAX_INGEST_POINTS = 400
MAX_MAILBOXES = 64
MAX_SPEED_MPS = 120.0
MAX_ACC_M = 10_000.0
ALLOWED_MODES = frozenset({"GNSS", "IDR", "HOLD"})
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")

# Keys we refuse to accept anywhere in an ingest body. Matching one is a
# hard reject so a buggy client cannot leak a device identifier into the log.
FORBIDDEN_DEVICE_KEYS = frozenset(
    {
        "imei",
        "imeisv",
        "imsi",
        "iccid",
        "android_id",
        "androidid",
        "advertising_id",
        "advertisingid",
        "gaid",
        "idfa",
        "idfv",
        "mac",
        "serial",
        "phone",
        "phone_number",
        "email",
        "device_fingerprint",
    }
)
_FORBIDDEN_RE = re.compile(
    r"^(imei|imeisv|imsi|iccid|android_?id|advertising_?id|gaid|idfa|idfv|"
    r"mac|serial|phone(_number)?|email|device_fingerprint)$",
    re.IGNORECASE,
)


def _now() -> float:
    return time.time()


def validate_token(token: Any) -> tuple[str | None, str | None]:
    t = str(token or "").strip()
    if not t:
        return None, "missing token"
    if not TOKEN_RE.fullmatch(t):
        return None, "invalid token"
    return t, None


def _has_forbidden_keys(obj: Any) -> str | None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = str(k).strip()
            if _FORBIDDEN_RE.fullmatch(key) or key.lower() in FORBIDDEN_DEVICE_KEYS:
                return f"device identifier field rejected: {key}"
            nested = _has_forbidden_keys(v)
            if nested:
                return nested
    elif isinstance(obj, list):
        for item in obj:
            nested = _has_forbidden_keys(item)
            if nested:
                return nested
    return None


def _finite_lat_lon(lat: Any, lon: Any) -> tuple[float, float] | str:
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


def _mode(raw: Any) -> tuple[str | None, str | None]:
    m = str(raw if raw is not None else "GNSS").strip().upper()
    if m not in ALLOWED_MODES:
        return None, f"mode must be one of {sorted(ALLOWED_MODES)}"
    return m, None


def _speed(raw: Any) -> tuple[float | None, str | None]:
    if raw is None or raw == "":
        return 0.0, None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None, "speed_mps must be numeric"
    if not math.isfinite(v) or v < 0.0 or v > MAX_SPEED_MPS:
        return None, f"speed_mps out of range [0, {MAX_SPEED_MPS}]"
    return v, None


def _acc(raw: Any) -> tuple[float | None, str | None]:
    if raw is None or raw == "":
        return None, None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None, "acc_m must be numeric"
    if not math.isfinite(v) or v < 0.0 or v > MAX_ACC_M:
        return None, f"acc_m out of range [0, {MAX_ACC_M}]"
    return v, None


def _client_time(raw: Any) -> float | None:
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
    now = _now()
    if t > now + 120.0 or (now - t) > 7 * 86400:
        return None
    return t


def clean_point(row: dict[str, Any], *, token: str) -> dict[str, Any] | str:
    """Return a stored point dict or an error string. Never copies unknown keys."""
    ll = _finite_lat_lon(row.get("lat"), row.get("lon"))
    if isinstance(ll, str):
        return ll
    lat, lon = ll
    mode, err = _mode(row.get("mode"))
    if err:
        return err
    speed, err = _speed(row.get("speed_mps"))
    if err:
        return err
    acc, err = _acc(row.get("acc_m"))
    if err:
        return err
    queued = row.get("queued") in (True, 1, "1", "true", "True")
    t_client = _client_time(row.get("t") if row.get("t") is not None else row.get("t_client"))
    out: dict[str, Any] = {
        "lat": lat,
        "lon": lon,
        "mode": mode,
        "speed_mps": speed,
        "acc_m": acc,
        "queued": queued,
        "token": token,
    }
    if t_client is not None:
        out["t"] = t_client
        out["t_client"] = t_client
    return out


def clean_ingest(payload: dict[str, Any]) -> dict[str, Any] | str:
    forbidden = _has_forbidden_keys(payload)
    if forbidden:
        return forbidden
    token, err = validate_token(payload.get("token"))
    if err:
        return err
    assert token is not None
    if isinstance(payload.get("points"), list):
        points = payload["points"]
        if not points:
            return "empty points"
        if len(points) > MAX_INGEST_POINTS:
            return f"too many points (max {MAX_INGEST_POINTS})"
        cleaned: list[dict[str, Any]] = []
        for p in points:
            if not isinstance(p, dict):
                return "bad point"
            one = clean_point(p, token=token)
            if isinstance(one, str):
                return one
            cleaned.append(one)
        return {"token": token, "points": cleaned}
    one = clean_point(payload, token=token)
    if isinstance(one, str):
        return one
    return {"token": token, "points": [one]}


@dataclass
class Mailbox:
    token: str
    created: float
    expires_at: float
    seq: int = 0
    points: list[dict[str, Any]] = field(default_factory=list)

    def expired(self, now: float) -> bool:
        return now >= self.expires_at

    def touch(self, now: float, ttl_s: float) -> None:
        self.expires_at = now + ttl_s

    def add(self, rows: list[dict[str, Any]], now: float) -> None:
        for row in rows:
            self.seq += 1
            stored = {
                "seq": self.seq,
                "t": row.get("t") or row.get("t_client") or now,
                "lat": row["lat"],
                "lon": row["lon"],
                "mode": row["mode"],
                "speed_mps": row["speed_mps"],
                "acc_m": row.get("acc_m"),
                "queued": bool(row.get("queued")),
            }
            self.points.append(stored)
        if len(self.points) > MAX_POINTS:
            del self.points[: len(self.points) - MAX_POINTS]

    def dump(self) -> dict[str, Any]:
        return {
            "token": self.token,
            "created": self.created,
            "expires_at": self.expires_at,
            "seq": self.seq,
            "points": list(self.points),
        }

    @classmethod
    def load(cls, raw: dict[str, Any]) -> Mailbox:
        return cls(
            token=str(raw["token"]),
            created=float(raw["created"]),
            expires_at=float(raw["expires_at"]),
            seq=int(raw.get("seq") or 0),
            points=list(raw.get("points") or []),
        )


class MailboxStore:
    """Thread-safe token → mailbox map.

    ``persist_dir`` holds one JSON snapshot per token. ``jsonl_path`` is an
    append-only ingest audit (optional; not required to reconstruct state).
    """

    def __init__(
        self,
        *,
        ttl_s: float = DEFAULT_TTL_S,
        persist_dir: str | Path | None = None,
        jsonl_path: str | Path | None = None,
    ) -> None:
        self.ttl_s = float(ttl_s)
        self._lock = threading.Lock()
        self._boxes: dict[str, Mailbox] = {}
        self._persist_dir = Path(persist_dir) if persist_dir else None
        self._jsonl_path = Path(jsonl_path) if jsonl_path else None
        if self._persist_dir:
            self._persist_dir.mkdir(parents=True, exist_ok=True)
            self._load_snapshots()

    def _reap_locked(self, now: float) -> None:
        dead = [t for t, b in self._boxes.items() if b.expired(now)]
        for t in dead:
            del self._boxes[t]
            self._delete_snapshot(t)

    def _snapshot_path(self, token: str) -> Path | None:
        if not self._persist_dir:
            return None
        return self._persist_dir / f"{token}.json"

    def _write_snapshot(self, box: Mailbox) -> None:
        path = self._snapshot_path(box.token)
        if path is None:
            return
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(box.dump(), separators=(",", ":")), encoding="utf-8")
        tmp.replace(path)

    def _delete_snapshot(self, token: str) -> None:
        path = self._snapshot_path(token)
        if path is None:
            return
        try:
            path.unlink()
        except OSError:
            pass

    def _load_snapshots(self) -> None:
        assert self._persist_dir is not None
        now = _now()
        for path in self._persist_dir.glob("*.json"):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(raw, dict) or "token" not in raw:
                    continue
                box = Mailbox.load(raw)
            except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
            if box.expired(now) or not TOKEN_RE.fullmatch(box.token):
                try:
                    path.unlink()
                except OSError:
                    pass
                continue
            self._boxes[box.token] = box

    def _jsonl(self, event: str, payload: dict[str, Any]) -> None:
        if self._jsonl_path is None:
            return
        rec = {"event": event, "t": _now(), **payload}
        try:
            with self._jsonl_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, separators=(",", ":")) + "\n")
        except OSError:
            pass

    def open(self, token: str | None = None) -> dict[str, Any]:
        now = _now()
        with self._lock:
            self._reap_locked(now)
            if token:
                tok, err = validate_token(token)
                if err:
                    return {"ok": False, "error": err}
                assert tok is not None
                existing = self._boxes.get(tok)
                if existing is not None and not existing.expired(now):
                    existing.touch(now, self.ttl_s)
                    self._write_snapshot(existing)
                    self._jsonl("open", {"token": tok, "existing": True})
                    return {
                        "ok": True,
                        "token": tok,
                        "expires_in_s": int(existing.expires_at - now),
                        "existing": True,
                    }
                if len(self._boxes) >= MAX_MAILBOXES:
                    return {"ok": False, "error": f"mailbox limit ({MAX_MAILBOXES}) reached"}
                box = Mailbox(token=tok, created=now, expires_at=now + self.ttl_s)
            else:
                if len(self._boxes) >= MAX_MAILBOXES:
                    return {"ok": False, "error": f"mailbox limit ({MAX_MAILBOXES}) reached"}
                tok = secrets.token_urlsafe(16)
                box = Mailbox(token=tok, created=now, expires_at=now + self.ttl_s)
            self._boxes[box.token] = box
            self._write_snapshot(box)
            self._jsonl("open", {"token": box.token, "existing": False})
            return {
                "ok": True,
                "token": box.token,
                "expires_in_s": int(self.ttl_s),
                "existing": False,
            }

    def ingest(self, payload: dict[str, Any]) -> dict[str, Any]:
        cleaned = clean_ingest(payload)
        if isinstance(cleaned, str):
            return {"ok": False, "error": cleaned}
        token = cleaned["token"]
        batch = cleaned["points"]
        now = _now()
        with self._lock:
            self._reap_locked(now)
            box = self._boxes.get(token)
            if box is None or box.expired(now):
                return {"ok": False, "error": "unknown or expired pairing token"}
            box.touch(now, self.ttl_s)
            box.add(batch, now)
            self._write_snapshot(box)
            self._jsonl("ingest", {"token": token, "n": len(batch)})
            return {
                "ok": True,
                "accepted": len(batch),
                "n_points": len(box.points),
                "expires_in_s": int(box.expires_at - now),
            }

    def feed(
        self,
        token: str,
        *,
        consume: bool = True,
        after: int = 0,
    ) -> dict[str, Any]:
        tok, err = validate_token(token)
        if err:
            return {"ok": False, "error": err}
        assert tok is not None
        now = _now()
        with self._lock:
            self._reap_locked(now)
            box = self._boxes.get(tok)
            if box is None or box.expired(now):
                return {"ok": False, "error": "unknown or expired pairing token"}
            selected = [p for p in box.points if int(p.get("seq") or 0) > after]
            cursor = box.seq
            if consume:
                # Ack: drop everything we just returned (seq > after). seq starts at 1
                # so after=0 (default) clears the mailbox.
                box.points = [p for p in box.points if int(p.get("seq") or 0) <= after]
                self._write_snapshot(box)
                self._jsonl("consume", {"token": tok, "n": len(selected), "cursor": cursor})
            return {
                "ok": True,
                "token": tok,
                "points": selected,
                "n": len(selected),
                "cursor": cursor,
                "expires_in_s": int(box.expires_at - now),
            }

    def stats(self) -> dict[str, Any]:
        now = _now()
        with self._lock:
            self._reap_locked(now)
            return {
                "ok": True,
                "service": "coast-relay",
                "n_mailboxes": len(self._boxes),
                "ttl_s": int(self.ttl_s),
            }
