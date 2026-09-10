"""UK demo contract: Fleet, Engine, and APK share one clip and outage window.

    python tests/test_uk_demo_contract.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from web.demo_contract import demo_csv_path, load_manifest, mode_at, outage_bounds
from web.engine_compute import OUTAGE_END_S, OUTAGE_START_S
from web.uk_demo import _build_from_apk_clip, load_track


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  ok   {name}")
        return
    print(f"  FAIL {name} {detail}")
    raise AssertionError(name)


def main() -> int:
    manifest = load_manifest()
    clip = demo_csv_path()
    start, end = outage_bounds()

    check("manifest names the frozen APK CSV",
          str(manifest.get("clip", "")).replace("\\", "/").endswith("iovnbd_demo.csv"))
    check("APK clip exists (do not overwrite it)", clip.is_file())
    check("outage is 20-80 s", start == 20.0 and end == 80.0, f"{start},{end}")
    check("GNSS before outage", mode_at(19.9) == "GNSS")
    check("IDR inside outage", mode_at(20.0) == "IDR" and mode_at(79.9) == "IDR")
    check("GNSS after outage", mode_at(80.0) == "GNSS")
    check("Engine outage matches manifest",
          OUTAGE_START_S == start and OUTAGE_END_S == end,
          f"{OUTAGE_START_S},{OUTAGE_END_S}")

    track = _build_from_apk_clip()
    points = track["points"]
    meta = track["meta"]
    check("rebuilt track has GNSS bookends",
          points[0]["mode"] == "GNSS" and points[-1]["mode"] == "GNSS")
    modes = {p["mode"] for p in points}
    check("track includes an IDR outage segment", "IDR" in modes and "GNSS" in modes, str(modes))
    check("first fix is the APK clip origin",
          52.4090 <= points[0]["lat"] <= 52.4100
          and -1.5980 <= points[0]["lon"] <= -1.5950,
          str(points[0]))
    check("meta.clip is the APK asset",
          meta.get("clip", "").replace("\\", "/").endswith("iovnbd_demo.csv"))

    # Mode changes GNSS → IDR → GNSS in time order.
    seq = []
    for p in points:
        if not seq or seq[-1] != p["mode"]:
            seq.append(p["mode"])
    check("mode sequence is GNSS-IDR-GNSS",
          seq == ["GNSS", "IDR", "GNSS"], str(seq))

    loaded = load_track()
    check("load_track prefers the APK-clip static JSON",
          loaded["meta"].get("clip", "").replace("\\", "/").endswith("iovnbd_demo.csv"))

    static = Path(__file__).resolve().parents[1] / "web" / "static" / "demo_uk_track.json"
    check("static fleet JSON was written", static.is_file())
    disk = json.loads(static.read_text(encoding="utf-8"))
    check("static JSON is not the old S-S1-only geography",
          "iovnbd_demo.csv" in (disk.get("meta") or {}).get("clip", "")
          or "iovnbd_demo.csv" in (disk.get("meta") or {}).get("source", ""))

    print("uk demo contract OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
