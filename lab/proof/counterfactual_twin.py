#!/usr/bin/env python3
"""Paired counterfactual: identical route/noise, only injected lean changes."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for path in (ROOT / "lab" / "stress", ROOT / "lab" / "baselines"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from blind_challenge import assert_correct_axis_mapping, sha256_file  # noqa: E402
from car_style import integrate_heading_speed  # noqa: E402
from load_iovnbd import (  # noqa: E402
    find_smartphone_csvs,
    load_smartphone_csv,
    segment_iovnbd_sessions,
)
from outage_replay import lean_aware_yaw_rates  # noqa: E402

G = 9.80665
SEED = 26168


def run_twin(seed: int, duration_s: float, output: Path) -> dict:
    rng = np.random.default_rng(seed)
    files = find_smartphone_csvs()
    if not files:
        raise RuntimeError("No real IO-VNBD S-*.csv files larger than 1 MB")
    dt = 0.1
    n = int(round(duration_s / dt)) + 1
    donors = []
    for source_path in files:
        loaded = load_smartphone_csv(source_path)
        assert_correct_axis_mapping(loaded)
        donors.extend(
            (source_path, session)
            for session in segment_iovnbd_sessions(loaded)
            if session["n"] >= n + 100
        )
    if not donors:
        raise RuntimeError(f"No segmented source is long enough for {duration_s:g}s noise")
    source, data = donors[int(rng.integers(len(donors)))]
    offset = int(rng.integers(50, data["n"] - n - 50))

    # Preserve the measured high-frequency phone noise but remove this car's motion/bias.
    real_gy = np.asarray(data["gy"][offset : offset + n], dtype=float)
    real_gz = np.asarray(data["gz"][offset : offset + n], dtype=float)
    noise_gy = real_gy - np.convolve(real_gy, np.ones(31) / 31, mode="same")
    noise_gz = real_gz - np.convolve(real_gz, np.ones(31) / 31, mode="same")
    # Edge convolution transients are not sensor noise.
    noise_gy[:16] = noise_gy[16]
    noise_gy[-16:] = noise_gy[-17]
    noise_gz[:16] = noise_gz[16]
    noise_gz[-16:] = noise_gz[-17]

    t = np.arange(n) * dt
    speed = np.full(n, 11.0)
    true_yaw_rate = np.deg2rad(5.5 + 3.0 * np.sin(2 * np.pi * t / 24.0))
    phi_lean = np.arctan2(speed * true_yaw_rate, G)
    phi_upright = np.zeros(n)

    def body_rates(phi: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return (
            true_yaw_rate * np.sin(phi) + noise_gy,
            true_yaw_rate * np.cos(phi) + noise_gz,
        )

    dts = np.r_[0.0, np.diff(t)]
    check_gy = true_yaw_rate * np.sin(phi_lean)
    check_gz = true_yaw_rate * np.cos(phi_lean)
    recovered_rate, recovered_phi = lean_aware_yaw_rates(
        check_gy, check_gz, speed, np.zeros(n)
    )
    max_noiseless_rate_error = float(np.max(np.abs(recovered_rate - true_yaw_rate)))
    max_noiseless_lean_error = float(np.max(np.abs(recovered_phi - phi_lean)))
    if max_noiseless_rate_error > 1e-8 or max_noiseless_lean_error > 1e-8:
        raise RuntimeError("Counterfactual frame/injection consistency check failed")
    xg, yg, _ = integrate_heading_speed(
        dts, speed, true_yaw_rate, x0=0, y0=0, yaw0=0
    )
    gt = np.column_stack([xg, yg])

    twins = {}
    trajectories = {}
    for label, phi in (("upright", phi_upright), ("injected_lean", phi_lean)):
        gy, gz = body_rates(phi)
        corrected, inferred_phi = lean_aware_yaw_rates(gy, gz, speed, np.zeros(n))
        xc, yc, _ = integrate_heading_speed(dts, speed, gz, x0=0, y0=0, yaw0=0)
        xl, yl, _ = integrate_heading_speed(
            dts, speed, corrected, x0=0, y0=0, yaw0=0
        )
        car_xy = np.column_stack([xc, yc])
        lean_xy = np.column_stack([xl, yl])
        distance = float(speed[0] * duration_s)
        car_error = float(np.linalg.norm(car_xy[-1] - gt[-1]))
        lean_error = float(np.linalg.norm(lean_xy[-1] - gt[-1]))
        twins[label] = {
            "data_class": (
                "fixture/synthetic-route+real-car-noise/upright"
                if label == "upright"
                else "fixture/synthetic-route+real-car-noise/injected-lean"
            ),
            "actual_mean_abs_lean_deg": float(np.rad2deg(np.mean(np.abs(phi)))),
            "inferred_mean_abs_lean_deg": float(np.rad2deg(np.mean(np.abs(inferred_phi)))),
            "car_style": {
                "final_error_m": car_error,
                "drift_pct": 100 * car_error / distance,
            },
            "lean_aware": {
                "final_error_m": lean_error,
                "drift_pct": 100 * lean_error / distance,
            },
        }
        trajectories[label] = {
            "car_xy_m": car_xy.tolist(),
            "lean_aware_xy_m": lean_xy.tolist(),
        }

    report = {
        "protocol": "SIH26168-counterfactual-twin-v2-corrected-axis",
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "seed": seed,
        "duration_s": duration_s,
        "controlled_variable": "roll/lean only",
        "axis_mapping": data["axis_mapping"],
        "injection_equations": {
            "vehicle_yaw_rate": "gy*sin(phi) + gz*cos(phi)",
            "body_gy": "vehicle_yaw_rate*sin(phi) + fixed donor noise_gy",
            "body_gz": "vehicle_yaw_rate*cos(phi) + fixed donor noise_gz",
            "lean": "atan2(speed*vehicle_yaw_rate, g)",
        },
        "noiseless_consistency_check": {
            "status": "PASS",
            "max_yaw_rate_error_rad_s": max_noiseless_rate_error,
            "max_lean_error_rad": max_noiseless_lean_error,
        },
        "held_constant": [
            "synthetic ground-truth route",
            "speed",
            "sample clock",
            "additive real-phone gy/gz noise samples",
            "estimator configuration",
        ],
        "real_noise_source": {
            "data_class": "real-car/IO-VNBD noise donor",
            "path": source.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(source),
            "source_session": data["name"],
            "session_sample_range": data["source_sample_range"],
            "sample_range_within_session": [offset, offset + n],
            "sample_range_within_file": [
                data["source_sample_range"][0] + offset,
                data["source_sample_range"][0] + offset + n,
            ],
        },
        "ground_truth_data_class": "fixture/synthetic coordinated-turn route",
        "twins": twins,
        "ground_truth_xy_m": gt.tolist(),
        "trajectories": trajectories,
        "honesty_note": "This is not a real two-wheeler recording; lean is explicitly injected.",
    }
    injected = twins["injected_lean"]
    if injected["lean_aware"]["final_error_m"] <= injected["car_style"]["final_error_m"]:
        report["counterfactual_status"] = "LEAN_AWARE_BETTER_IN_INJECTED_FIXTURE"
        report["investigation"] = "No frame inconsistency detected; noiseless check passes."
    else:
        report["counterfactual_status"] = "LEAN_AWARE_WORSE_IN_INJECTED_FIXTURE"
        report["investigation"] = (
            "Injection and estimator frame equations are internally consistent "
            "(noiseless check passes). The degradation remains under fixed measured "
            "phone-channel noise; no metric or simulation equation was tuned."
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--duration", type=float, default=90.0)
    parser.add_argument("--output", type=Path, default=HERE / "results" / "counterfactual_twin.json")
    args = parser.parse_args()
    report = run_twin(args.seed, args.duration, args.output)
    print(json.dumps(report["twins"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
