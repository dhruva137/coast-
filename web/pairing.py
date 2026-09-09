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

import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any

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

    def as_json(self) -> dict[str, Any]:
        return {
            "t": round(self.t, 3),
            "lat": self.lat,
            "lon": self.lon,
            "mode": self.mode,
            "speed_mps": round(self.speed_mps, 3),
            "acc_m": self.acc_m,
        }


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
        now = time.time()
        with self._lock:
            self._reap(now)
            s = Session(token=secrets.token_urlsafe(16), created=now)
            self._sessions[s.token] = s
            return s

    def _reap(self, now: float) -> None:
        for tok in [t for t, s in self._sessions.items() if s.expired(now)]:
            del self._sessions[tok]

    def _claim(self, token: str, now: float) -> Device | None:
        """Bind a device to a session on its first post. Returns None if the
        token is unknown or expired — an unknown token must never silently
        create a device, or the endpoint becomes an open write."""
        s = self._sessions.get(token)
        if s is None or s.expired(now):
            return None
        if s.device_id and s.device_id in self._devices:
            return self._devices[s.device_id]
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
        token = str(payload.get("token") or "").strip()
        if not token:
            return {"ok": False, "error": "missing token"}
        try:
            lat = float(payload["lat"])
            lon = float(payload["lon"])
        except (KeyError, TypeError, ValueError):
            return {"ok": False, "error": "lat/lon required and must be numeric"}
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            return {"ok": False, "error": "lat/lon out of range"}

        mode = str(payload.get("mode") or "GNSS").upper()
        if mode not in ("GNSS", "IDR", "HOLD"):
            mode = "GNSS"
        try:
            speed = float(payload.get("speed_mps") or 0.0)
        except (TypeError, ValueError):
            speed = 0.0
        acc = payload.get("acc_m")
        try:
            acc = float(acc) if acc is not None else None
        except (TypeError, ValueError):
            acc = None

        with self._lock:
            self._reap(now)
            dev = self._claim(token, now)
            if dev is None:
                return {"ok": False, "error": "unknown or expired pairing token"}
            dev.add(Point(t=now, lat=lat, lon=lon, mode=mode, speed_mps=speed, acc_m=acc))
            return {
                "ok": True,
                "device_id": dev.device_id,
                "label": dev.label,
                "color": dev.color,
                "n_points": len(dev.points),
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


def pair_payload(token: str, lan_base: str, relay_base: str | None) -> str:
    """What the QR encodes.

    A plain URL, deliberately: a generic camera app can open it and land on a
    'get the app' page, which a raw JSON blob cannot do. Both endpoints ride
    along so the phone can race them.
    """
    from urllib.parse import urlencode

    q = {"s": token, "lan": lan_base}
    if relay_base:
        q["relay"] = relay_base
    return f"{lan_base}/pair?{urlencode(q)}"
