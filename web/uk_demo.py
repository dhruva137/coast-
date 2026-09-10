"""UK IO-VNBD demo track for the console fleet view.

Laptop demos often have no phone paired. This module loads a measured Midlands
(Coventry) track derived from ``lab/stress/results/traces/S-S1_*.json`` and
streams it into the fleet as a labelled demo device — GNSS first, then IDR —
so the live-tracks canvas matches the APK blackout story and training geography.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

try:  # pragma: no cover
    from web.pairing import Fleet
except ImportError:  # pragma: no cover
    from pairing import Fleet  # type: ignore

_REPO = Path(__file__).resolve().parents[1]
_STATIC_TRACK = _REPO / "web" / "static" / "demo_uk_track.json"
_TRACES = _REPO / "lab" / "stress" / "results" / "traces"

DEMO_DEVICE_ID = "demo-uk-s1"
DEMO_LABEL = "UK · S-S1 (IO-VNBD)"

_lock = threading.Lock()
_player: threading.Thread | None = None
_stop = threading.Event()
_status: dict[str, Any] = {
    "running": False,
    "device_id": DEMO_DEVICE_ID,
    "n_points": 0,
    "i": 0,
    "region": "Coventry / Midlands UK",
}


def load_track() -> dict[str, Any]:
    """Prefer the slim static JSON; rebuild from the newest real S-S1 trace if missing."""
    if _STATIC_TRACK.is_file():
        return json.loads(_STATIC_TRACK.read_text(encoding="utf-8"))
    return _build_from_trace()


def _build_from_trace() -> dict[str, Any]:
    if not _TRACES.is_dir():
        raise FileNotFoundError("no filter traces under lab/stress/results/traces/")
    cands = sorted(
        (
            p
            for p in _TRACES.iterdir()
            if p.is_file()
            and p.suffix.lower() == ".json"
            and p.name.upper().startswith("S-S1")
            and not p.name.upper().startswith("SYNTHETIC")
        ),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not cands:
        raise FileNotFoundError("no S-S1*.json filter trace found")
    raw = json.loads(cands[0].read_text(encoding="utf-8"))
    steps = raw.get("steps") or []
    if len(steps) < 8:
        raise ValueError(f"trace {cands[0].name} has too few steps")
    stride = max(1, len(steps) // 250)
    sampled = steps[::stride]
    points: list[dict[str, Any]] = []
    n = len(sampled)
    for i, s in enumerate(sampled):
        frac = i / max(1, n - 1)
        mode = "GNSS" if frac < 0.45 else "IDR"
        est = s.get("estimate") or {}
        truth = s.get("truth") or est
        src = truth if mode == "GNSS" else est
        points.append(
            {
                "lat": round(float(src["lat"]), 7),
                "lon": round(float(src["lon"]), 7),
                "mode": mode,
                "speed_mps": round(float(s.get("speed_mps") or 0.0), 3),
            }
        )
    payload = {
        "meta": {
            "source": str(cands[0].relative_to(_REPO)).replace("\\", "/"),
            "drive": "S-S1",
            "region": "Coventry / Midlands UK",
            "n": len(points),
            "honesty": (
                "measured filter estimate + truth; GNSS segment uses truth, "
                "IDR segment uses particle estimate"
            ),
        },
        "points": points,
    }
    _STATIC_TRACK.parent.mkdir(parents=True, exist_ok=True)
    _STATIC_TRACK.write_text(
        json.dumps(payload, separators=(",", ":")), encoding="utf-8"
    )
    return payload


def status() -> dict[str, Any]:
    with _lock:
        return dict(_status)


def stop_demo(fleet: Fleet) -> dict[str, Any]:
    global _player
    _stop.set()
    t = _player
    if t and t.is_alive():
        t.join(timeout=2.0)
    with _lock:
        _status["running"] = False
        _player = None
    fleet.forget(DEMO_DEVICE_ID)
    return {"ok": True, "stopped": True, **status()}


def start_demo(
    fleet: Fleet, *, interval_s: float = 0.04, reset: bool = True
) -> dict[str, Any]:
    """Stream the UK track into the fleet. Restarts if already playing."""
    global _player
    track = load_track()
    points = track.get("points") or []
    if not points:
        return {"ok": False, "error": "empty UK demo track"}

    if reset:
        _stop.set()
        t = _player
        if t and t.is_alive():
            t.join(timeout=2.0)
        fleet.forget(DEMO_DEVICE_ID)

    _stop.clear()
    fleet.upsert_demo_device(
        device_id=DEMO_DEVICE_ID,
        label=DEMO_LABEL,
        color="#00D4AA",
        reset_points=True,
    )

    def _run() -> None:
        with _lock:
            _status.update(
                {
                    "running": True,
                    "n_points": len(points),
                    "i": 0,
                    "region": (track.get("meta") or {}).get(
                        "region", "Coventry / Midlands UK"
                    ),
                    "source": (track.get("meta") or {}).get("source"),
                }
            )
        try:
            for i, row in enumerate(points):
                if _stop.is_set():
                    break
                ok = fleet.push_point(
                    DEMO_DEVICE_ID,
                    lat=float(row["lat"]),
                    lon=float(row["lon"]),
                    mode=str(row.get("mode") or "IDR"),
                    speed_mps=float(row.get("speed_mps") or 0.0),
                    acc_m=8.0 if row.get("mode") == "IDR" else 3.0,
                )
                if not ok:
                    break
                with _lock:
                    _status["i"] = i + 1
                time.sleep(interval_s)
        finally:
            with _lock:
                _status["running"] = False

    thr = threading.Thread(target=_run, name="uk-demo-player", daemon=True)
    with _lock:
        _player = thr
    thr.start()
    return {
        "ok": True,
        "device_id": DEMO_DEVICE_ID,
        "label": DEMO_LABEL,
        "n_points": len(points),
        "meta": track.get("meta"),
        **status(),
    }
