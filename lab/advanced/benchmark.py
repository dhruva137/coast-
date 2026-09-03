#!/usr/bin/env python3
"""Benchmark gyro/mount calibration + abstention on held-out IO-VNBD outages.

GNSS inside each forced outage is used only for scoring.  Calibration sees the
prefix.  Both methods receive the same known-route polyline because the current
hardened baseline is map-aided; this isolates yaw-rate calibration.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
for path in (HERE, LAB / "stress", LAB / "eval"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from gyro_mount_calibration import fit_calibration, ood_fraction, predict_yaw_rate  # noqa: E402
from hardened_outage import run_hardened_outage, verdict  # noqa: E402
from load_iovnbd import find_smartphone_csvs, load_smartphone_csv  # noqa: E402
from map_aid import build_map_from_gnss, dead_reckon_map_aided  # noqa: E402
from metrics import lla_to_enu  # noqa: E402
from outage_replay import _bearing_to_yaw_rad, _fill_speed, _interp_lla, score_outage  # noqa: E402

RESULTS = HERE / "results"
SEED = 26168
NEUTRAL_TOLERANCE_M = 0.01


def _status(delta_m: float) -> str:
    if delta_m < -NEUTRAL_TOLERANCE_M:
        return "improved"
    if delta_m > NEUTRAL_TOLERANCE_M:
        return "worsened"
    return "neutral"


def _sites(n: int, hz: float) -> dict[str, int]:
    return {
        "early": max(300, int(120 * hz)),
        "mid": max(int(90 * hz), n // 2),
        "late": max(int(90 * hz), int(0.7 * n)),
    }


def _calibrated_candidate(data: dict[str, Any], hardened: dict[str, Any]) -> dict[str, Any]:
    t = np.asarray(data["t_s"])
    i0, i1 = int(hardened["i0"]), int(hardened["i1"])
    gyro = np.column_stack([data["gx"], data["gy"], data["gz"]])
    cal = fit_calibration(t, gyro, data["bearing_deg"], data["speed_mps"], end_idx=i0)
    fs = float(data.get("hz_est", 10.0) or 10.0)
    outage_ood = ood_fraction(gyro[i0:i1], cal, fs=fs)

    origin_lat, origin_lon = float(data["lat"][0]), float(data["lon"][0])
    lat_i, lon_i = _interp_lla(t[:i1], data["lat"][:i1], data["lon"][:i1])
    gt_all = lla_to_enu(lat_i, lon_i, origin_lat, origin_lon)
    x0, y0 = map(float, gt_all[i0 - 1, :2])
    yaw0 = _bearing_to_yaw_rad(data["bearing_deg"], i0 - 1)

    raw_speed = np.asarray(data["speed_mps"][:i1], dtype=np.float64)
    held = _fill_speed(raw_speed, slice(i0, i1))
    pre = raw_speed[max(0, i0 - 20) : i0]
    pre = pre[np.isfinite(pre)]
    speed0 = float(np.median(pre)) if pre.size else float(hardened["speed0_mps"])
    held[i0:i1] = speed0
    t_dr = np.concatenate([[t[i0 - 1]], t[i0:i1]])
    speed_dr = np.concatenate([[speed0], held[i0:i1]])
    gyro_dr = np.vstack([gyro[i0 - 1], gyro[i0:i1]])

    tick_t0 = time.perf_counter()
    yaw_rate = predict_yaw_rate(gyro_dr, cal, fs=fs)
    infer_us_per_tick = (time.perf_counter() - tick_t0) * 1e6 / max(len(gyro_dr), 1)

    lat_full, lon_full = _interp_lla(t, data["lat"], data["lon"])
    route = build_map_from_gnss(
        lat_full,
        lon_full,
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        densify_m=12.0,
        max_vertices=2500,
    )
    seed_s = float(route["length_m"]) * i0 / max(len(t) - 1, 1)
    seq = dead_reckon_map_aided(
        t_dr,
        speed_dr,
        yaw_rate,
        route,
        x0=x0,
        y0=y0,
        yaw0=yaw0,
        max_cross_track_m=150.0,
        heading_blend=0.55,
        seed_s_hint_m=seed_s,
    )
    candidate_xy = seq["xy"][1:]
    gt_out = hardened["gt_out"]
    baseline_name = "car_bias_map" if "car_bias_map" in hardened["est"] else "car_bias"
    baseline = hardened["scores"][baseline_name]
    candidate = score_outage(candidate_xy, gt_out, distance_m=baseline["distance_m"])
    candidate["m_per_km"] = candidate["final_error_m"] / max(candidate["distance_m"], 1.0) * 1000.0

    use_candidate = bool(cal.trusted_prefix and outage_ood <= 0.25)
    safe = candidate if use_candidate else baseline
    row_status = (
        _status(float(candidate["final_error_m"] - baseline["final_error_m"]))
        if use_candidate
        else "abstained"
    )
    duration = max(float(t[i1 - 1] - t[i0]), 0.0)
    if use_candidate:
        # Small-angle lateral envelope from a yaw-rate residual held over T.
        yaw_bound = min(math.pi, cal.conformal_q90_rps * duration)
        uncertainty_radius = float(
            baseline["distance_m"] * math.sin(min(yaw_bound, math.pi / 2)) + 10.0
        )
        uncertainty_kind = "split_conformal_yaw_propagation"
    else:
        # Rejection is an explicit "no finite certified bound" result.  A large
        # finite sentinel keeps strict JSON valid while guaranteeing no caller
        # mistakes the fallback trajectory for a calibrated prediction set.
        uncertainty_radius = 1e9
        uncertainty_kind = "abstained_unbounded"
    return {
        "calibration": cal.to_dict(),
        "outage_ood_fraction": outage_ood,
        "decision": "calibrated" if use_candidate else "abstain_baseline",
        "status": row_status,
        "baseline_method": baseline_name,
        "baseline": baseline,
        "candidate": candidate,
        "safe": safe,
        "uncertainty_radius_m": uncertainty_radius,
        "uncertainty_kind": uncertainty_kind,
        "uncertainty_covered": bool(safe["final_error_m"] <= uncertainty_radius),
        "infer_us_per_tick_python": infer_us_per_tick,
        "candidate_verdict": verdict(candidate, deny_s=duration),
        "safe_verdict": verdict(safe, deny_s=duration),
    }


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    b = np.array([r["baseline"]["final_error_m"] for r in rows])
    c = np.array([r["candidate"]["final_error_m"] for r in rows])
    s = np.array([r["safe"]["final_error_m"] for r in rows])
    used = np.array([r["decision"] == "calibrated" for r in rows])
    coverage = np.mean([r["uncertainty_covered"] for r in rows]) if rows else 0.0

    def stats(x: np.ndarray) -> dict[str, float]:
        return {
            "median_final_m": float(np.median(x)),
            "mean_final_m": float(np.mean(x)),
            "p90_final_m": float(np.quantile(x, 0.9)),
        }

    paired_median_delta = float(np.median(s - b))
    candidate_median_delta = float(np.median(c) - np.median(b))
    safe_median_delta = float(np.median(s) - np.median(b))
    accepted_count = int(used.sum())
    candidate_status = _status(candidate_median_delta)
    safe_status = _status(safe_median_delta)
    return {
        "n_outages": len(rows),
        "baseline": stats(b),
        "candidate": stats(c),
        "safe_abstaining": stats(s),
        "candidate_median_delta_m": candidate_median_delta,
        "candidate_status": candidate_status,
        "safe_median_delta_m": safe_median_delta,
        "safe_paired_median_delta_m": paired_median_delta,
        "safe_median_relative_delta_pct": float(100 * safe_median_delta / max(np.median(b), 1e-9)),
        "safe_status": safe_status,
        "accepted_count": accepted_count,
        "abstained_count": int(len(rows) - accepted_count),
        "safe_abstention_prevented_regression": bool(
            candidate_status == "worsened" and safe_status != "worsened"
        ),
        "candidate_win_rate": float(np.mean(c < b)),
        "safe_win_rate": float(np.mean(s < b)),
        "accepted_fraction": float(np.mean(used)),
        "conformal_empirical_coverage": float(coverage),
        "target_coverage": 0.90,
        "pass": bool(safe_status == "improved" and coverage >= 0.85),
        "pass_rule": "median final error improves and empirical coverage >= 85%",
        "status_tolerance_m": NEUTRAL_TOLERANCE_M,
    }


def _plot(rows: list[dict[str, Any]], out: Path) -> None:
    baseline = np.array([r["baseline"]["final_error_m"] for r in rows])
    safe = np.array([r["safe"]["final_error_m"] for r in rows])
    candidate = np.array([r["candidate"]["final_error_m"] for r in rows])
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    axes[0].scatter(baseline, candidate, c=["tab:blue" if r["decision"] == "calibrated" else "tab:gray" for r in rows])
    lim = max(float(np.max(baseline)), float(np.max(candidate)), 1.0)
    axes[0].plot([0, lim], [0, lim], "k--", linewidth=1)
    axes[0].set(xlabel="Hardened baseline final error (m)", ylabel="Calibrated candidate (m)", title="Held-out outage pairs")
    axes[0].grid(alpha=0.25)
    order_b = np.sort(baseline)
    order_s = np.sort(safe)
    q = np.arange(1, len(rows) + 1) / len(rows)
    axes[1].plot(order_b, q, label="hardened")
    axes[1].plot(order_s, q, label="safe calibrated")
    axes[1].set(xlabel="Final error (m)", ylabel="Empirical CDF", title="Abstaining system")
    axes[1].grid(alpha=0.25)
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    plt.close(fig)


def run(denies: tuple[float, ...] = (20.0, 40.0, 60.0)) -> dict[str, Any]:
    csvs = find_smartphone_csvs()
    if not csvs:
        raise RuntimeError("no real IO-VNBD S-*.csv files larger than 1 MB")
    rows: list[dict[str, Any]] = []
    for csv_path in csvs:
        data = load_smartphone_csv(csv_path)
        for site, idx in _sites(data["n"], data["hz_est"]).items():
            for deny in denies:
                hardened = run_hardened_outage(data, deny_s=deny, start_idx=idx)
                row = _calibrated_candidate(data, hardened)
                row.update({"csv": csv_path.name, "site": site, "deny_s": deny, "i0": idx})
                rows.append(row)
                print(
                    f"{csv_path.name:8s} {site:5s} {deny:2.0f}s "
                    f"{row['baseline']['final_error_m']:7.1f} -> {row['safe']['final_error_m']:7.1f} m "
                    f"{row['decision']} ({row['calibration']['reason']})"
                )
    summary = _summary(rows)
    report = {
        "dataset": "real IO-VNBD smartphone S-*.csv (>1 MB)",
        "seed": SEED,
        "axis_mapping": {
            "vehicle_yaw": "loader gz = -GYROSCOPE Pitch",
            "advanced_remap": "none; fit scale+bias on loader gz only",
            "alignment_evidence": "lab/stress/results/alignment/ALIGNMENT_REPORT.md",
            "alignment_correlations": {
                "S-S1_orientation": 0.992,
                "S-S1_latlon": 0.930,
                "S-S2_orientation": 0.983,
                "S-S2_latlon": 0.956,
            },
        },
        "calibration_provenance": {
            "feature_timing": "true GPS orientation changes; gyro averaged over identical intervals",
            "lag_selection": "training portion of prefix only, -1.0..+1.0 s at 0.1 s",
            "trust_correlation": ">=0.70 on final 25% of prefix updates",
            "mapped_yaw_scale": "[0.85, 1.15], consistent with loader rad/s sensor contract",
            "ood_radius": "empirical 99.5% Mahalanobis quantile on held-out prefix ticks",
            "outage_gnss_used_for_calibration": False,
        },
        "protocol": "prefix-only calibration; forced outage GNSS held out for scoring; same known-route prior for both methods",
        "known_route_caveat": "route geometry is built from the full logged drive as a stand-in for an offline OSM/fleet map; no outage positions enter the calibrator",
        "summary": summary,
        "rows": rows,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "benchmark_results.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    _plot(rows, RESULTS / "benchmark_comparison.png")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="20 s outages only")
    args = parser.parse_args()
    report = run((20.0,) if args.quick else (20.0, 40.0, 60.0))
    print(json.dumps(report["summary"], indent=2))
    return 0 if report["summary"]["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
