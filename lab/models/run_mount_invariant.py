"""Mount-invariant AVNet ablation: gravity-axis canonicalization vs current bakeoff.

EqNIO-style preprocessing (see ``gravity_canonical``) aligns each window's mean
specific force to +z before the standardiser / FrequencyDecoupledNet. This script
runs the *same* leave-file-out protocol as ``run_speed_bakeoff.py`` twice —

  * ``raw``           — current bakeoff input (no canonicalization)
  * ``gravity_canon`` — gravity-axis canonicalized IMU

— and writes the honest delta to ``lab/models/results/mount_invariant/``.

A wash is a valid result: report it as such. Do not invent improvement.

Also scores a *mount-swap probe*: apply one fixed random SO(3) to the held-out
IMU (simulating a different phone orientation) and re-infer. Canonicalization
should be far more stable under that probe than raw.

Run (from repo root)::

    python lab/models/run_mount_invariant.py [--folds N] [--epochs N] [--cap N]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from gravity_canonical import (  # noqa: E402
    apply_fixed_rotation,
    canonicalize_imu,
    gravity_z_stats,
    random_so3,
)
from run_speed_bakeoff import (  # noqa: E402
    SEED,
    _hold_label,
    _mae,
    _rmse,
    clean_drives,
    outage_distance,
    predict,
    train_one,
)
from speed_data import DriveWindows, load_corpus  # noqa: E402

RESULTS = _HERE / "results" / "mount_invariant"
CONDITIONS = ("raw", "gravity_canon")


def _maybe_canon(imu: np.ndarray, condition: str) -> np.ndarray:
    if condition == "gravity_canon":
        return canonicalize_imu(imu)
    if condition == "raw":
        return np.ascontiguousarray(imu, dtype=np.float32)
    raise ValueError(condition)


def _clone_drive(d: DriveWindows, imu: np.ndarray) -> DriveWindows:
    return DriveWindows(
        name=d.name,
        imu=np.ascontiguousarray(imu, dtype=np.float32),
        speed=d.speed,
        t_end=d.t_end,
        label_source=d.label_source,
        n_rows=d.n_rows,
        hz_est=d.hz_est,
        speed_unit_decision=d.speed_unit_decision,
        speed_unit_ratio=d.speed_unit_ratio,
        csv_path=d.csv_path,
    )


def prepare_corpus(drives: list[DriveWindows], condition: str) -> list[DriveWindows]:
    return [_clone_drive(d, _maybe_canon(d.imu, condition)) for d in drives]


def run_condition(
    drives_raw: list[DriveWindows],
    condition: str,
    *,
    folds: list[DriveWindows],
    device: str,
    epochs: int,
    cap: int,
    mount_rot: np.ndarray,
) -> dict[str, Any]:
    drives = prepare_corpus(drives_raw, condition)
    by_name = {d.name: d for d in drives}
    rows: list[dict[str, Any]] = []
    t0 = time.time()
    for fi, held_raw in enumerate(folds):
        held = by_name[held_raw.name]
        train = [d for d in drives if d.name != held.name]
        model, std = train_one(train, device, epochs, cap, SEED + fi)
        mu, var = predict(model, std, held.imu, device)
        y = held.speed.astype(np.float64)
        hold = _hold_label(held).astype(np.float64)
        mean_pred = float(np.mean(np.concatenate([d.speed for d in train])))
        sd = np.sqrt(var)
        cov68 = float(np.mean(np.abs(y - mu) <= sd))
        cov95 = float(np.mean(np.abs(y - mu) <= 1.96 * sd))
        od = outage_distance(mu, y, held.t_end.astype(np.float64))

        # Mount-swap probe: rotate held IMU in the *raw* phone frame, then
        # re-apply the condition transform so gravity_canon can recover.
        rotated_raw = apply_fixed_rotation(held_raw.imu, mount_rot)
        probe_imu = _maybe_canon(rotated_raw, condition)
        mu_r, _ = predict(model, std, probe_imu, device)
        probe_rmse = _rmse(mu_r, y)
        probe_delta = probe_rmse - _rmse(mu, y)

        row = {
            "held": held.name,
            "n": len(held),
            "outage": od,
            "model_rmse": _rmse(mu, y),
            "model_mae": _mae(mu, y),
            "hold_rmse": _rmse(hold, y),
            "hold_mae": _mae(hold, y),
            "mean_rmse": _rmse(np.full_like(y, mean_pred), y),
            "beats_hold": bool(_rmse(mu, y) < _rmse(hold, y)),
            "cov68": cov68,
            "cov95": cov95,
            "mount_probe_rmse": probe_rmse,
            "mount_probe_delta_rmse": float(probe_delta),
        }
        rows.append(row)
        print(
            f"  [{condition}] [{fi + 1}/{len(folds)}] {held.name:<10} "
            f"RMSE {row['model_rmse']:.3f}  hold {row['hold_rmse']:.3f}  "
            f"probe_dRMSE {probe_delta:+.3f}  ({time.time() - t0:.0f}s)"
        )
    return _aggregate(rows, condition)


def _aggregate(rows: list[dict[str, Any]], condition: str) -> dict[str, Any]:
    model_rmse = np.array([r["model_rmse"] for r in rows])
    hold_rmse = np.array([r["hold_rmse"] for r in rows])
    agg: dict[str, Any] = {
        "condition": condition,
        "n_folds": len(rows),
        "model_median_rmse": float(np.median(model_rmse)),
        "hold_median_rmse": float(np.median(hold_rmse)),
        "mean_median_rmse": float(np.median([r["mean_rmse"] for r in rows])),
        "folds_model_beats_hold": int(sum(r["beats_hold"] for r in rows)),
        "median_improvement_pct": float(
            100.0 * (1.0 - np.median(model_rmse) / max(np.median(hold_rmse), 1e-9))
        ),
        "median_cov68": float(np.median([r["cov68"] for r in rows])),
        "median_cov95": float(np.median([r["cov95"] for r in rows])),
        "mount_probe_median_rmse": float(np.median([r["mount_probe_rmse"] for r in rows])),
        "mount_probe_median_delta_rmse": float(
            np.median([r["mount_probe_delta_rmse"] for r in rows])
        ),
    }
    ods = [r["outage"] for r in rows if r["outage"]]
    if ods:
        agg["outage_model_dist_err_m"] = float(np.median([o["model_dist_err_m"] for o in ods]))
        agg["outage_frozen_dist_err_m"] = float(np.median([o["frozen_dist_err_m"] for o in ods]))
        agg["outage_model_drift_pct"] = float(np.median([o["model_drift_pct"] for o in ods]))
        agg["outage_frozen_drift_pct"] = float(np.median([o["frozen_drift_pct"] for o in ods]))
        agg["outage_folds_model_wins"] = int(sum(o["model_beats_frozen"] for o in ods))
        agg["outage_folds"] = len(ods)
    return {"aggregate": agg, "folds": rows}


def _delta(a: dict[str, Any], b: dict[str, Any], key: str) -> float | None:
    if key not in a or key not in b:
        return None
    return float(b[key] - a[key])


def _write_summary(path: Path, report: dict[str, Any]) -> None:
    raw = report["conditions"]["raw"]["aggregate"]
    canon = report["conditions"]["gravity_canon"]["aggregate"]
    d_rmse = _delta(raw, canon, "model_median_rmse")
    d_out = _delta(raw, canon, "outage_model_dist_err_m")
    d_drift = _delta(raw, canon, "outage_model_drift_pct")
    d_probe = _delta(raw, canon, "mount_probe_median_delta_rmse")

    # Wash if |ΔRMSE| < 0.05 m/s and closed-loop |Δdist| < 5 m (noise floor).
    wash_pw = d_rmse is not None and abs(d_rmse) < 0.05
    wash_cl = d_out is not None and abs(d_out) < 5.0
    if wash_pw and wash_cl:
        verdict = (
            "**Wash.** Gravity-axis canonicalization does not move per-window or "
            "closed-loop medians beyond the noise floor on this corpus (same phone "
            "mount family across IO-VNBD drives). Reported honestly — no claim of "
            "improvement."
        )
    elif d_rmse is not None and d_rmse < -0.05:
        verdict = (
            f"**Per-window improved** by {abs(d_rmse):.3f} m/s median RMSE "
            f"(canonicalized better). Closed-loop Δ dist err = "
            f"{d_out:+.1f} m." if d_out is not None else
            f"**Per-window improved** by {abs(d_rmse):.3f} m/s median RMSE."
        )
    elif d_rmse is not None and d_rmse > 0.05:
        verdict = (
            f"**Per-window worse** by {d_rmse:.3f} m/s median RMSE under "
            f"canonicalization. Closed-loop Δ dist err = {d_out:+.1f} m."
            if d_out is not None else
            f"**Per-window worse** by {d_rmse:.3f} m/s median RMSE."
        )
    else:
        verdict = (
            "**Mixed / near-wash.** See tables. Do not claim a win without a clear "
            "signed delta."
        )

    gstats = report.get("gravity_diagnostics", {})
    lines = [
        "# Mount-invariant speed model — gravity-axis canonicalization (EqNIO-style)",
        "",
        f"Device: {report['device']} | epochs/fold: {report['epochs']} | "
        f"folds: {raw['n_folds']} | cap: {report['cap']}",
        "",
        "Protocol: identical to `lab/models/run_speed_bakeoff.py` (CAN labels, "
        "leave-file-out, hold baseline, 60 s outage distance). The only change is "
        "whether IMU windows are gravity-axis canonicalized before the "
        "standardiser (`lab/models/gravity_canonical.py`).",
        "",
        "Paper: EqNIO — Subequivariant Neural Inertial Odometry "
        "(ICLR 2025, [arXiv 2408.06321](https://arxiv.org/abs/2408.06321)).",
        "",
        "## Verdict",
        "",
        verdict,
        "",
        f"- Δ median per-window RMSE (canon − raw): "
        f"**{d_rmse:+.3f} m/s**" if d_rmse is not None else "- Δ RMSE: n/a",
        f"- Δ median 60 s dist err (canon − raw): "
        f"**{d_out:+.1f} m**" if d_out is not None else "- Δ outage dist: n/a",
        f"- Δ median outage drift % (canon − raw): "
        f"**{d_drift:+.2f} pp**" if d_drift is not None else "- Δ drift: n/a",
        "",
        "## Per-window (RMSE)",
        "",
        "| condition | median RMSE | beats hold | vs hold |",
        "|---|---:|---:|---:|",
        f"| **raw (current bakeoff path)** | **{raw['model_median_rmse']:.3f} m/s** | "
        f"{raw['folds_model_beats_hold']}/{raw['n_folds']} | "
        f"{raw['median_improvement_pct']:.1f}% |",
        f"| **gravity_canon** | **{canon['model_median_rmse']:.3f} m/s** | "
        f"{canon['folds_model_beats_hold']}/{canon['n_folds']} | "
        f"{canon['median_improvement_pct']:.1f}% |",
        f"| Hold last speed | {raw['hold_median_rmse']:.3f} m/s | — | — |",
        "",
    ]
    if raw.get("outage_folds"):
        lines += [
            "## Closed-loop / outage distance (60 s)",
            "",
            "| condition | median dist err | median drift % | folds model wins |",
            "|---|---:|---:|---:|",
            f"| **raw** | **{raw['outage_model_dist_err_m']:.1f} m** | "
            f"**{raw['outage_model_drift_pct']:.1f}** | "
            f"{raw['outage_folds_model_wins']}/{raw['outage_folds']} |",
            f"| **gravity_canon** | **{canon['outage_model_dist_err_m']:.1f} m** | "
            f"**{canon['outage_model_drift_pct']:.1f}** | "
            f"{canon['outage_folds_model_wins']}/{canon['outage_folds']} |",
            f"| Frozen onset speed | {raw['outage_frozen_dist_err_m']:.1f} m | "
            f"{raw['outage_frozen_drift_pct']:.1f} | — |",
            "",
        ]
    lines += [
        "## Mount-swap probe (fixed random SO(3) on held-out IMU)",
        "",
        "Same trained weights; test IMU rotated once per fold (shared rotation "
        "seed). `probe ΔRMSE` = probe RMSE − unrotated RMSE (lower/near-zero is "
        "more mount-stable).",
        "",
        "| condition | median probe RMSE | median probe ΔRMSE |",
        "|---|---:|---:|",
        f"| raw | {raw['mount_probe_median_rmse']:.3f} | "
        f"{raw['mount_probe_median_delta_rmse']:+.3f} |",
        f"| gravity_canon | {canon['mount_probe_median_rmse']:.3f} | "
        f"{canon['mount_probe_median_delta_rmse']:+.3f} |",
        "",
        (
            f"Δ (canon − raw) median probe ΔRMSE: **{d_probe:+.3f} m/s**."
            if d_probe is not None
            else ""
        ),
        "",
        "## Gravity diagnostics (sanity)",
        "",
        f"After canonicalize on pooled clean windows: median |g_xy| = "
        f"{gstats.get('canon_median_gxy', float('nan')):.3f} m/s², "
        f"median |g_z| = {gstats.get('canon_median_gz', float('nan')):.3f} m/s² "
        f"(raw |g_xy| was {gstats.get('raw_median_gxy', float('nan')):.3f}).",
        "",
        "## Limitations",
        "",
        "- IO-VNBD phone mounts are already near-upright across drives; tilt "
        "diversity is limited, so canonicalization may be a wash on *this* corpus "
        "even if it helps a pocket/handlebar mix.",
        "- Residual yaw about gravity is not removed (full EqNIO subequivariance "
        "not implemented — preprocess only).",
        "- Does not change the bakeoff headline that the speed model still loses "
        "to hold on per-window RMSE; map-in-loop remains the position win.",
        "- ONNX phone asset not swapped; this is a lab ablation only.",
        "",
        "## Per fold (model RMSE)",
        "",
        "| held-out | n | raw RMSE | canon RMSE | Δ (c−r) | raw outage m | "
        "canon outage m |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    raw_folds = {r["held"]: r for r in report["conditions"]["raw"]["folds"]}
    for r in report["conditions"]["gravity_canon"]["folds"]:
        a = raw_folds[r["held"]]
        od_a = a.get("outage") or {}
        od_b = r.get("outage") or {}
        om_a = f"{od_a['model_dist_err_m']:.0f}" if od_a else "—"
        om_b = f"{od_b['model_dist_err_m']:.0f}" if od_b else "—"
        lines.append(
            f"| `{r['held']}` | {r['n']} | {a['model_rmse']:.3f} | "
            f"{r['model_rmse']:.3f} | {r['model_rmse'] - a['model_rmse']:+.3f} | "
            f"{om_a} | {om_b} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", type=int, default=0, help="limit folds (0 = all clean)")
    ap.add_argument("--epochs", type=int, default=12, help="match committed bakeoff")
    ap.add_argument("--cap", type=int, default=150_000)
    args = ap.parse_args()

    torch.manual_seed(SEED)
    np.random.seed(SEED)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device: {device}")

    drives_raw = clean_drives(load_corpus(verbose=False))
    print(f"clean CAN drives: {len(drives_raw)}")
    folds = drives_raw if not args.folds else drives_raw[: args.folds]

    # Sanity: canonicalize collapses horizontal gravity.
    sample = np.concatenate([d.imu for d in drives_raw[:3]], axis=0)
    raw_g = gravity_z_stats(sample)
    canon_g = gravity_z_stats(canonicalize_imu(sample))
    print(
        f"gravity sanity: raw |g_xy|={raw_g['median_gxy']:.3f} -> "
        f"canon |g_xy|={canon_g['median_gxy']:.3f}  "
        f"|g_z|={canon_g['median_gz']:.3f}"
    )

    rng = np.random.default_rng(SEED)
    mount_rot = random_so3(rng)

    conditions: dict[str, Any] = {}
    for cond in CONDITIONS:
        print(f"\n=== condition: {cond} ===")
        conditions[cond] = run_condition(
            drives_raw,
            cond,
            folds=folds,
            device=device,
            epochs=args.epochs,
            cap=args.cap,
            mount_rot=mount_rot,
        )

    report = {
        "device": device,
        "epochs": args.epochs,
        "cap": args.cap,
        "seed": SEED,
        "protocol": "leave-file-out CAN speed bakeoff + gravity-axis canon ablation",
        "paper": "EqNIO arXiv 2408.06321",
        "gravity_diagnostics": {
            "raw_median_gxy": raw_g["median_gxy"],
            "raw_median_gz": raw_g["median_gz"],
            "canon_median_gxy": canon_g["median_gxy"],
            "canon_median_gz": canon_g["median_gz"],
        },
        "conditions": conditions,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_summary(RESULTS / "summary.md", report)

    raw = conditions["raw"]["aggregate"]
    canon = conditions["gravity_canon"]["aggregate"]
    print("\n=== DELTA (canon - raw) ===")
    print(
        f"per-window median RMSE: "
        f"{canon['model_median_rmse'] - raw['model_median_rmse']:+.3f} m/s"
    )
    if "outage_model_dist_err_m" in raw:
        print(
            f"outage median dist err: "
            f"{canon['outage_model_dist_err_m'] - raw['outage_model_dist_err_m']:+.1f} m"
        )
    print(f"wrote {RESULTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
