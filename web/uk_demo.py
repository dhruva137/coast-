"""UK IO-VNBD demo track for the console fleet view.

Laptop demos often have no phone paired. This module streams the **same clip
the APK replays** (`iovnbd_demo.csv`) into the fleet as a labelled demo
device — GNSS, then IDR for the scripted outage, then GNSS again.

That is the APK-clip geography with honest mode labels. It is not a live
phone particle filter.
"""

from __future__ import annotations

import csv
import json
import threading
import time
from pathlib import Path
from typing import Any

try:  # pragma: no cover
    from web.demo_contract import demo_csv_path, load_manifest, mode_at, outage_bounds
    from web.pairing import Fleet
except ImportError:  # pragma: no cover
    from demo_contract import demo_csv_path, load_manifest, mode_at, outage_bounds  # type: ignore
    from pairing import Fleet  # type: ignore

_REPO = Path(__file__).resolve().parents[1]
_STATIC_TRACK = _REPO / "web" / "static" / "demo_uk_track.json"

DEMO_DEVICE_ID = "demo-uk-s1"
DEMO_LABEL = "UK · IO-VNBD clip"

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

_EXPECTED_CLIP = "android/app/src/main/assets/demo/iovnbd_demo.csv"


def load_track() -> dict[str, Any]:
    """Prefer the slim static JSON when it matches the APK clip; else rebuild."""
    if _STATIC_TRACK.is_file():
        data = json.loads(_STATIC_TRACK.read_text(encoding="utf-8"))
        meta = data.get("meta") or {}
        clip = str(meta.get("clip") or "").replace("\\", "/")
        if clip == _EXPECTED_CLIP and data.get("points"):
            return data
    return _build_from_apk_clip()


def _f(v: str, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _build_from_apk_clip() -> dict[str, Any]:
    csv_path = demo_csv_path()
    manifest = load_manifest()
    outage = list(outage_bounds())
    rows: list[tuple[float, float, float, float]] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            raise ValueError(f"{csv_path.name} has no header")
        for raw in reader:
            if len(raw) < 8:
                continue
            lat, lon = _f(raw[0]), _f(raw[1])
            if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                continue
            t_s = _f(raw[7]) / 1000.0
            speed = _f(raw[3])
            rows.append((t_s, lat, lon, speed))
    if len(rows) < 8:
        raise ValueError(f"{csv_path.name} has too few GPS rows")

    # ~2 Hz is enough for the fleet canvas; keep first/last and outage edges.
    stride = max(1, len(rows) // 250)
    sampled = rows[::stride]
    if sampled[-1] != rows[-1]:
        sampled.append(rows[-1])

    points: list[dict[str, Any]] = []
    for t_s, lat, lon, speed in sampled:
        points.append(
            {
                "lat": round(lat, 7),
                "lon": round(lon, 7),
                "mode": mode_at(t_s),
                "speed_mps": round(max(0.0, speed), 3),
                "t": round(t_s, 2),
            }
        )
    payload = {
        "meta": {
            "source": str(csv_path.relative_to(_REPO)).replace("\\", "/"),
            "clip": _EXPECTED_CLIP,
            "drive": manifest.get("drive") or "IO-VNBD demo clip",
            "region": manifest.get("region") or "Coventry / Midlands UK",
            "n": len(points),
            "outage_s": outage,
            "honesty": manifest.get("honesty")
            or (
                "APK demo-clip geography; GNSS→IDR→GNSS labels follow the "
                "scripted 20–80 s outage. Not a live phone particle filter."
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


if __name__ == "__main__":
    built = _build_from_apk_clip()
    print(f"wrote {_STATIC_TRACK} n={built['meta']['n']} outage={built['meta']['outage_s']}")
