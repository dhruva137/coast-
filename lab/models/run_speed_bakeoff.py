"""Leave-file-out speed bake-off: does the learned speed model beat holding speed?

This is the graded screening deliverable: the problem statement's "AI Speed &
Vibration Filter", trained on IO-VNBD and honestly evaluated.

The claim under test, and the one that matters, is NOT "the model has low RMSE".
It is "the model beats the trivial baseline of holding the last known speed",
because that baseline is exactly what free dead reckoning does during an outage.
An earlier reported model never beat it; if this one does not either, that is
the headline finding and it is reported as such rather than hidden.

Protocol
--------
* Labels are CAN indicated vehicle speed at 10 Hz (`speed_data`, `can_only`).
* Leave-file-out: train on N-1 drives, evaluate on the held-out drive, rotate.
  A drive the model trained on is never scored -- that would measure memorised
  road, not learned kinematics.
* Baselines, both scored on the same held-out windows:
    - `hold`  : predict the speed 2.0 s earlier (the window's first sample).
                This is the "speed-hold" free-DR does, and the one to beat.
    - `mean`  : predict the training-set mean speed. A floor.
* Uncertainty: the model has a Gaussian NLL head, so we also report empirical
  coverage of its nominal 68% and 95% intervals. A calibrated interval is what
  the GNSS+INS fusion needs to know how far to trust the speed.

Drives are filtered to those whose CAN speed unit resolved cleanly (ratio in
[0.8, 1.25]) and that actually moved (mean > 2 m/s); S-Vw1 (all-stopped) and
S-Vtb3 (ratio 0.32, unreliable label) are dropped for cause.

Run:
    python lab/models/run_speed_bakeoff.py [--folds N] [--epochs N] [--cap N]

Writes lab/models/results/speed_bakeoff/{report.json,summary.md}. Production
training/export is a separate gated step in ``export_avnet_production.py``.
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
import torch.nn.functional as F

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from backbone import build_model  # noqa: E402
from pipeline_integrity import ANDROID_ASSET, MODEL, asset_integrity  # noqa: E402
from speed_data import DriveWindows, clean_drives, load_corpus  # noqa: E402

SEED = 26168
RESULTS = _HERE / "results" / "speed_bakeoff"


class Standardiser:
    """Per-channel mean/std from the training split only. No test leakage."""

    def __init__(self, imu: np.ndarray) -> None:
        flat = imu.reshape(-1, imu.shape[-1])
        self.mean = flat.mean(axis=0).astype(np.float32)
        self.std = (flat.std(axis=0) + 1e-6).astype(np.float32)

    def __call__(self, imu: np.ndarray) -> np.ndarray:
        return ((imu - self.mean) / self.std).astype(np.float32)


def _hold_label(d: DriveWindows) -> np.ndarray:
    """Speed 2.0 s before each window's label, i.e. persistence over the window.

    The window is 20 samples at 10 Hz. The label is the speed at the last
    sample; the hold baseline predicts the speed at the FIRST sample, which is
    what you would carry forward if you froze speed at outage onset.

    ``speed_data`` does not keep the per-sample speed track, only the last-sample
    label, so persistence is reconstructed from the label series ordered by
    ``t_end``: the window 2.0 s earlier has t_end 2.0 s smaller.
    """
    order = np.argsort(d.t_end)
    t = d.t_end[order]
    s = d.speed[order]
    # For each window, find the label ~2.0 s earlier.
    prev_t = t - 2.0
    idx = np.searchsorted(t, prev_t, side="right") - 1
    idx = np.clip(idx, 0, len(t) - 1)
    hold = s[idx]
    # Undo the sort so it aligns with d.speed.
    out = np.empty_like(hold)
    out[order] = hold
    return out.astype(np.float32)


def train_one(
    train: list[DriveWindows],
    device: str,
    epochs: int,
    cap: int,
    seed: int,
) -> tuple[torch.nn.Module, Standardiser]:
    rng = np.random.default_rng(seed)
    imu = np.concatenate([d.imu for d in train], axis=0)
    speed = np.concatenate([d.speed for d in train], axis=0)
    if cap and imu.shape[0] > cap:
        sel = rng.choice(imu.shape[0], size=cap, replace=False)
        imu, speed = imu[sel], speed[sel]

    std = Standardiser(imu)
    x = torch.from_numpy(std(imu)).to(device)
    y = torch.from_numpy(speed).to(device)

    model = build_model().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=2e-3, weight_decay=1e-5)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
    n = x.shape[0]
    bs = 1024
    # Warm up the MEAN with plain MSE before turning on the NLL variance term.
    # NLL from a cold start collapses to "predict huge variance" -- the exp(-logvar)
    # weight lets the net minimise loss by hedging instead of fitting, which showed
    # up as coverage pinned at 1.00. Fitting the mean first, then calibrating the
    # variance, avoids that. The logvar clamp is tight enough (sd <= ~2.7 m/s) that
    # the head cannot hedge to infinity.
    warmup = max(1, int(0.6 * epochs))
    model.train()
    for ep in range(epochs):
        use_nll = ep >= warmup
        perm = torch.randperm(n, device=device)
        for i in range(0, n, bs):
            b = perm[i : i + bs]
            out = model(x[b])
            heads = model.split_heads(out)
            mu = heads["speed"]
            if use_nll:
                logvar = heads["logvar_speed"].clamp(-4.0, 2.0)
                nll = 0.5 * (F.mse_loss(mu, y[b], reduction="none") * torch.exp(-logvar) + logvar)
                loss = nll.mean()
            else:
                loss = F.mse_loss(mu, y[b])
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step()
        sched.step()
    return model, std


@torch.no_grad()
def predict(
    model: torch.nn.Module,
    std: Standardiser,
    imu: np.ndarray,
    device: str,
) -> tuple[np.ndarray, np.ndarray]:
    model.eval()
    x = torch.from_numpy(std(imu)).to(device)
    out = model(x)
    heads = model.split_heads(out)
    mu = heads["speed"].cpu().numpy()
    var = np.exp(heads["logvar_speed"].clamp(-4.0, 2.0).cpu().numpy())
    return mu.astype(np.float64), var.astype(np.float64)


def _rmse(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.sqrt(np.mean((a - b) ** 2)))


def _mae(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.mean(np.abs(a - b)))


def outage_distance(
    mu: np.ndarray, y: np.ndarray, t_end: np.ndarray, deny_s: float = 60.0
) -> dict[str, float] | None:
    """Distance error over a 60 s outage: model speed vs frozen-onset speed.

    This is the metric the per-window RMSE misses. During a GNSS outage free
    dead reckoning FREEZES speed at the last known value and holds it for the
    whole outage; over 60 s the true speed changes a lot (a light, a highway
    on-ramp), so the frozen guess drifts. The model reads live IMU every window
    and tracks those changes. Along-track distance error is what feeds position
    drift, so it is the honest comparison, and it is the one the problem
    statement's <10% drift bar is about.
    """
    order = np.argsort(t_end)
    t = t_end[order]
    m = mu[order]
    tr = y[order]
    rows = []
    n = t.size
    for i0 in np.linspace(int(0.05 * n), int(0.8 * n), 12).astype(int):
        t0 = t[i0]
        i1 = int(np.searchsorted(t, t0 + deny_s))
        if i1 >= n or i1 - i0 < 20:
            continue
        dt = np.diff(t[i0:i1], prepend=t[i0])
        dt = np.clip(dt, 0.0, 0.5)
        true_d = float(np.sum(tr[i0:i1] * dt))
        if true_d < 50.0:  # need real distance to talk about drift %
            continue
        model_d = float(np.sum(m[i0:i1] * dt))
        frozen_d = float(tr[i0] * (t[i1 - 1] - t0))  # hold true onset speed
        rows.append(
            (abs(model_d - true_d), abs(frozen_d - true_d), true_d)
        )
    if not rows:
        return None
    a = np.asarray(rows)
    return {
        "n": len(rows),
        "model_dist_err_m": float(np.median(a[:, 0])),
        "frozen_dist_err_m": float(np.median(a[:, 1])),
        "model_drift_pct": float(np.median(a[:, 0] / a[:, 2] * 100.0)),
        "frozen_drift_pct": float(np.median(a[:, 1] / a[:, 2] * 100.0)),
        "model_beats_frozen": bool(np.median(a[:, 0]) < np.median(a[:, 1])),
    }


def _format_outage(outage: dict[str, Any] | None) -> str:
    if outage is None:
        return "outage: n/a"
    outcome = "WIN" if outage["model_beats_frozen"] else "lose"
    return (
        f"outage: model {outage['model_dist_err_m']:.0f}m vs frozen "
        f"{outage['frozen_dist_err_m']:.0f}m {outcome}"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", type=int, default=0, help="limit folds (0 = all clean drives)")
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--cap", type=int, default=150_000, help="max training windows per fold")
    args = ap.parse_args()

    torch.manual_seed(SEED)
    np.random.seed(SEED)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device: {device}")

    drives = clean_drives(load_corpus(verbose=False))
    print(f"clean CAN drives: {len(drives)}")
    for d in drives:
        print(f"  {d.name:<10} n={len(d):>7}  mean={np.mean(d.speed):5.2f} m/s")

    folds = drives if not args.folds else drives[: args.folds]
    rows: list[dict[str, Any]] = []
    t0 = time.time()
    for fi, held in enumerate(folds):
        train = [d for d in drives if d.name != held.name]
        model, std = train_one(train, device, args.epochs, args.cap, SEED + fi)
        mu, var = predict(model, std, held.imu, device)
        y = held.speed.astype(np.float64)
        hold = _hold_label(held).astype(np.float64)
        mean_pred = float(np.mean(np.concatenate([d.speed for d in train])))

        sd = np.sqrt(var)
        cov68 = float(np.mean(np.abs(y - mu) <= sd))
        cov95 = float(np.mean(np.abs(y - mu) <= 1.96 * sd))
        od = outage_distance(mu, y, held.t_end.astype(np.float64))
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
        }
        rows.append(row)
        print(
            f"[{fi + 1}/{len(folds)}] {held.name:<10} "
            f"model RMSE {row['model_rmse']:.3f}  hold RMSE {row['hold_rmse']:.3f}  "
            f"cov68 {cov68:.2f}  {_format_outage(od)}  "
            f"({time.time() - t0:.0f}s)"
        )

    model_rmse = np.array([r["model_rmse"] for r in rows])
    hold_rmse = np.array([r["hold_rmse"] for r in rows])
    agg = {
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
    }
    ods = [r["outage"] for r in rows if r["outage"]]
    if ods:
        agg["outage_model_dist_err_m"] = float(np.median([o["model_dist_err_m"] for o in ods]))
        agg["outage_frozen_dist_err_m"] = float(np.median([o["frozen_dist_err_m"] for o in ods]))
        agg["outage_model_drift_pct"] = float(np.median([o["model_drift_pct"] for o in ods]))
        agg["outage_frozen_drift_pct"] = float(np.median([o["frozen_drift_pct"] for o in ods]))
        agg["outage_folds_model_wins"] = int(sum(o["model_beats_frozen"] for o in ods))
        agg["outage_folds"] = len(ods)

    RESULTS.mkdir(parents=True, exist_ok=True)
    report = {"device": device, "epochs": args.epochs, "cap": args.cap,
              "aggregate": agg, "folds": rows}
    (RESULTS / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_summary(RESULTS / "summary.md", report)

    print("\n=== AGGREGATE ===")
    print(f"model median RMSE : {agg['model_median_rmse']:.3f} m/s")
    print(f"hold  median RMSE : {agg['hold_median_rmse']:.3f} m/s")
    print(f"model beats hold  : {agg['folds_model_beats_hold']}/{agg['n_folds']} folds")
    print(f"median improvement: {agg['median_improvement_pct']:.1f}%")
    print(f"uncertainty cov   : 68%->{agg['median_cov68']:.2f}  95%->{agg['median_cov95']:.2f}")

    print(f"\nwrote {RESULTS}")
    return 0


def _write_summary(path: Path, report: dict[str, Any]) -> None:
    a = report["aggregate"]
    lines = [
        "# Speed bake-off - leave-file-out, CAN labels",
        "",
        f"Device: {report['device']} | epochs/fold: {report['epochs']} | "
        f"folds: {a['n_folds']}",
        "",
        "Protocol confirmed: labels are CAN indicated vehicle speed "
        "(`speed_data`, `can_only` / `can_10hz`); leave-file-out — train on "
        "N-1 drives, score the held-out drive only.",
        "",
        "The question is whether the learned speed model beats simply **holding** "
        "the last known speed, which is what free dead reckoning does in an "
        "outage. RMSE alone is not the point; beating `hold` is.",
        "",
        "## Per-window (RMSE)",
        "",
        "| | median RMSE | note |",
        "|---|---:|---|",
        f"| **Model (AVNet-tiny)** | **{a['model_median_rmse']:.3f} m/s** | "
        f"beats hold on {a['folds_model_beats_hold']}/{a['n_folds']} folds |",
        f"| Hold last speed | {a['hold_median_rmse']:.3f} m/s | the baseline to beat |",
        f"| Predict the mean | {a['mean_median_rmse']:.3f} m/s | the floor |",
        "",
        f"Median improvement over hold: **{a['median_improvement_pct']:.1f}%**.",
        "",
    ]
    if a.get("outage_folds"):
        lines += [
            "## Closed-loop / outage distance (60 s)",
            "",
            "Integrates model speed vs freezing onset speed over mid-route "
            "60 s windows. This is the along-track metric free DR actually cares "
            "about; per-window RMSE can lose while distance still wins.",
            "",
            "| | median dist err | median drift % | folds model wins |",
            "|---|---:|---:|---:|",
            f"| **Model** | **{a['outage_model_dist_err_m']:.1f} m** | "
            f"**{a['outage_model_drift_pct']:.1f}** | "
            f"{a['outage_folds_model_wins']}/{a['outage_folds']} |",
            f"| Frozen onset speed | {a['outage_frozen_dist_err_m']:.1f} m | "
            f"{a['outage_frozen_drift_pct']:.1f} | — |",
            "",
        ]
    lines += [
        "## Uncertainty calibration",
        "",
        f"The model has a Gaussian NLL head. Empirical coverage of its nominal "
        f"intervals (median over folds): 68% target -> **{a['median_cov68']:.2f}**, "
        f"95% target -> **{a['median_cov95']:.2f}**. This is what the GNSS+INS "
        "fusion reads to decide how far to trust the speed; a well-calibrated "
        "head has coverage close to its nominal.",
        "",
        "## Per fold",
        "",
        "| held-out drive | n | model RMSE | hold RMSE | beats hold | "
        "outage model m | outage frozen m | outage win | cov68 | cov95 |",
        "|---|---:|---:|---:|:--:|---:|---:|:--:|---:|---:|",
    ]
    for r in report["folds"]:
        od = r.get("outage") or {}
        om = f"{od['model_dist_err_m']:.0f}" if od else "—"
        of = f"{od['frozen_dist_err_m']:.0f}" if od else "—"
        if od:
            ow = "yes" if od.get("model_beats_frozen") else "no"
        else:
            ow = "—"
        lines.append(
            f"| `{r['held']}` | {r['n']} | {r['model_rmse']:.3f} | "
            f"{r['hold_rmse']:.3f} | {'yes' if r['beats_hold'] else 'no'} | "
            f"{om} | {of} | {ow} | "
            f"{r['cov68']:.2f} | {r['cov95']:.2f} |"
        )
    integrity = asset_integrity(MODEL, ANDROID_ASSET)
    model = integrity["model"]
    contract = model.get("contract") if model["exists"] else None
    hash_text = model.get("sha256", "missing")[:16]
    lines += [
        "",
        "## ONNX / Android asset contract",
        "",
        f"- Model and APK asset byte-identical: **{integrity['hash_match'] is True}** "
        f"(sha256 `{hash_text}`).",
        f"- ONNX I/O: `{contract['input_name']}` {contract['input_shape']} → "
        f"`{contract['output_name']}` {contract['output_shape']}."
        if contract
        else "- ONNX model is missing; no deployment claim is allowed.",
        "- Evaluation and production export are separate: run "
        "`export_avnet_production.py` only after the leave-file-out gate.",
        "- Physical-phone inference latency is not measured by this workstation run.",
        "",
        "## Verdict",
        "",
        f"**Per-window wash:** model median RMSE {a['model_median_rmse']:.3f} m/s "
        f"vs hold {a['hold_median_rmse']:.3f} m/s; beats hold on "
        f"{a['folds_model_beats_hold']}/{a['n_folds']} folds.",
    ]
    if a.get("outage_folds"):
        lines += [
            "",
            f"**Closed-loop mixed:** model median 60 s distance error "
            f"{a['outage_model_dist_err_m']:.1f} m vs frozen "
            f"{a['outage_frozen_dist_err_m']:.1f} m "
            f"({a['outage_folds_model_wins']}/{a['outage_folds']} folds win).",
        ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
