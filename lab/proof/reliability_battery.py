#!/usr/bin/env python3
"""Deterministic Monte Carlo outage battery with CDF and calibration evidence."""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for path in (HERE, ROOT / "lab" / "stress"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from blind_challenge import (  # noqa: E402
    assert_correct_axis_mapping,
    eligible_starts,
    estimate_sanitized,
    reveal_and_score,
    sanitize_estimator_input,
    sha256_file,
)
from load_iovnbd import (  # noqa: E402
    find_smartphone_csvs,
    load_smartphone_csv,
    segment_iovnbd_sessions,
)

SEED = 26168
DURATIONS = (20.0, 40.0, 60.0, 90.0)
RESULTS = HERE / "results"


def quantiles(values: np.ndarray) -> dict[str, float]:
    return {
        "p50": float(np.quantile(values, 0.50)),
        "p90": float(np.quantile(values, 0.90)),
        "p95": float(np.quantile(values, 0.95)),
        "p99": float(np.quantile(values, 0.99)),
        "max": float(np.max(values)),
    }


def _bins(rows: list[dict[str, Any]], key: str, edges: list[float]) -> list[dict[str, Any]]:
    output = []
    for low, high in zip(edges[:-1], edges[1:]):
        subset = [row for row in rows if low <= float(row[key]) < high]
        if subset:
            errors = np.asarray([row["final_error_m"] for row in subset])
            output.append(
                {
                    "range": [low, high],
                    "n": len(subset),
                    "median_final_error_m": float(np.median(errors)),
                    "p95_final_error_m": float(np.quantile(errors, 0.95)),
                    "failure_rate_over_50m": float(np.mean(errors > 50)),
                }
            )
    return output


def _duration_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors = np.asarray([row["final_error_m"] for row in rows])
    normalized = np.asarray(
        [row["final_error_m"] / row["sigma_end_m"] for row in rows]
    )
    coverage = float(np.mean([row["inside_95_end"] for row in rows]))
    return {
        "n": len(rows),
        "final_error_m": quantiles(errors),
        "coverage_95_endpoint": coverage,
        "coverage_gap_percentage_points": 100.0 * (coverage - 0.95),
        "failure_rate_over_50m": float(np.mean(errors > 50.0)),
        "posthoc_sigma_scale_for_95pct": float(
            np.quantile(normalized, 0.95) / math.sqrt(5.991)
        ),
    }


def _stratified_candidates(
    sessions: list[tuple[Path, dict[str, Any]]],
    n_trials: int,
    rng: np.random.Generator,
) -> list[tuple[int, float, int]]:
    targets = {
        duration: n_trials // len(DURATIONS) + (i < n_trials % len(DURATIONS))
        for i, duration in enumerate(DURATIONS)
    }
    chosen: list[tuple[int, float, int]] = []
    for duration in DURATIONS:
        buckets: dict[int, list[int]] = {}
        for session_index, (_, data) in enumerate(sessions):
            starts = eligible_starts(data, duration)
            if starts.size:
                buckets[session_index] = [
                    int(value) for value in rng.permutation(starts)
                ]
        order = [int(value) for value in rng.permutation(list(buckets))]
        duration_rows: list[tuple[int, float, int]] = []
        while len(duration_rows) < targets[duration] and order:
            next_order = []
            for session_index in order:
                if buckets[session_index]:
                    duration_rows.append(
                        (session_index, duration, buckets[session_index].pop())
                    )
                    if len(duration_rows) >= targets[duration]:
                        break
                if buckets[session_index]:
                    next_order.append(session_index)
            order = next_order
        if len(duration_rows) < targets[duration]:
            raise RuntimeError(
                f"Only {len(duration_rows)} of {targets[duration]} eligible "
                f"{duration:g}s placements"
            )
        chosen.extend(duration_rows)
    return chosen


def run_battery(n_trials: int, seed: int, output_dir: Path, max_logs: int = 6) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    files = find_smartphone_csvs()
    if not files:
        raise RuntimeError("No real IO-VNBD S-*.csv files larger than 1 MB")

    loaded_files: list[tuple[Path, dict[str, Any]]] = []
    sessions: list[tuple[Path, dict[str, Any]]] = []
    for index in rng.permutation(len(files)):
        path = files[int(index)]
        try:
            data = load_smartphone_csv(path)
        except (ValueError, OSError):
            continue
        assert_correct_axis_mapping(data)
        file_sessions = [
            segment
            for segment in segment_iovnbd_sessions(data)
            if any(eligible_starts(segment, duration).size for duration in DURATIONS)
        ]
        if file_sessions:
            loaded_files.append((path, data))
            sessions.extend((path, segment) for segment in file_sessions)
        if len(loaded_files) >= max_logs:
            break
    if not sessions:
        raise RuntimeError("No eligible segmented real session")
    file_hashes = {path: sha256_file(path) for path, _ in loaded_files}
    candidates = _stratified_candidates(sessions, n_trials, rng)

    rows: list[dict[str, Any]] = []
    for trial, (session_index, duration, i0) in enumerate(candidates):
        path, data = sessions[session_index]
        t = np.asarray(data["t_s"])
        i1 = int(np.searchsorted(t, t[i0] + duration))
        prediction = estimate_sanitized(sanitize_estimator_input(data, i0, i1))
        scores, _ = reveal_and_score(data, i0, i1, prediction)
        sigma_end = math.sqrt(float(prediction["covariance_diag"][-1, 0]))
        radius95 = math.sqrt(5.991) * sigma_end
        turn_rate = float(np.rad2deg(np.mean(np.abs(np.asarray(data["gz"][i0:i1])))))
        speed = float(prediction["speed_hold_mps"])
        for method, score in scores.items():
            rows.append(
                {
                    "trial": trial,
                    "data_class": "real-car/IO-VNBD",
                    "source": path.relative_to(ROOT).as_posix(),
                    "source_sha256": file_hashes[path],
                    "source_session": data["name"],
                    "source_session_index": data["session_index"],
                    "source_session_sample_range": data["source_sample_range"],
                    "start_index": i0,
                    "source_start_index": data["source_sample_range"][0] + i0,
                    "duration_s": duration,
                    "speed_mps": speed,
                    "turn_severity_deg_s": turn_rate,
                    "method": method,
                    "sigma_end_m": sigma_end,
                    "radius95_m": radius95,
                    **score,
                }
            )

    methods: dict[str, Any] = {}
    for method in sorted({row["method"] for row in rows}):
        subset = [row for row in rows if row["method"] == method]
        errors = np.asarray([row["final_error_m"] for row in subset])
        normalized = np.asarray([row["final_error_m"] / row["sigma_end_m"] for row in subset])
        methods[method] = {
            "n": len(subset),
            "final_error_m": quantiles(errors),
            "drift_pct": quantiles(np.asarray([row["drift_pct"] for row in subset])),
            "coverage_95_endpoint": float(np.mean([row["inside_95_end"] for row in subset])),
            "target_coverage": 0.95,
            "coverage_gap_percentage_points": float(
                100 * (np.mean([row["inside_95_end"] for row in subset]) - 0.95)
            ),
            "normalized_error": quantiles(normalized),
            "failure_rate_over_50m": float(np.mean(errors > 50)),
            "by_duration_s": {
                str(int(duration)): _duration_summary(
                    [row for row in subset if row["duration_s"] == duration]
                )
                for duration in DURATIONS
            },
        }

    primary = [row for row in rows if row["method"] == "idr_lean_bias"]
    report = {
        "protocol": "SIH26168-monte-carlo-v2-corrected-axis-segmented",
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "seed": seed,
        "requested_trials": n_trials,
        "completed_trials": len(primary),
        "placement": (
            "deterministic PRNG without replacement over eligible 2-second grid; "
            "equal allocation across 20/40/60/90s and round-robin across sessions"
        ),
        "data_class": "real-car/IO-VNBD",
        "estimation_leakage_rule": "outage GNSS position, bearing, and speed excluded",
        "axis_mapping": {
            "vehicle_gz_yaw": "-IO-VNBD GYROSCOPE Pitch",
            "source": "lab/stress/load_iovnbd.py",
            "audit": "lab/stress/results/alignment/ALIGNMENT_REPORT.md",
        },
        "segmentation": sessions[0][1]["segmentation"],
        "independent_source_files": len(loaded_files),
        "viable_sessions": len(sessions),
        "covariance_model": "predeclared isotropic sigma_m=3+1*t; not fit on these reveals",
        "covariance_calibration_note": (
            "Observed coverage and posthoc scale are diagnostics only; the scale "
            "must not be reused as held-out performance without a new evaluation."
        ),
        "logs": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": file_hashes[path],
                "bytes": path.stat().st_size,
                "samples": data["n"],
            }
            for path, data in loaded_files
        ],
        "sessions": [
            {
                "name": data["name"],
                "source": path.relative_to(ROOT).as_posix(),
                "source_session_index": data["session_index"],
                "source_sample_range": data["source_sample_range"],
                "duration_s": data["session_duration_s"],
                "distance_m": data["session_distance_m"],
            }
            for path, data in sessions
        ],
        "methods": methods,
        "failure_map": {
            "speed_mps": _bins(primary, "speed_mps", [0, 2, 5, 10, 20, 1000]),
            "turn_severity_deg_s": _bins(
                primary, "turn_severity_deg_s", [0, 1, 3, 6, 12, 1000]
            ),
            "duration_s": _bins(primary, "duration_s", [0, 30, 50, 75, 100]),
        },
        "rows": rows,
        "honesty_note": "No threshold is declared a pass. Failures and calibration gaps are retained.",
    }
    json_path = output_dir / "reliability.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    plot_report(report, output_dir / "reliability.png")
    return report


def plot_report(report: dict[str, Any], output: Path) -> None:
    rows = report["rows"]
    methods = sorted(report["methods"])
    colors = {"car_bias": "#7c8da6", "idr_lean_bias": "#00d4ff"}
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    fig.patch.set_facecolor("#07111d")
    for ax in axes.ravel():
        ax.set_facecolor("#0d1b2a")
        ax.grid(alpha=0.18, color="white")
        ax.tick_params(colors="#dbeafe")
        for spine in ax.spines.values():
            spine.set_color("#314158")

    for method in methods:
        subset = [row for row in rows if row["method"] == method]
        errors = np.sort([row["final_error_m"] for row in subset])
        cdf = np.arange(1, len(errors) + 1) / len(errors)
        axes[0, 0].plot(errors, cdf, label=method, color=colors.get(method))
        axes[0, 1].plot(errors, 1 - cdf, label=method, color=colors.get(method))
    axes[0, 0].set(title="Endpoint error CDF", xlabel="error (m)", ylabel="fraction ≤ error")
    axes[0, 1].set(title="Survival curve", xlabel="error (m)", ylabel="fraction > error", yscale="log")

    primary = [row for row in rows if row["method"] == "idr_lean_bias"]
    durations = sorted({row["duration_s"] for row in primary})
    coverage = [
        np.mean([row["inside_95_end"] for row in primary if row["duration_s"] == duration])
        for duration in durations
    ]
    axes[1, 0].plot(durations, coverage, "o-", color="#00d4ff", label="observed")
    axes[1, 0].axhline(0.95, ls="--", color="#ffb703", label="nominal 95%")
    axes[1, 0].set(title="Endpoint covariance calibration", xlabel="outage (s)", ylabel="coverage", ylim=(0, 1.03))

    scatter = axes[1, 1].scatter(
        [row["turn_severity_deg_s"] for row in primary],
        [row["final_error_m"] for row in primary],
        c=[row["duration_s"] for row in primary],
        cmap="plasma",
        alpha=0.8,
    )
    axes[1, 1].set(title="Failure surface", xlabel="mean |gyro z| (deg/s)", ylabel="endpoint error (m)")
    fig.colorbar(scatter, ax=axes[1, 1], label="outage duration (s)")
    for ax in axes.ravel():
        ax.title.set_color("white")
        ax.xaxis.label.set_color("#dbeafe")
        ax.yaxis.label.set_color("#dbeafe")
        legend = ax.get_legend()
        if legend:
            legend.get_frame().set_alpha(0.2)
            for text in legend.get_texts():
                text.set_color("white")
    fig.suptitle("SIH26168 — real-car held-out GNSS reliability envelope", color="white", fontsize=16)
    fig.tight_layout()
    fig.savefig(output, dpi=170, facecolor=fig.get_facecolor())
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=120)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--max-logs", type=int, default=6)
    parser.add_argument("--output-dir", type=Path, default=RESULTS)
    args = parser.parse_args()
    report = run_battery(args.trials, args.seed, args.output_dir, args.max_logs)
    print(json.dumps({"trials": report["completed_trials"], "methods": report["methods"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
