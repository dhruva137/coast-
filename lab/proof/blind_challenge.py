#!/usr/bin/env python3
"""Tamper-evident, GNSS-held-out outage challenge on real IO-VNBD logs."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for path in (ROOT / "lab" / "stress", ROOT / "lab" / "eval", ROOT / "lab" / "baselines"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from hardened_outage import estimate_gyro_bias_z  # noqa: E402
from load_iovnbd import (  # noqa: E402
    find_smartphone_csvs,
    load_smartphone_csv,
    segment_iovnbd_sessions,
)
from metrics import lla_to_enu, path_length, position_errors  # noqa: E402
from outage_replay import (  # noqa: E402
    _bearing_to_yaw_rad,
    _interp_lla,
    dead_reckon_car_style,
    dead_reckon_idr_lean,
)

PROTOCOL = "SIH26168-blind-outage-v2-corrected-axis-segmented"
DEFAULT_SEED = 26168
RESULTS = HERE / "results"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def eligible_starts(data: dict[str, Any], duration_s: float, margin_s: float = 30.0) -> np.ndarray:
    """Return starts with calibration history and complete, finite held-out GNSS."""
    t = np.asarray(data["t_s"])
    if len(t) < 2 or not np.all(np.diff(t) > 0):
        # searchsorted and duration semantics require one monotonic recording.
        # Concatenated/reset-clock files need explicit session segmentation.
        return np.array([], dtype=int)
    lo = int(np.searchsorted(t - t[0], margin_s))
    hi = int(np.searchsorted(t, t[-1] - duration_s - 2.0))
    if hi <= lo:
        return np.array([], dtype=int)
    candidates = np.arange(lo, hi, max(1, int(round(data["hz_est"] * 2.0))))
    ends = np.searchsorted(t, t[candidates] + duration_s)
    good = ends < len(t)
    good &= np.isfinite(data["lat"][candidates]) & np.isfinite(data["lon"][candidates])
    good &= np.isfinite(data["lat"][np.minimum(ends, len(t) - 1)])
    good &= np.isfinite(data["lon"][np.minimum(ends, len(t) - 1)])
    lat = np.asarray(data["lat"])
    lon = np.asarray(data["lon"])
    bounded_ends = np.minimum(ends, len(t) - 1)
    speed = np.asarray(data["speed_mps"])
    good &= np.isfinite(speed[np.maximum(candidates - 1, 0)])
    good &= speed[np.maximum(candidates - 1, 0)] >= 1.0
    invalid_imu = np.zeros(len(t), dtype=np.int64)
    for key in ("gx", "gy", "gz"):
        invalid_imu += (~np.isfinite(np.asarray(data[key]))).astype(np.int64)
    invalid_prefix = np.cumsum(invalid_imu)
    good &= (
        invalid_prefix[bounded_ends]
        - invalid_prefix[np.maximum(candidates - 1, 0)]
    ) == 0
    invalid_gnss = (
        ~np.isfinite(lat)
        | ~np.isfinite(lon)
        | (np.abs(lat) > 90)
        | (np.abs(lon) > 180)
    ).astype(np.int64)
    invalid_gnss_prefix = np.cumsum(invalid_gnss)
    good &= (
        invalid_gnss_prefix[bounded_ends]
        - invalid_gnss_prefix[np.maximum(candidates - 1, 0)]
    ) == 0
    return candidates[good]


def assert_correct_axis_mapping(data: dict[str, Any]) -> None:
    """Fail closed if proof input bypasses the audited loader mapping."""
    mapping = data.get("axis_mapping", {})
    if mapping.get("vehicle_gz_yaw") != "-gyro_pitch_raw":
        raise RuntimeError("Proof requires audited vehicle yaw = -GYROSCOPE Pitch")
    expected = -np.asarray(data["gyro_pitch_raw"], dtype=np.float64)
    if not np.array_equal(np.asarray(data["gz"]), expected, equal_nan=True):
        raise RuntimeError("Loader gz does not match corrected -gyro_pitch_raw mapping")


def choose_challenge(seed: int, duration_s: float | None = None) -> tuple[Path, dict[str, Any], int, float]:
    """Select from every eligible real session using a customer-supplied seed."""
    rng = np.random.default_rng(seed)
    files = find_smartphone_csvs()
    if not files:
        raise RuntimeError("No real IO-VNBD S-*.csv files larger than 1 MB")
    duration = float(duration_s if duration_s is not None else rng.choice([20, 40, 60, 90]))
    sessions: list[tuple[Path, dict[str, Any]]] = []
    for path in files:
        loaded = load_smartphone_csv(path)
        assert_correct_axis_mapping(loaded)
        sessions.extend((path, segment) for segment in segment_iovnbd_sessions(loaded))
    for session_index in rng.permutation(len(sessions)):
        path, data = sessions[int(session_index)]
        starts = eligible_starts(data, duration)
        if starts.size:
            return path, data, int(rng.choice(starts)), duration
    raise RuntimeError(
        f"No eligible {duration:g}s outage in {len(sessions)} viable sessions "
        f"from {len(files)} real logs"
    )


def sanitize_estimator_input(data: dict[str, Any], i0: int, i1: int) -> dict[str, np.ndarray | float]:
    """Construct the one-way trust boundary; no outage GNSS crosses it."""
    t = np.asarray(data["t_s"])
    return {
        "pre_t": t[:i0].copy(),
        "pre_lat": np.asarray(data["lat"][:i0]).copy(),
        "pre_lon": np.asarray(data["lon"][:i0]).copy(),
        "pre_bearing": np.asarray(data["bearing_deg"][:i0]).copy(),
        "pre_speed": np.asarray(data["speed_mps"][:i0]).copy(),
        "pre_gz": np.asarray(data["gz"][:i0]).copy(),
        "out_t": t[i0:i1].copy(),
        "out_gx": np.asarray(data["gx"][i0 - 1 : i1]).copy(),
        "out_gy": np.asarray(data["gy"][i0 - 1 : i1]).copy(),
        "out_gz": np.asarray(data["gz"][i0 - 1 : i1]).copy(),
    }


def estimate_sanitized(sensor: dict[str, np.ndarray | float]) -> dict[str, Any]:
    """Estimate using an object structurally incapable of containing outage GNSS."""
    pre_t = np.asarray(sensor["pre_t"])
    i0 = len(pre_t)
    bg_z = estimate_gyro_bias_z(
        pre_t,
        np.asarray(sensor["pre_gz"]),
        np.asarray(sensor["pre_bearing"]),
        np.asarray(sensor["pre_speed"]),
        i0=i0,
    )
    # Use the last available pre-outage fix as the local-frame origin. This
    # avoids coupling the challenge to recording-session history hours earlier.
    origin_lat = float(np.asarray(sensor["pre_lat"])[-1])
    origin_lon = float(np.asarray(sensor["pre_lon"])[-1])
    x0, y0 = 0.0, 0.0
    yaw0 = _bearing_to_yaw_rad(np.asarray(sensor["pre_bearing"]), i0 - 1)
    pre_speed = np.asarray(sensor["pre_speed"])[max(0, i0 - 20) : i0]
    pre_speed = pre_speed[np.isfinite(pre_speed)]
    speed0 = max(0.0, float(np.median(pre_speed))) if pre_speed.size else 0.0

    # The only outage inputs crossing this boundary are clock and IMU.
    out_t = np.asarray(sensor["out_t"])
    t_dr = np.r_[pre_t[-1], out_t]
    speed = np.full(len(t_dr), speed0)
    gx = np.asarray(sensor["out_gx"])
    gy = np.asarray(sensor["out_gy"])
    gz = np.asarray(sensor["out_gz"]) - bg_z
    xc, yc, yaw_c = dead_reckon_car_style(t_dr, speed, gz, x0=x0, y0=y0, yaw0=yaw0)
    xl, yl, yaw_l, phi = dead_reckon_idr_lean(
        t_dr, speed, gx, gy, gz, x0=x0, y0=y0, yaw0=yaw0
    )
    elapsed = out_t - out_t[0]
    # Predeclared conservative covariance model, not fit to this reveal.
    sigma_m = 3.0 + 1.0 * elapsed
    covariance = np.zeros((len(elapsed), 3))
    covariance[:, 0] = sigma_m**2
    covariance[:, 1] = sigma_m**2
    covariance[:, 2] = (np.deg2rad(2.0 + 0.35 * elapsed)) ** 2
    return {
        "origin": [origin_lat, origin_lon],
        "speed_hold_mps": speed0,
        "gyro_bias_z_rad_s": bg_z,
        "elapsed_s": elapsed,
        "est": {
            "car_bias": np.column_stack([xc[1:], yc[1:]]),
            "idr_lean_bias": np.column_stack([xl[1:], yl[1:]]),
        },
        "yaw": {"car_bias": yaw_c[1:], "idr_lean_bias": yaw_l[1:]},
        "phi": phi[1:],
        "covariance_diag": covariance,
    }


def reveal_and_score(
    data: dict[str, Any], i0: int, i1: int, prediction: dict[str, Any]
) -> tuple[dict[str, Any], np.ndarray]:
    """Open the held-out GNSS only after prediction has been serialized."""
    t = np.asarray(data["t_s"])
    lat, lon = _interp_lla(t[i0:i1], data["lat"][i0:i1], data["lon"][i0:i1])
    gt = lla_to_enu(lat, lon, *prediction["origin"])
    dt = np.diff(t[i0:i1], prepend=t[i0])
    held_speed = np.asarray(data["speed_mps"][i0:i1])
    held_speed = np.where(np.isfinite(held_speed), np.maximum(held_speed, 0), 0)
    distance = float(np.sum(held_speed * np.clip(dt, 0, 0.5)))
    if distance < 1:
        distance = float(path_length(gt))
    scores: dict[str, Any] = {}
    radius95 = math.sqrt(5.991) * np.sqrt(prediction["covariance_diag"][:, 0])
    for name, xy in prediction["est"].items():
        errors = position_errors(xy, gt)
        scores[name] = {
            "final_error_m": float(errors[-1]),
            "ate_m": float(np.sqrt(np.mean(errors**2))),
            "max_error_m": float(np.max(errors)),
            "distance_m": distance,
            "drift_pct": float(100 * errors[-1] / max(distance, 1)),
            "inside_95_end": bool(errors[-1] <= radius95[-1]),
        }
    return scores, gt


def _serializable_prediction(prediction: dict[str, Any]) -> dict[str, Any]:
    return {
        **{k: v for k, v in prediction.items() if k not in ("est", "yaw", "phi", "covariance_diag", "elapsed_s")},
        "timeline": [
            {
                "t_s": float(prediction["elapsed_s"][i]),
                "car_xy_m": prediction["est"]["car_bias"][i].tolist(),
                "idr_xy_m": prediction["est"]["idr_lean_bias"][i].tolist(),
                "car_yaw_rad": float(prediction["yaw"]["car_bias"][i]),
                "idr_yaw_rad": float(prediction["yaw"]["idr_lean_bias"][i]),
                "lean_rad": float(prediction["phi"][i]),
                "covariance_diag": prediction["covariance_diag"][i].tolist(),
                "map_posterior": None,
            }
            for i in range(len(prediction["elapsed_s"]))
        ],
        "disclosure": "map posterior unavailable; this challenge uses no map",
    }


def run_challenge(seed: int, duration_s: float | None, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    path, data, i0, duration = choose_challenge(seed, duration_s)
    t = np.asarray(data["t_s"])
    i1 = int(np.searchsorted(t, t[i0] + duration))
    source_hash = sha256_file(path)
    selection = {
        "protocol": PROTOCOL,
        "seed": seed,
        "data_class": "real-car/IO-VNBD",
        "source_relpath": path.relative_to(ROOT).as_posix(),
        "source_sha256": source_hash,
        "source_session": data["name"],
        "source_session_index": data["session_index"],
        "source_session_sample_range": data["source_sample_range"],
        "start_index": i0,
        "end_index_exclusive": i1,
        "source_start_index": data["source_sample_range"][0] + i0,
        "source_end_index_exclusive": data["source_sample_range"][0] + i1,
        "start_time_s": float(t[i0] - t[0]),
        "requested_duration_s": duration,
        "estimator": "bias-calibrated constant-speed gyro/lean DR; no map",
        "covariance_model": "isotropic sigma_m=3+1*t; chi2(2) 95% radius",
        "axis_mapping": data["axis_mapping"],
        "segmentation": data["segmentation"],
    }
    commitment = {
        "phase": "COMMITTED_BEFORE_ESTIMATION",
        "created_utc": utc_now(),
        "selection": selection,
        "commitment_sha256": hashlib.sha256(canonical(selection)).hexdigest(),
    }
    commit_path = output_dir / "blind_commitment.json"
    commit_path.write_text(json.dumps(commitment, indent=2), encoding="utf-8")

    prediction = estimate_sanitized(sanitize_estimator_input(data, i0, i1))
    prediction_doc = {
        "phase": "PREDICTED_BEFORE_REVEAL",
        "created_utc": utc_now(),
        "commitment_sha256": commitment["commitment_sha256"],
        **_serializable_prediction(prediction),
    }
    prediction_path = output_dir / "blind_prediction.json"
    prediction_path.write_text(json.dumps(prediction_doc, indent=2), encoding="utf-8")
    prediction_hash = sha256_file(prediction_path)

    scores, gt = reveal_and_score(data, i0, i1, prediction)
    reveal = {
        "phase": "REVEALED_AND_SCORED",
        "created_utc": utc_now(),
        "commitment_sha256": commitment["commitment_sha256"],
        "prediction_sha256": prediction_hash,
        "held_out_ground_truth_enu_m": gt.tolist(),
        "scores": scores,
        "claims": {"pass_invented": False, "data_class": "real-car/IO-VNBD"},
    }
    (output_dir / "blind_reveal.json").write_text(json.dumps(reveal, indent=2), encoding="utf-8")
    return {"selection": selection, "scores": scores, "prediction_sha256": prediction_hash}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="customer/witness supplied seed")
    parser.add_argument("--duration", type=float, choices=[20, 40, 60, 90])
    parser.add_argument("--output-dir", type=Path, default=RESULTS / "blind")
    args = parser.parse_args()
    result = run_challenge(args.seed, args.duration, args.output_dir)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
