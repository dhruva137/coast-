"""Build the Fleet UK replay from the same clip used by the APK.

The APK CSV and MBTiles are immutable demo assets. This builder reads them and
the measured map-filter trace that starts 20 seconds into that clip, then emits
one small browser payload:

    recorded GNSS 0-20 s -> filter estimate 20-80 s -> recorded GNSS 80-90 s

No coordinates are invented and no interpolation hides the reacquisition jump.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO / "web" / "static" / "uk_demo_manifest.json"
OUTPUT_PATH = REPO / "web" / "static" / "demo_uk_track.json"
EARTH_R_M = 6_371_008.8
STRIDE = 3


def _haversine(a: dict[str, Any], b: dict[str, Any]) -> float:
    lat1 = math.radians(float(a["lat"]))
    lat2 = math.radians(float(b["lat"]))
    dlat = lat2 - lat1
    dlon = math.radians(float(b["lon"]) - float(a["lon"]))
    q = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
    )
    return 2.0 * EARTH_R_M * math.asin(min(1.0, math.sqrt(q)))


def _read_csv(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with path.open(newline="", encoding="utf-8", errors="replace") as fh:
        for row in csv.DictReader(fh):
            rows.append(
                {
                    "t_rel_s": float(row["Time since start"]) / 1000.0,
                    "lat": float(row["GPS latitude"]),
                    "lon": float(row["GPS longitude"]),
                    "speed_mps": float(row["Indicated vehicle speed"]) / 3.6,
                }
            )
    if len(rows) < 10:
        raise ValueError(f"demo clip has too few rows: {path}")
    t0 = rows[0]["t_rel_s"]
    for row in rows:
        row["t_rel_s"] = round(row["t_rel_s"] - t0, 3)
    return rows


def build() -> dict[str, Any]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    clip = manifest["clip"]
    outage = manifest["outage"]
    start = float(outage["start_rel_s"])
    end = float(outage["end_rel_s"])

    csv_rows = _read_csv(REPO / clip["asset_csv"])
    trace_path = REPO / outage["trace"]
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    if trace.get("meta", {}).get("honesty") != "REAL":
        raise ValueError("UK Fleet demo requires a REAL filter trace")

    points: list[dict[str, Any]] = []
    for row in csv_rows[::STRIDE]:
        if row["t_rel_s"] >= start:
            break
        points.append(
            {
                **row,
                "mode": "GNSS",
                "source": "recorded_reference",
            }
        )

    for step in trace.get("steps", [])[::STRIDE]:
        estimate = step.get("estimate") or {}
        points.append(
            {
                "t_rel_s": round(start + float(step["t"]), 3),
                "lat": round(float(estimate["lat"]), 7),
                "lon": round(float(estimate["lon"]), 7),
                "mode": "IDR",
                "speed_mps": round(float(step.get("speed_mps") or 0.0), 3),
                "source": "map_filter_estimate",
            }
        )

    post = [row for row in csv_rows if row["t_rel_s"] >= end]
    for row in post[::STRIDE]:
        points.append(
            {
                **row,
                "mode": "GNSS",
                "source": "recorded_reference",
            }
        )

    if not points:
        raise ValueError("empty UK demo track")
    modes = [p["mode"] for p in points]
    transitions = sum(a != b for a, b in zip(modes, modes[1:]))
    if transitions != 2 or modes[0] != "GNSS" or modes[-1] != "GNSS":
        raise ValueError(f"expected GNSS-IDR-GNSS, got {transitions} transitions")

    first_idr = next(i for i, p in enumerate(points) if p["mode"] == "IDR")
    first_reacquire = next(
        i
        for i in range(first_idr + 1, len(points))
        if points[i]["mode"] == "GNSS"
    )
    payload = {
        "meta": {
            "contract_id": manifest["contract_id"],
            "source": outage["trace"],
            "clip_asset": clip["asset_csv"],
            "drive": manifest["drive"],
            "region": manifest["region"],
            "n": len(points),
            "outage_rel_s": [start, end],
            "algorithm": manifest["surfaces"]["fleet"]["algorithm"],
            "graph": manifest["provenance"]["graph"],
            "graph_built_from_drive_data": False,
            "handover_jump_m": round(
                _haversine(points[first_idr - 1], points[first_idr]), 2
            ),
            "reacquire_jump_m": round(
                _haversine(points[first_reacquire - 1], points[first_reacquire]),
                2,
            ),
            "honesty": manifest["provenance"]["honesty"],
        },
        "points": points,
    }
    return payload


def main() -> int:
    payload = build()
    OUTPUT_PATH.write_text(
        json.dumps(payload, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    meta = payload["meta"]
    print(
        f"wrote {OUTPUT_PATH} ({meta['n']} points, "
        f"handover {meta['handover_jump_m']} m, "
        f"reacquire {meta['reacquire_jump_m']} m)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
