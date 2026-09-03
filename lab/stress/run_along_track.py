#!/usr/bin/env python3
"""Along-track map odometry: progress on known route using speed only.

Ignores phone gyro during outage. This is the fleet / OSM product mode when
the road graph is known: position = integrate speed along the polyline.
If this fails, the map prior or speed signal is wrong — not the lean solver.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

_STRESS = Path(__file__).resolve().parent
sys.path.insert(0, str(_STRESS))

from load_iovnbd import find_smartphone_csvs, load_smartphone_csv  # noqa: E402
from map_aid import build_map_from_gnss, project_point  # noqa: E402
from metrics import lla_to_enu  # noqa: E402
from outage_replay import _interp_lla, score_outage  # noqa: E402
from hardened_outage import verdict  # noqa: E402

RESULTS = _STRESS / "results"


def along_track_dr(
    t: np.ndarray,
    speed: np.ndarray,
    prior: dict,
    *,
    x0: float,
    y0: float,
) -> np.ndarray:
    """Start at nearest map point to (x0,y0); advance along polyline by speed*dt."""
    verts = prior["vertices"]
    cum = prior["cum_m"]
    seed = project_point(np.array([x0, y0]), prior, max_cross_track_m=200.0)
    # Arc length at seed
    j = int(seed["seg"])
    a, b = verts[j], verts[min(j + 1, len(verts) - 1)]
    along0 = float(cum[j] + np.linalg.norm(seed["xy"] - a))
    s = along0
    out = np.empty((t.size, 2), dtype=np.float64)
    out[0] = seed["xy"]
    total = float(cum[-1])
    for i in range(1, t.size):
        dt = float(t[i] - t[i - 1])
        if dt <= 0 or dt > 0.5:
            out[i] = out[i - 1]
            continue
        s = min(total, max(0.0, s + float(speed[i - 1]) * dt))
        # Place on polyline
        k = int(np.searchsorted(cum, s, side="right") - 1)
        k = max(0, min(k, len(verts) - 2))
        seg = cum[k + 1] - cum[k]
        u = 0.0 if seg < 1e-9 else (s - cum[k]) / seg
        u = max(0.0, min(1.0, u))
        out[i] = verts[k] + u * (verts[k + 1] - verts[k])
    return out


def run_one(csv: Path, start_idx: int, deny_s: float = 60.0) -> dict:
    data = load_smartphone_csv(csv)
    t = data["t_s"]
    n = t.size
    i0 = max(30, min(start_idx, n - 20))
    i1 = i0
    while i1 < n and t[i1] < t[i0] + deny_s:
        i1 += 1
    origin_lat, origin_lon = float(data["lat"][0]), float(data["lon"][0])
    lat_i, lon_i = _interp_lla(t[:i1], data["lat"][:i1], data["lon"][:i1])
    lat_f, lon_f = _interp_lla(t, data["lat"], data["lon"])
    gt = lla_to_enu(lat_i, lon_i, origin_lat, origin_lon)
    gt_out = gt[i0:]
    x0, y0 = float(gt[i0 - 1, 0]), float(gt[i0 - 1, 1])

    prior = build_map_from_gnss(
        lat_f, lon_f, origin_lat=origin_lat, origin_lon=origin_lon,
        densify_m=15.0, max_vertices=1500,
    )

    # Oracle speed
    spd = np.asarray(data["speed_mps"][i0:i1], dtype=np.float64)
    spd = np.where(np.isfinite(spd), np.maximum(spd, 0.0), 0.0)
    t_dr = np.concatenate([[t[i0 - 1]], t[i0:i1]])
    spd_dr = np.concatenate([[spd[0] if spd.size else 0.0], spd])
    xy = along_track_dr(t_dr, spd_dr, prior, x0=x0, y0=y0)[1:]

    # Hold-speed variant
    hold = np.full_like(spd_dr, float(np.median(spd[:20])) if spd.size else 0.0)
    hold[0] = hold[1] if hold.size > 1 else 0.0
    xy_hold = along_track_dr(t_dr, hold, prior, x0=x0, y0=y0)[1:]

    dt = np.clip(np.diff(t[i0:i1], prepend=t[i0]), 0, 0.5)
    dist = float(np.sum(spd * dt)) or 1.0
    sc_o = score_outage(xy, gt_out, distance_m=dist)
    sc_h = score_outage(xy_hold, gt_out, distance_m=dist)
    for sc in (sc_o, sc_h):
        sc["m_per_km"] = sc["final_error_m"] / max(sc["distance_m"], 1.0) * 1000.0
    return {
        "csv": csv.name,
        "oracle_along": sc_o,
        "hold_along": sc_h,
        "verdict_oracle": verdict(sc_o, deny_s=deny_s),
        "verdict_hold": verdict(sc_h, deny_s=deny_s),
        "map_len": prior["length_m"],
        "map_n": prior["n_vertices"],
    }


def main() -> int:
    rows = []
    for csv in sorted(find_smartphone_csvs(), key=lambda p: p.stat().st_size)[:3]:
        data = load_smartphone_csv(csv)
        n = data["n"]
        for site, idx in {"mid": max(900, n // 2), "late": max(900, int(n * 0.65))}.items():
            r = run_one(csv, idx, 60.0)
            r["site"] = site
            rows.append(r)
            print(
                f"{csv.name} {site}: along+oracle_speed "
                f"final={r['oracle_along']['final_error_m']:.1f}m "
                f"drift={r['oracle_along']['drift_pct']:.1f}% {r['verdict_oracle']} | "
                f"hold final={r['hold_along']['final_error_m']:.1f}m {r['verdict_hold']}",
                flush=True,
            )
    path = RESULTS / "along_track_report.json"
    path.write_text(json.dumps(rows, indent=2, default=float), encoding="utf-8")
    print("wrote", path)
    n_pass = sum(1 for r in rows if r["verdict_oracle"].startswith("PASS"))
    print(f"along+oracle PASS {n_pass}/{len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
