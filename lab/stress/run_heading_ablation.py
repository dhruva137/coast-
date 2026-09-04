"""Where does 60 s of dead-reckoning heading error actually come from?

This is the experiment that decides the architecture. It ablates the heading
path against paired IO-VNBD CAN ground truth, holding speed fixed at the
phone's own GNSS speed column so that only heading varies.

Configurations
--------------
A  raw ``-gyro_pitch``            the contract the repo shipped
B  A + 0.5 Hz causal low pass     vibration rejection alone
C  CAN-fitted 3-axis mount vector  perfect linear mount, unfiltered
D  C + 0.5 Hz causal low pass      perfect linear mount + vibration rejection
E  D + stationary bias removal     adds a pre-outage gyro bias estimate
F  CAN yaw rate directly           sensor-perfect ceiling

C, D, E and F all consume CAN data and are therefore ORACLES, not deployable
methods. They exist to bound what an online alignment engine could ever buy.
Only A and B are achievable from the phone alone.

What it showed (10 synchronised drives, median 60 s final error)
----------------------------------------------------------------
    A raw            362.6 m
    B +low pass      340.9 m
    C +mount         217.6 m
    D +mount+LP      167.1 m     <- best linear mount model
    E +bias          183.1 m     <- bias estimate is noisy; it hurts
    F oracle yaw      60.7 m     <- sensor-perfect

Three conclusions, all load-bearing:

1. Filtering alone is nearly worthless (A->B, 6%). Correlation against CAN
   improves a lot under low pass, but correlation is not the objective:
   integrated heading error is dominated by the slowly-varying component that
   a low pass passes straight through.
2. Mount and filter only pay off *together* (A->D, 2.2x). Neither is
   sufficient alone, which is why the single hardcoded axis fails outside the
   S-S1/S-S3c family.
3. Even a perfect linear mount leaves a 2.75x gap to the sensor ceiling
   (D vs F), and the ceiling itself is only ~6.7% drift over 60 s. **A phone
   gyro cannot carry 60 s of heading on its own.** The map is not an
   enhancement, it is a requirement.

Run:
    python lab/stress/run_heading_ablation.py [--segments N]

Writes lab/stress/results/heading_ablation/{report.json,summary.md}.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

_STRESS = Path(__file__).resolve().parent
if str(_STRESS) not in sys.path:
    sys.path.insert(0, str(_STRESS))

from gyro_preprocess import DEFAULT_CUTOFF_HZ, lowpass_causal  # noqa: E402
from load_iovnbd import (  # noqa: E402
    attach_vehicle_truth,
    find_smartphone_csvs,
    load_smartphone_csv,
)

EARTH_R_M = 6_371_008.8
DENY_S = 60.0
MIN_SPEED_MPS = 5.0
SEED_SAMPLES = 50  # 5 s of GNSS course before the outage
CONFIGS = ("A_raw", "B_lowpass", "C_mount", "D_mount_lp", "E_mount_lp_bias", "F_oracle")
ORACLE_CONFIGS = {"C_mount", "D_mount_lp", "E_mount_lp_bias", "F_oracle"}


def _enu(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    east = np.deg2rad(lon - lon[0]) * EARTH_R_M * np.cos(np.deg2rad(lat[0]))
    north = np.deg2rad(lat - lat[0]) * EARTH_R_M
    return np.column_stack([east, north])


def _dead_reckon(
    t: np.ndarray,
    pos: np.ndarray,
    speed: np.ndarray,
    truth_speed: np.ndarray,
    yaw_rate: np.ndarray,
    segments: int,
) -> list[dict[str, float]]:
    n = t.size
    rows: list[dict[str, float]] = []
    for i0 in np.linspace(int(0.08 * n), int(0.88 * n), segments).astype(int):
        i1 = i0 + int(DENY_S / 0.1)
        if i1 >= n or float(np.nanmean(truth_speed[i0:i1])) < MIN_SPEED_MPS:
            continue
        seed = pos[i0 - 1] - pos[max(0, i0 - SEED_SAMPLES)]
        if float(np.hypot(*seed)) < 10.0:
            continue
        dt = np.diff(t[i0 - 1 : i1])
        yaw = np.arctan2(seed[0], seed[1]) + np.cumsum(yaw_rate[i0 - 1 : i1 - 1] * dt)
        v = speed[i0:i1]
        x = pos[i0 - 1, 0] + np.cumsum(v * np.sin(yaw) * dt)
        y = pos[i0 - 1, 1] + np.cumsum(v * np.cos(yaw) * dt)
        err = float(np.hypot(x[-1] - pos[i1 - 1, 0], y[-1] - pos[i1 - 1, 1]))
        dist = float(np.nansum(truth_speed[i0:i1] * dt))
        rows.append(
            {
                "start_idx": int(i0),
                "final_error_m": err,
                "distance_m": dist,
                "drift_pct": 100.0 * err / max(dist, 1.0),
                "m_per_km": err / max(dist, 1.0) * 1000.0,
            }
        )
    return rows


def build_yaw_rates(data: dict[str, Any]) -> dict[str, np.ndarray] | None:
    """All six heading hypotheses for one drive, or None if unusable."""
    n = int(min(data["n"], data.get("can_n", 0)))
    if n < 5000:
        return None
    gyro = np.stack(
        [
            np.asarray(data["gyro_yaw_raw"][:n], dtype=np.float64),
            np.asarray(data["gyro_pitch_raw"][:n], dtype=np.float64),
            np.asarray(data["gyro_roll_raw"][:n], dtype=np.float64),
        ],
        axis=1,
    )
    can_yaw = np.asarray(data["can_yaw_rate_rad_s"][:n], dtype=np.float64)
    truth_speed = np.asarray(data["can_speed_mps"][:n], dtype=np.float64)
    # Navigation course rate is the negative of the ISO 8855 vehicle yaw rate:
    # compass bearing grows clockwise, ISO yaw grows counter-clockwise.
    course_rate = -can_yaw

    fit = np.isfinite(course_rate) & (truth_speed > 4.0) & np.isfinite(gyro).all(axis=1)
    if int(fit.sum()) < 2000:
        return None
    gyro_lp = np.stack(
        [lowpass_causal(gyro[:, i], cutoff_hz=DEFAULT_CUTOFF_HZ) for i in range(3)],
        axis=1,
    )
    w_raw, *_ = np.linalg.lstsq(gyro[fit], course_rate[fit], rcond=None)
    w_lp, *_ = np.linalg.lstsq(gyro_lp[fit], course_rate[fit], rcond=None)

    mount_lp = gyro_lp @ w_lp
    stationary = truth_speed < 0.5
    bias = float(np.mean(mount_lp[stationary])) if int(stationary.sum()) > 200 else 0.0

    return {
        "A_raw": -gyro[:, 1],
        "B_lowpass": -gyro_lp[:, 1],
        "C_mount": gyro @ w_raw,
        "D_mount_lp": mount_lp,
        "E_mount_lp_bias": mount_lp - bias,
        "F_oracle": course_rate,
        "_meta": {  # type: ignore[dict-item]
            "n": n,
            "mount_vector_raw": [float(x) for x in w_raw],
            "mount_vector_lp": [float(x) for x in w_lp],
            "mount_norm_lp": float(np.linalg.norm(w_lp)),
            "stationary_bias_rad_s": bias,
            "can_yaw_std_rad_s": float(np.std(can_yaw[fit])),
            "gyro_pitch_std_rad_s": float(np.std(gyro[fit, 1])),
            "mean_speed_mps": float(np.mean(truth_speed[fit])),
        },
    }


def run_file(data: dict[str, Any], segments: int) -> dict[str, Any] | None:
    hyp = build_yaw_rates(data)
    if hyp is None:
        return None
    meta = hyp.pop("_meta")
    n = int(meta["n"])
    t = np.asarray(data["t_s"][:n], dtype=np.float64)
    pos = _enu(
        np.asarray(data["can_lat"][:n], dtype=np.float64),
        np.asarray(data["can_lon"][:n], dtype=np.float64),
    )
    speed = np.asarray(data["speed_mps"][:n], dtype=np.float64)
    truth_speed = np.asarray(data["can_speed_mps"][:n], dtype=np.float64)
    out: dict[str, Any] = {"name": data["name"], "meta": meta, "configs": {}}
    for cfg in CONFIGS:
        rows = _dead_reckon(t, pos, speed, truth_speed, hyp[cfg], segments)
        if not rows:
            continue
        err = np.array([r["final_error_m"] for r in rows])
        drift = np.array([r["drift_pct"] for r in rows])
        mpk = np.array([r["m_per_km"] for r in rows])
        out["configs"][cfg] = {
            "n": len(rows),
            "median_error_m": float(np.median(err)),
            "median_drift_pct": float(np.median(drift)),
            "median_m_per_km": float(np.median(mpk)),
            "pass_isro": int(((drift < 10.0) & (mpk < 100.0)).sum()),
            "is_oracle": cfg in ORACLE_CONFIGS,
        }
    return out if out["configs"] else None


def write_summary(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Heading ablation - where 60 s of DR error comes from",
        "",
        f"Drives: **{len(report['files'])}** with paired CAN ground truth. "
        f"Segments per drive: {report['segments_per_file']}. "
        f"Speed is held at the phone's GNSS speed in every row, so only heading varies.",
        "",
        "`C`-`F` consume CAN data and are **oracles**, not deployable methods. "
        "They bound what an online alignment engine could ever buy. "
        "Only `A` and `B` are achievable from the phone alone.",
        "",
        "| Config | What it is | median err | median drift % | PASS_ISRO |",
        "|---|---|---:|---:|---:|",
    ]
    labels = {
        "A_raw": "raw `-gyro_pitch` (shipped contract)",
        "B_lowpass": "+ 0.5 Hz causal low pass",
        "C_mount": "+ CAN-fitted 3-axis mount *(oracle)*",
        "D_mount_lp": "+ mount and low pass *(oracle)*",
        "E_mount_lp_bias": "+ stationary bias removal *(oracle)*",
        "F_oracle": "CAN yaw rate directly *(ceiling)*",
    }
    agg = report["aggregate"]
    for cfg in CONFIGS:
        if cfg not in agg:
            continue
        v = agg[cfg]
        lines.append(
            f"| `{cfg}` | {labels[cfg]} | {v['median_error_m']:.1f} m | "
            f"{v['median_drift_pct']:.1f} | {v['pass_isro']}/{v['n_rows']} |"
        )
    lines += [
        "",
        "## Reading",
        "",
        "1. **Filtering alone is nearly worthless.** Low pass sharply improves "
        "correlation against CAN yaw rate, but correlation is not the objective: "
        "integrated heading error is dominated by the slowly-varying component "
        "that a low pass passes straight through.",
        "2. **Mount and filter pay off only together.** Neither is sufficient "
        "alone, which is why one hardcoded axis fails outside the quiet urban drives.",
        "3. **Even a perfect linear mount leaves a large gap to the sensor "
        "ceiling, and the ceiling itself barely clears the ISRO bar.** A phone "
        "gyro cannot carry 60 s of heading on its own. Map constraint is a "
        "requirement, not an enhancement.",
        "",
        "## Per-drive",
        "",
        "| Drive | mean v | gyro std | CAN yaw std | A raw | D mount+LP | F oracle |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for f in report["files"]:
        m = f["meta"]
        c = f["configs"]

        def cell(k: str) -> str:
            return f"{c[k]['median_error_m']:.0f} m" if k in c else "-"

        lines.append(
            f"| `{f['name']}` | {m['mean_speed_mps']:.1f} | "
            f"{m['gyro_pitch_std_rad_s']:.3f} | {m['can_yaw_std_rad_s']:.3f} | "
            f"{cell('A_raw')} | {cell('D_mount_lp')} | {cell('F_oracle')} |"
        )
    lines += [
        "",
        "Where `gyro std` runs several times `CAN yaw std`, the channel is "
        "vibration-dominated and the raw signal carries little heading "
        "information. Those are the fast drives.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--segments", type=int, default=10)
    ap.add_argument("--files", type=int, default=0)
    args = ap.parse_args()

    csvs = find_smartphone_csvs()
    if args.files:
        csvs = csvs[: args.files]
    files: list[dict[str, Any]] = []
    for p in csvs:
        try:
            data = attach_vehicle_truth(load_smartphone_csv(p))
        except (OSError, ValueError):
            continue
        if data.get("truth_source") != "can_10hz":
            continue
        result = run_file(data, args.segments)
        if result is None:
            continue
        files.append(result)
        c = result["configs"]
        print(
            f"  {result['name']:14s} "
            f"A={c.get('A_raw', {}).get('median_error_m', float('nan')):7.1f}m "
            f"D={c.get('D_mount_lp', {}).get('median_error_m', float('nan')):7.1f}m "
            f"F={c.get('F_oracle', {}).get('median_error_m', float('nan')):7.1f}m"
        )

    aggregate: dict[str, Any] = {}
    for cfg in CONFIGS:
        vals = [f["configs"][cfg] for f in files if cfg in f["configs"]]
        if not vals:
            continue
        aggregate[cfg] = {
            "n_drives": len(vals),
            "n_rows": sum(v["n"] for v in vals),
            "median_error_m": float(np.median([v["median_error_m"] for v in vals])),
            "median_drift_pct": float(np.median([v["median_drift_pct"] for v in vals])),
            "pass_isro": sum(v["pass_isro"] for v in vals),
            "is_oracle": cfg in ORACLE_CONFIGS,
        }
    report = {
        "segments_per_file": args.segments,
        "deny_s": DENY_S,
        "cutoff_hz": DEFAULT_CUTOFF_HZ,
        "aggregate": aggregate,
        "files": files,
    }
    out_dir = _STRESS / "results" / "heading_ablation"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_summary(out_dir / "summary.md", report)

    print(f"\n{'config':18s} {'drives':>6s} {'medErr':>9s} {'drift%':>7s} {'PASS':>10s}")
    for cfg in CONFIGS:
        if cfg not in aggregate:
            continue
        v = aggregate[cfg]
        tag = " (oracle)" if v["is_oracle"] else ""
        print(
            f"{cfg:18s} {v['n_drives']:6d} {v['median_error_m']:8.1f}m "
            f"{v['median_drift_pct']:6.1f} {v['pass_isro']:4d}/{v['n_rows']}{tag}"
        )
    print(f"\nwrote {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
