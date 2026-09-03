#!/usr/bin/env python3
"""Local-corridor map DR: map built from ±3 min around the outage only.

This matches a navigation app that knows the current road segment, not the
entire multi-hour drive history (which self-intersects and fools nearest-snap).
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
from metrics import lla_to_enu  # noqa: E402
from outage_replay import _bearing_to_yaw_rad, _interp_lla, dead_reckon_car_style, score_outage  # noqa: E402
from run_along_track import along_track_dr  # noqa: E402

RESULTS = _STRESS / "results"


def run_local(csv: Path, start_idx: int, deny_s: float = 60.0, pad_s: float = 180.0) -> dict:
    data = load_smartphone_csv(csv)
    t = data["t_s"]
    n = t.size
    hz = max(1.0, float(data["hz_est"] or 10.0))
    i0 = max(30, min(start_idx, n - 20))
    i1 = i0
    while i1 < n and t[i1] < t[i0] + deny_s:
        i1 += 1
    pad = int(pad_s * hz)
    a0 = max(0, i0 - pad)
    a1 = min(n, i1 + pad)

    origin_lat, origin_lon = float(data["lat"][0]), float(data["lon"][0])
    lat_i, lon_i = _interp_lla(t[:i1], data["lat"][:i1], data["lon"][:i1])
    lat_w, lon_w = _interp_lla(t[a0:a1], data["lat"][a0:a1], data["lon"][a0:a1])
    gt = lla_to_enu(lat_i, lon_i, origin_lat, origin_lon)
    gt_out = gt[i0:]
    x0, y0 = float(gt[i0 - 1, 0]), float(gt[i0 - 1, 1])
    yaw0 = _bearing_to_yaw_rad(data["bearing_deg"], i0 - 1)
    bg = estimate_gyro_bias_z(t, data["gz"], data["bearing_deg"], data["speed_mps"], i0=i0)

    prior = build_map_from_gnss(
        lat_w, lon_w, origin_lat=origin_lat, origin_lon=origin_lon,
        densify_m=10.0, max_vertices=500,
    )

    spd = np.asarray(data["speed_mps"][i0:i1], dtype=np.float64)
    spd = np.where(np.isfinite(spd), np.maximum(spd, 0.0), 0.0)
    t_dr = np.concatenate([[t[i0 - 1]], t[i0:i1]])
    spd_dr = np.concatenate([[float(spd[0]) if spd.size else 0.0], spd])
    gz_dr = np.concatenate([[data["gz"][i0 - 1]], data["gz"][i0:i1]]) - bg

    along = along_track_dr(t_dr, spd_dr, prior, x0=x0, y0=y0)[1:]
    seq = dead_reckon_map_aided(
        t_dr, spd_dr, gz_dr, prior, x0=x0, y0=y0, yaw0=yaw0,
        max_cross_track_m=80.0, heading_blend=0.6,
    )["xy"][1:]
    free_x, free_y, _ = dead_reckon_car_style(t_dr, spd_dr, gz_dr, x0=x0, y0=y0, yaw0=yaw0)
    free = np.column_stack([free_x[1:], free_y[1:]])

    dt = np.clip(np.diff(t[i0:i1], prepend=t[i0]), 0, 0.5)
    dist = float(np.sum(spd * dt)) or 1.0
    out = {}
    for name, xy in {"free_oracle_spd": free, "map_blend": seq, "along_only": along}.items():
        sc = score_outage(xy, gt_out, distance_m=dist)
        sc["m_per_km"] = sc["final_error_m"] / max(sc["distance_m"], 1.0) * 1000.0
        out[name] = sc
        out[f"verdict_{name}"] = verdict(sc, deny_s=deny_s)
    out.update({
        "csv": csv.name,
        "site_idx": i0,
        "map_n": prior["n_vertices"],
        "map_len": prior["length_m"],
        "bias_dps": float(np.rad2deg(bg)),
    })
    return out


def main() -> int:
    rows = []
    for csv in sorted(find_smartphone_csvs(), key=lambda p: p.stat().st_size)[:3]:
        data = load_smartphone_csv(csv)
        n = data["n"]
        for site, idx in {"mid": max(900, n // 2), "late": max(900, int(n * 0.65))}.items():
            r = run_local(csv, idx, 60.0)
            r["site"] = site
            rows.append(r)
            print(
                f"{csv.name} {site}: "
                f"free={r['free_oracle_spd']['final_error_m']:.1f}m {r['verdict_free_oracle_spd']} | "
                f"blend={r['map_blend']['final_error_m']:.1f}m {r['verdict_map_blend']} | "
                f"along={r['along_only']['final_error_m']:.1f}m {r['verdict_along_only']}",
                flush=True,
            )
    path = RESULTS / "local_corridor_report.json"
    path.write_text(json.dumps(rows, indent=2, default=float), encoding="utf-8")
    # Count ISRO / competitive on along_only and map_blend
    for key in ("along_only", "map_blend"):
        n_pass = sum(1 for r in rows if r[f"verdict_{key}"].startswith("PASS"))
        n_isro = sum(1 for r in rows if r[f"verdict_{key}"] == "PASS_ISRO")
        print(f"{key}: PASS {n_pass}/{len(rows)} (ISRO {n_isro})")
    print("wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
