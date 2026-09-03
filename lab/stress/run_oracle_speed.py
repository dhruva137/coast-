#!/usr/bin/env python3
"""Diagnostic: oracle (held-out) speed + bias + map — isolates heading error.

If this PASSes ISRO while speed-hold FAILs, the product blocker is odometry,
not lean/heading. Labeled ORACLE — not a field claim.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

_STRESS = Path(__file__).resolve().parent
sys.path.insert(0, str(_STRESS))

from hardened_outage import estimate_gyro_bias_z, verdict  # noqa: E402
from load_iovnbd import find_smartphone_csvs, load_smartphone_csv  # noqa: E402
from map_aid import build_map_from_gnss, dead_reckon_map_aided  # noqa: E402
from metrics import lla_to_enu, path_length  # noqa: E402
from outage_replay import (  # noqa: E402
    _bearing_to_yaw_rad,
    _interp_lla,
    dead_reckon_car_style,
    score_outage,
)

RESULTS = _STRESS / "results"


def run_oracle(csv: Path, start_idx: int, deny_s: float = 60.0) -> dict:
    data = load_smartphone_csv(csv)
    t = data["t_s"]
    n = t.size
    i0 = max(30, min(start_idx, n - 20))
    t_end = t[i0] + deny_s
    i1 = i0
    while i1 < n and t[i1] < t_end:
        i1 += 1
    bg = estimate_gyro_bias_z(t, data["gz"], data["bearing_deg"], data["speed_mps"], i0=i0)
    origin_lat, origin_lon = float(data["lat"][0]), float(data["lon"][0])
    lat_i, lon_i = _interp_lla(t[:i1], data["lat"][:i1], data["lon"][:i1])
    lat_f, lon_f = _interp_lla(t, data["lat"], data["lon"])
    gt = lla_to_enu(lat_i, lon_i, origin_lat, origin_lon)
    gt_out = gt[i0:]
    yaw0 = _bearing_to_yaw_rad(data["bearing_deg"], i0 - 1)
    x0, y0 = float(gt[i0 - 1, 0]), float(gt[i0 - 1, 1])

    # ORACLE: use true GPS speed during outage (diagnostic only).
    spd = np.asarray(data["speed_mps"][i0:i1], dtype=np.float64)
    spd = np.where(np.isfinite(spd), np.maximum(spd, 0.0), 0.0)
    speed0 = float(spd[0]) if spd.size else 0.0
    t_dr = np.concatenate([[t[i0 - 1]], t[i0:i1]])
    spd_dr = np.concatenate([[speed0], spd])
    gz_dr = np.concatenate([[data["gz"][i0 - 1]], data["gz"][i0:i1]]) - bg

    xc, yc, _ = dead_reckon_car_style(t_dr, spd_dr, gz_dr, x0=x0, y0=y0, yaw0=yaw0)
    free = np.column_stack([xc[1:], yc[1:]])

    prior = build_map_from_gnss(
        lat_f, lon_f, origin_lat=origin_lat, origin_lon=origin_lon,
        densify_m=25.0, max_vertices=800,
    )
    seq = dead_reckon_map_aided(
        t_dr, spd_dr, gz_dr, prior, x0=x0, y0=y0, yaw0=yaw0,
        max_cross_track_m=150.0, heading_blend=0.55,
    )
    mapped = seq["xy"][1:]

    dt = np.clip(np.diff(t[i0:i1], prepend=t[i0]), 0, 0.5)
    dist = float(np.sum(spd * dt)) or float(path_length(gt_out))
    sc_free = score_outage(free, gt_out, distance_m=dist)
    sc_map = score_outage(mapped, gt_out, distance_m=dist)
    for sc in (sc_free, sc_map):
        sc["m_per_km"] = sc["final_error_m"] / max(sc["distance_m"], 1.0) * 1000.0

    return {
        "csv": csv.name,
        "deny_s": deny_s,
        "bias_dps": float(np.rad2deg(bg)),
        "speed0": speed0,
        "dist_m": dist,
        "oracle_free": sc_free,
        "oracle_map": sc_map,
        "verdict_free": verdict(sc_free, deny_s=deny_s),
        "verdict_map": verdict(sc_map, deny_s=deny_s),
    }


def main() -> int:
    csvs = sorted(find_smartphone_csvs(), key=lambda p: p.stat().st_size)
    rows = []
    for csv in csvs[:2]:
        data = load_smartphone_csv(csv)
        n = data["n"]
        for site, idx in {"mid": max(900, n // 2), "late": max(900, int(n * 0.65))}.items():
            r = run_oracle(csv, idx, 60.0)
            r["site"] = site
            rows.append(r)
            print(
                f"{csv.name} {site}: free={r['oracle_free']['final_error_m']:.1f}m "
                f"{r['verdict_free']} | map={r['oracle_map']['final_error_m']:.1f}m "
                f"{r['verdict_map']} drift_map={r['oracle_map']['drift_pct']:.1f}%",
                flush=True,
            )
    out = RESULTS / "oracle_speed_report.json"
    out.write_text(json.dumps(rows, indent=2, default=float), encoding="utf-8")
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
