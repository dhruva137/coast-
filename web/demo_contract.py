"""UK demo contract shared by Fleet, Engine, and the APK clip.

The frozen APK asset ``android/app/src/main/assets/demo/iovnbd_demo.csv`` is
the geography. Do not overwrite it. Outage is 20–80 s with GNSS bookends so
the console can show GNSS → IDR → GNSS without inventing a second track.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO / "web" / "static" / "uk_demo_manifest.json"
DEFAULT_OUTAGE = (20.0, 80.0)
DEFAULT_CLIP = "android/app/src/main/assets/demo/iovnbd_demo.csv"


@lru_cache(maxsize=1)
def load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.is_file():
        return {
            "clip": DEFAULT_CLIP,
            "apk_asset": "demo/iovnbd_demo.csv",
            "outage_s": list(DEFAULT_OUTAGE),
            "region": "Coventry / Midlands UK",
            "honesty": "APK demo clip; GNSS bookends around a 20–80 s outage.",
        }
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("uk_demo_manifest.json must be an object")
    return raw


def demo_csv_path() -> Path:
    rel = str(load_manifest().get("clip") or DEFAULT_CLIP).replace("\\", "/")
    path = REPO / rel
    if not path.is_file():
        raise FileNotFoundError(f"demo clip missing: {path}")
    return path


def outage_bounds() -> tuple[float, float]:
    bounds = load_manifest().get("outage_s") or list(DEFAULT_OUTAGE)
    if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
        return DEFAULT_OUTAGE
    start, end = float(bounds[0]), float(bounds[1])
    if end <= start:
        return DEFAULT_OUTAGE
    return start, end


def mode_at(t_s: float) -> str:
    """GNSS outside the outage, IDR inside — bookends on both sides."""
    start, end = outage_bounds()
    return "IDR" if start <= float(t_s) < end else "GNSS"
