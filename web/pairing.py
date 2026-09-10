"""Phone-to-console pairing, fleet state, and QR generation.

A judge scans a QR on the laptop screen, their phone posts position, and their
device appears on the console map. Multiple phones at once — that is the fleet
view, and it is also the logistics use case the pitch describes.

Design notes that matter for the demo
-------------------------------------
**The QR carries two endpoints, not one.** Venue wifi commonly runs AP isolation
(clients can reach the internet but not each other), which would silently kill a
phone→laptop POST with a connection timeout rather than an error. So the payload
names both a LAN base and an optional relay, and the app races them. Running the
laptop as a hotspot puts it at a fixed 192.168.137.1 and sidesteps isolation
entirely.

**The token is a nonce, not a credential.** Same shape as WhatsApp Web or Google
device pairing: the QR carries a short-lived one-time value, and the phone's
first POST is what activates the session and binds it. Nothing sensitive travels
in the code.

**No device identifiers.** A device is labelled with a name the console assigns
(Judge-1, Judge-2) and keyed by a random id minted at pairing. We deliberately
never receive an IMEI, advertising id, or account, so re-identifying a phone
across sessions is impossible by construction rather than by policy — which is
what makes the privacy panel honest.
"""

from __future__ import annotations

import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

try:  # pragma: no cover - import shim
    from web.security import MAX_DEVICES, validate_ingest_batch, validate_ingest_payload, validate_token
except ImportError:  # pragma: no cover
    from security import MAX_DEVICES, validate_ingest_batch, validate_ingest_payload, validate_token  # type: ignore

# Public store-and-forward host encoded in the QR when COAST_RELAY_BASE is unset.
# Not claimed deployed by this repo — set COAST_RELAY_BASE to a running relay,
# or `off` for LAN-only. See relay/README.md.
DEFAULT_RELAY_BASE = "https://coast.paper2anything.com"

# Session lifetime. Short, because a pairing code that lingers is a pairing code
# that leaks.
SESSION_TTL_S = 15 * 60
# Device is considered offline (greyed, not removed) after this long with no post.
STALE_S = 12.0
# Cap per device so a long demo cannot exhaust memory.
MAX_POINTS = 4000

# One colour per device, used consistently for its marker, its track and its
# list row — that is how a viewer tracks "which one is mine" without reading.
PALETTE = [
    "#00D4AA",
    "#FF6B2D",
    "#4A9EFF",
    "#C88BFF",
    "#FFD166",
    "#FF5C8A",
    "#5CE1E6",
    "#9BE564",
]


@dataclass
class Point:
    t: float
    lat: float
    lon: float
    mode: str
    speed_mps: float
    acc_m: float | None = None
    queued: bool = False

    def as_json(self) -> dict[str, Any]:
        out = {
            "t": round(self.t, 3),
            "lat": self.lat,
            "lon": self.lon,
            "mode": self.mode,
            "speed_mps": round(self.speed_mps, 3),
            "acc_m": self.acc_m,
        }
        if self.queued:
            out["queued"] = True
        return out


@dataclass
class Device:
    device_id: str
    label: str
    color: str
    first_seen: float
    last_seen: float
    points: list[Point] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    _last_mode: str | None = None

    def add(self, p: Point) -> None:
        # A mode change is the narrative beat of the whole demo — the moment the
        # phone lost GNSS and kept going. Record it as a timeline event.
        if self._last_mode is not None and p.mode != self._last_mode:
            self.events.append(
                {
                    "t": round(p.t, 3),
                    "from": self._last_mode,
                    "to": p.mode,
                    "lat": p.lat,
                    "lon": p.lon,
                }
            )
            if len(self.events) > 200:
                del self.events[:-200]
        self._last_mode = p.mode
        self.points.append(p)
        if len(self.points) > MAX_POINTS:
            del self.points[: len(self.points) - MAX_POINTS]
        self.last_seen = p.t

    def distance_m(self) -> float:
        if len(self.points) < 2:
            return 0.0
        import math

        total = 0.0
        for a, b in zip(self.points, self.points[1:]):
            dlat = math.radians(b.lat - a.lat)
            dlon = math.radians(b.lon - a.lon)
            mlat = math.radians((a.lat + b.lat) * 0.5)
            total += math.hypot(dlat, dlon * math.cos(mlat)) * 6_371_000.0
        return total

    def as_json(self, now: float, *, with_points: bool = True) -> dict[str, Any]:
        latest = self.points[-1] if self.points else None
        idr = sum(1 for p in self.points if p.mode.upper() == "IDR")
        queued_n = sum(1 for p in self.points if p.queued)
        return {
            "device_id": self.device_id,
            "label": self.label,
            "color": self.color,
            "online": (now - self.last_seen) < STALE_S,
            "age_s": round(now - self.last_seen, 1),
            "first_seen": round(self.first_seen, 3),
            "last_seen": round(self.last_seen, 3),
            "n_points": len(self.points),
            "n_idr_points": idr,
            "n_queued_points": queued_n,
            "distance_m": round(self.distance_m(), 1),
            "latest": latest.as_json() if latest else None,
            "events": list(self.events),
            "points": [p.as_json() for p in self.points] if with_points else [],
        }


@dataclass
class Session:
    token: str
    created: float
    device_id: str | None = None

    def expired(self, now: float) -> bool:
        return self.device_id is None and (now - self.created) > SESSION_TTL_S


class Fleet:
    """All pairing sessions and paired devices. Thread-safe; the HTTP handler
    is multi-threaded and the phone posts from a different thread than the UI."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, Session] = {}
        self._devices: dict[str, Device] = {}
        self._n_paired = 0

    # -- pairing ---------------------------------------------------------

    def new_session(self) -> Session:
        return self.open_session(None)

    def open_session(self, token: str | None = None) -> Session:
        """Mint a nonce, or adopt a token typed from the phone.

        Invalid tokens raise ValueError so the HTTP layer can 400.
        """
        now = time.time()
        with self._lock:
            self._reap(now)
            if token:
                tok, err = validate_token(token)
                if err:
                    raise ValueError(err)
                assert tok is not None
                existing = self._sessions.get(tok)
                if existing is not None and not existing.expired(now):
                    return existing
                s = Session(token=tok, created=now)
            else:
                s = Session(token=secrets.token_urlsafe(16), created=now)
            self._sessions[s.token] = s
            return s

    def keep_alive(self, token: str) -> bool:
        """Extend an unpaired session while the console is polling the relay."""
        now = time.time()
        with self._lock:
            s = self._sessions.get(token)
            if s is None:
                return False
            if s.device_id is None:
                s.created = now
            return True

    def active_tokens(self) -> list[str]:
        """Tokens the console should pull from the relay mailbox."""
        now = time.time()
        with self._lock:
            self._reap(now)
            return list(self._sessions.keys())

    def _reap(self, now: float) -> None:
        for tok in [t for t, s in self._sessions.items() if s.expired(now)]:
            del self._sessions[tok]

    def _claim(self, token: str, now: float) -> Device | None | str:
        """Bind a device to a session on its first post. Returns None if the
        token is unknown or expired — an unknown token must never silently
        create a device, or the endpoint becomes an open write.

        Returns the string 'device limit' if MAX_DEVICES would be exceeded.
        """
        s = self._sessions.get(token)
        if s is None or s.expired(now):
            return None
        if s.device_id and s.device_id in self._devices:
            return self._devices[s.device_id]
        if len(self._devices) >= MAX_DEVICES:
            return "device limit"
        self._n_paired += 1
        did = secrets.token_urlsafe(8)
        dev = Device(
            device_id=did,
            label=f"Judge-{self._n_paired}",
            color=PALETTE[(self._n_paired - 1) % len(PALETTE)],
            first_seen=now,
            last_seen=now,
        )
        self._devices[did] = dev
        s.device_id = did
        return dev

    # -- ingest ----------------------------------------------------------

    def ingest(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = time.time()
        if isinstance(payload.get("points"), list):
            cleaned = validate_ingest_batch(payload)
        else:
            one = validate_ingest_payload(payload)
            cleaned = {"token": one["token"], "points": [one]} if not isinstance(one, str) else one
        if isinstance(cleaned, str):
            return {"ok": False, "error": cleaned}
        token = cleaned["token"]
        batch = cleaned["points"]

        with self._lock:
            self._reap(now)
            dev = self._claim(token, now)
            if dev == "device limit":
                return {"ok": False, "error": f"device limit ({MAX_DEVICES}) reached"}
            if dev is None:
                return {"ok": False, "error": "unknown or expired pairing token"}
            for row in batch:
                t = row.get("t_client") or now
                dev.add(
                    Point(
                        t=t,
                        lat=row["lat"],
                        lon=row["lon"],
                        mode=row["mode"],
                        speed_mps=row["speed_mps"],
                        acc_m=row["acc_m"],
                        queued=bool(row.get("queued")),
                    )
                )
            # last_seen is radio contact, not the GPS clock on a queued point.
            dev.last_seen = now
            return {
                "ok": True,
                "device_id": dev.device_id,
                "label": dev.label,
                "color": dev.color,
                "n_points": len(dev.points),
                "accepted": len(batch),
            }

    # -- read / delete ---------------------------------------------------

    def snapshot(self, *, with_points: bool = True) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            devs = [d.as_json(now, with_points=with_points) for d in self._devices.values()]
            pending = sum(1 for s in self._sessions.values() if s.device_id is None)
        devs.sort(key=lambda d: d["first_seen"])
        return {
            "t": now,
            "devices": devs,
            "n_devices": len(devs),
            "n_online": sum(1 for d in devs if d["online"]),
            "pending_sessions": pending,
        }

    def privacy_report(self, device_id: str) -> dict[str, Any] | None:
        """Exactly what we hold about one device, for the console's
        'what we know about you' panel. If a field is not worth showing a
        judge, we should not be collecting it."""
        now = time.time()
        with self._lock:
            dev = self._devices.get(device_id)
            if dev is None:
                return None
            return {
                "device_id": dev.device_id,
                "label": dev.label,
                "held": {
                    "label": dev.label,
                    "positions_received": len(dev.points),
                    "first_seen": round(dev.first_seen, 3),
                    "last_seen": round(dev.last_seen, 3),
                    "path_distance_m": round(dev.distance_m(), 1),
                    "mode_transitions": len(dev.events),
                },
                "not_collected": [
                    "Device identifier, IMEI, or advertising ID",
                    "Phone number, email, or any account",
                    "Contacts, photos, or any other app's data",
                    "Anything at all while the app is closed",
                ],
                "age_s": round(now - dev.first_seen, 1),
            }

    def forget(self, device_id: str) -> bool:
        """Delete a device and everything held about it. Pressed in front of the
        judge; must actually remove the data, not hide it."""
        with self._lock:
            if device_id not in self._devices:
                return False
            del self._devices[device_id]
            for tok, s in list(self._sessions.items()):
                if s.device_id == device_id:
                    del self._sessions[tok]
            return True

    def forget_all(self) -> int:
        with self._lock:
            n = len(self._devices)
            self._devices.clear()
            self._sessions.clear()
            return n

    def upsert_demo_device(
        self,
        *,
        device_id: str,
        label: str,
        color: str | None = None,
        reset_points: bool = True,
    ) -> Device:
        """Create or reset a named demo device (no pairing token)."""
        now = time.time()
        with self._lock:
            existing = self._devices.get(device_id)
            if existing is not None and not reset_points:
                return existing
            if existing is None:
                self._n_paired += 1
            swatch = color or PALETTE[(self._n_paired - 1) % len(PALETTE)]
            dev = Device(
                device_id=device_id,
                label=label,
                color=swatch,
                first_seen=now,
                last_seen=now,
            )
            self._devices[device_id] = dev
            return dev

    def push_point(
        self,
        device_id: str,
        *,
        lat: float,
        lon: float,
        mode: str,
        speed_mps: float,
        acc_m: float | None = None,
    ) -> bool:
        """Append one position to an existing device. Returns False if unknown."""
        now = time.time()
        with self._lock:
            dev = self._devices.get(device_id)
            if dev is None:
                return False
            dev.add(
                Point(
                    t=now,
                    lat=lat,
                    lon=lon,
                    mode=mode,
                    speed_mps=speed_mps,
                    acc_m=acc_m,
                )
            )
            return True


# -- QR ------------------------------------------------------------------


def qr_svg(data: str, *, scale: int = 6, dark: str = "#0A0B0D") -> str | None:
    """QR as inline SVG. Returns None if no encoder is available, so the caller
    can degrade to showing the URL as text rather than breaking the page."""
    try:
        import segno
    except ImportError:
        return None
    import io

    # segno's SVG writer emits bytes, not text.
    buf = io.BytesIO()
    segno.make(data, error="m").save(
        buf, kind="svg", scale=scale, dark=dark, light="#FFFFFF", border=2, xmldecl=False
    )
    return buf.getvalue().decode("utf-8")


def _strip_base(url: str) -> str:
    return (url or "").strip().rstrip("/")


def configured_relay_base() -> str | None:
    """Origin the phone should POST to when LAN is isolated.

    ``COAST_RELAY_BASE`` overrides. ``off`` / ``none`` / ``false`` disables
    the relay (QR host stays on LAN). When unset, :data:`DEFAULT_RELAY_BASE`
    is used so a venue phone can still reach a public mailbox.
    """
    if "COAST_RELAY_BASE" in os.environ:
        raw = os.environ["COAST_RELAY_BASE"].strip()
        if not raw or raw.lower() in {"0", "off", "none", "false", "disable", "disabled"}:
            return None
        return _strip_base(raw)
    return _strip_base(DEFAULT_RELAY_BASE)


def _relay_http_json(
    method: str,
    url: str,
    body: dict[str, Any] | None = None,
    *,
    timeout_s: float = 4.0,
) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read().decode("utf-8")
    if not raw:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("relay response was not a JSON object")
    return parsed


def register_relay_mailbox(token: str, relay_base: str | None = None) -> bool:
    """POST /pair/open so the public mailbox exists before the phone posts."""
    base = _strip_base(relay_base) if relay_base else configured_relay_base()
    if not base:
        return False
    try:
        result = _relay_http_json("POST", f"{base}/pair/open", {"token": token})
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        return False
    return bool(result.get("ok"))


def pull_relay_into_fleet(
    fleet: Fleet,
    token: str,
    *,
    relay_base: str | None = None,
) -> int:
    """GET /feed?s=TOKEN (consume) and merge points into Fleet. LAN ingest stays separate.

    Returns the number of points accepted. Never forwards device-identifier keys —
    only lat/lon/mode/speed/acc/queued/time are passed to :meth:`Fleet.ingest`.
    """
    base = _strip_base(relay_base) if relay_base else configured_relay_base()
    if not base:
        return 0
    fleet.keep_alive(token)
    q = urllib.parse.urlencode({"s": token})
    try:
        result = _relay_http_json("GET", f"{base}/feed?{q}")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        return 0
    if not result.get("ok"):
        return 0
    points = result.get("points") or []
    if not isinstance(points, list) or not points:
        return 0
    cleaned: list[dict[str, Any]] = []
    for row in points:
        if not isinstance(row, dict):
            continue
        one: dict[str, Any] = {
            "lat": row.get("lat"),
            "lon": row.get("lon"),
            "mode": row.get("mode", "GNSS"),
            "speed_mps": row.get("speed_mps", 0.0),
        }
        if row.get("acc_m") is not None:
            one["acc_m"] = row.get("acc_m")
        if row.get("queued"):
            one["queued"] = True
        t = row.get("t_client") if row.get("t_client") is not None else row.get("t")
        if t is not None:
            one["t"] = t
            one["t_client"] = t
        cleaned.append(one)
    if not cleaned:
        return 0
    out = fleet.ingest({"token": token, "points": cleaned})
    if not out.get("ok"):
        return 0
    return int(out.get("accepted") or len(cleaned))


def pair_payload(token: str, lan_base: str, relay_base: str | None) -> str:
    """What the QR encodes.

    A plain URL, deliberately: a generic camera app can open it and land on a
    'get the app' page, which a raw JSON blob cannot do. Both endpoints ride
    along so the phone can race them.

    When a relay is configured the **QR host is the relay**, with ``lan`` as a
    query fallback. Scanning then works off-LAN (guest Wi-Fi AP isolation).
    ``relay=`` is still in the query so the Android parser pins both bases.
    """
    from urllib.parse import urlencode

    lan = _strip_base(lan_base)
    q = {"s": token, "lan": lan}
    relay = _strip_base(relay_base) if relay_base else ""
    if relay:
        q["relay"] = relay
        return f"{relay}/pair?{urlencode(q)}"
    return f"{lan}/pair?{urlencode(q)}"
