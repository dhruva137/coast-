"""Does predicting a residual on persistence fix the 23/23 loss?

The problem
-----------
COAST-VNet-1 loses to "hold the last known speed" on every one of 23
leave-file-out folds. The diagnosis is structural, not a training failure: the
model's input is `(20, 6)` -- accelerometer and gyroscope only. It is never
shown the previous speed, which is the *sole* input the baseline it is being
compared against uses. We are asking it to beat a predictor whose only feature
it cannot see.

The fix
-------
Reformulate the output as a correction on persistence:

    v̂_t = v_prev + Δ̂        with v_prev supplied as an input channel

Persistence stops being a competitor and becomes the model's floor. Emitting
Δ̂ = 0 reproduces the baseline exactly, so losing to it on every fold becomes
structurally impossible rather than merely unlikely.

Scheduled sampling / rollout
----------------------------
Teacher-forcing on the *true* v_prev is not the deployment contract. In the
phone, v_prev is the model's own previous estimate and error compounds. After
a warmup of fully teacher-forced epochs, training mixes in the model's chained
estimate as the 7th channel (probability rises 0 → ``SS_P_MAX``). Evaluation
reports **both** teacher-forced and closed-loop rollout; headlines are rollout
and 60 s integrated distance error.

Precedent: Brossard et al.'s gyro denoiser predicts a correction to the raw
signal rather than the signal (MIT); "Persistence Initialization" (Kvernelv et
al., Applied Intelligence 2023) and R2N2 (arXiv 1709.03159) do the same in
forecasting.

The failure mode to watch for
-----------------------------
A residual model can cheat by learning Δ̂ ≈ 0 -- it then ties the baseline on
teacher-forced RMSE while contributing nothing. That is why this script reports
**closed-loop 60 s distance error** alongside RMSE, and reports the mean |Δ̂|:
a model whose corrections are all ~0 is a copier, and the numbers say so.

Usage
-----
    python -m lab.models.run_residual_speed --folds 3 --epochs 8
    python -m lab.models.run_residual_speed --epochs 12   # all clean folds
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F

REPO = Path(__file__).resolve().parents[2]
MODELS = REPO / "lab" / "models"
if str(MODELS) not in sys.path:
    sys.path.insert(0, str(MODELS))

OUT = MODELS / "results" / "residual_speed"

SEED = 26168
WINDOW_S = 2.0
CLOSED_LOOP_S = 60.0
COPIER_ABS_DELTA = 0.05
SS_P_MAX = 0.5
MIN_HISTORY_S = 1.5
BATCH = 1024


def _rmse(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.sqrt(np.mean((a - b) ** 2)))


def _closed_loop_err(pred: np.ndarray, truth: np.ndarray, t_end: np.ndarray) -> float | None:
    """Median |distance error| over CLOSED_LOOP_S windows.

    Integrating speed gives distance travelled; the gap against truth-integrated
    distance is the along-track error a dead-reckoned fix actually accumulates.
    This is the metric the product cares about -- per-window RMSE is a
    diagnostic.
    """
    order = np.argsort(t_end)
    t = t_end[order]
    p = pred[order]
    y = truth[order]
    errs: list[float] = []
    n = len(t)
    j = 0
    for i in range(n):
        while j < n and t[j] - t[i] < CLOSED_LOOP_S:
            j += 1
        if j >= n:
            break
        seg = slice(i, j)
        dt = np.diff(t[seg], prepend=t[i])
        dt = np.clip(dt, 0.0, 5.0)
        errs.append(abs(float(np.sum((p[seg] - y[seg]) * dt))))
    if len(errs) < 3:
        return None
    return float(statistics.median(errs))


def _with_vprev(imu: np.ndarray, vprev: np.ndarray) -> np.ndarray:
    """Append persistence as a constant 7th channel across the window."""
    n, w, _ = imu.shape
    ch = np.repeat(vprev.astype(np.float32).reshape(n, 1, 1), w, axis=1)
    return np.concatenate([imu, ch], axis=2)


def _predecessor_idx(t_sorted: np.ndarray) -> np.ndarray:
    """For each sorted t_end, index of the window ~WINDOW_S earlier."""
    prev_t = t_sorted.astype(np.float64) - WINDOW_S
    idx = np.searchsorted(t_sorted, prev_t, side="right") - 1
    return np.clip(idx, 0, len(t_sorted) - 1)


def _has_history(t_sorted: np.ndarray, pred_idx: np.ndarray, min_lag: float = MIN_HISTORY_S) -> np.ndarray:
    """True when the predecessor is a real ~2 s-earlier window, not clip-to-start."""
    i = np.arange(len(t_sorted))
    lag = t_sorted.astype(np.float64) - t_sorted.astype(np.float64)[pred_idx]
    return (pred_idx < i) & (lag >= min_lag)


def _ss_prob(epoch: int, n_epochs: int, p_max: float = SS_P_MAX) -> float:
    """0 during the first third of epochs, then linearly up to p_max."""
    warmup = max(1, n_epochs // 3)
    if epoch < warmup:
        return 0.0
    span = max(1, n_epochs - warmup)
    return float(p_max) * float(epoch - warmup + 1) / float(span)


def _mix_vprev(
    vpr: np.ndarray,
    delta_tf: np.ndarray,
    pred_idx: np.ndarray,
    has_hist: np.ndarray,
    p: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Time-ordered mix of true v_prev and the model's chained estimate.

    Windows are already sorted by t_end. With probability p (only where a real
    ~2 s predecessor exists) the 7th channel is the model's own previous
    speed, not the CAN label. The chain uses the mixed estimates so training
    sees compounding, matching rollout.
    """
    n = int(vpr.shape[0])
    v_used = np.empty(n, dtype=np.float32)
    v_chain = np.empty(n, dtype=np.float32)
    take = (rng.random(n) < p) & has_hist
    dlt = delta_tf.astype(np.float32, copy=False)
    src = vpr.astype(np.float32, copy=False)
    for i in range(n):
        v_used[i] = v_chain[pred_idx[i]] if take[i] else src[i]
        v_chain[i] = v_used[i] + dlt[i]
    return v_used


def _pack_drive(d: Any, hold: np.ndarray) -> dict[str, np.ndarray]:
    order = np.argsort(d.t_end)
    t = d.t_end[order].astype(np.float64)
    pred_idx = _predecessor_idx(t)
    return {
        "imu": d.imu[order],
        "speed": d.speed[order].astype(np.float32),
        "vpr": hold[order].astype(np.float32),
        "t": t,
        "pred_idx": pred_idx,
        "has_hist": _has_history(t, pred_idx),
    }


def _standardise_windows(std: Any, imu: np.ndarray, vprev: np.ndarray) -> np.ndarray:
    """Apply a 7-channel Standardiser without allocating a full concat twice."""
    x = _with_vprev(imu, vprev)
    return std(x)


@torch.no_grad()
def _predict_delta(
    model: torch.nn.Module,
    std: Any,
    imu: np.ndarray,
    vprev: np.ndarray,
    device: str,
    bs: int = BATCH,
) -> np.ndarray:
    """Teacher-forced residual Δ̂ for each window."""
    n = int(imu.shape[0])
    out = np.empty(n, dtype=np.float64)
    model.eval()
    for i in range(0, n, bs):
        sl = slice(i, i + bs)
        x = torch.from_numpy(_standardise_windows(std, imu[sl], vprev[sl])).to(device)
        out[sl] = model.split_heads(model(x))["speed"].detach().cpu().numpy()
    return out


@torch.no_grad()
def _rollout_predict(
    model: torch.nn.Module,
    std: Any,
    imu: np.ndarray,
    vpr: np.ndarray,
    t_end: np.ndarray,
    device: str,
    bs: int = BATCH,
) -> tuple[np.ndarray, np.ndarray]:
    """Closed-loop: start from true v_prev, then feed v̂ back as the ~2 s predecessor.

    Returns ``(v_hat, delta)`` aligned with the original (unsorted) window order.
    """
    n = int(imu.shape[0])
    order = np.argsort(t_end)
    t = t_end[order].astype(np.float64)
    pred_idx = _predecessor_idx(t)
    has_hist = _has_history(t, pred_idx)
    imu_o = imu[order]
    vpr_o = vpr[order].astype(np.float32)

    mean = std.mean.astype(np.float32)
    sstd = std.std.astype(np.float32)
    imu_std = torch.from_numpy(((imu_o - mean[:6]) / sstd[:6]).astype(np.float32)).to(device)
    vpr_t = torch.from_numpy(vpr_o).to(device)
    pred_t = torch.from_numpy(pred_idx.astype(np.int64)).to(device)
    hist_t = torch.from_numpy(has_hist.astype(np.bool_)).to(device)
    mean7 = float(mean[6])
    std7 = float(sstd[6])
    w = int(imu_std.shape[1])

    v_hat = torch.zeros(n, device=device, dtype=torch.float32)
    d_hat = torch.zeros(n, device=device, dtype=torch.float32)
    done = torch.zeros(n, device=device, dtype=torch.bool)

    model.eval()
    guard = 0
    remaining = n
    while remaining > 0:
        guard += 1
        if guard > n + 5:
            raise RuntimeError("rollout made no progress")
        ready = (~done) & (~hist_t | done[pred_t])
        idx = torch.nonzero(ready, as_tuple=False).reshape(-1)
        if idx.numel() == 0:
            idx = torch.nonzero(~done, as_tuple=False).reshape(-1)
        if idx.numel() == 0:
            break
        own = hist_t[idx] & done[pred_t[idx]]
        v_prev = torch.where(own, v_hat[pred_t[idx]], vpr_t[idx])
        for s in range(0, int(idx.numel()), bs):
            sl = idx[s : s + bs]
            vp = v_prev[s : s + bs]
            vch = ((vp - mean7) / std7).view(-1, 1, 1).expand(-1, w, 1)
            x = torch.cat([imu_std[sl], vch], dim=-1)
            delta = model.split_heads(model(x))["speed"]
            d_hat[sl] = delta
            v_hat[sl] = vp + delta
        done[idx] = True
        remaining = int((~done).sum().item())

    v_np = np.empty(n, dtype=np.float64)
    d_np = np.empty(n, dtype=np.float64)
    v_np[order] = v_hat.detach().cpu().numpy()
    d_np[order] = d_hat.detach().cpu().numpy()
    return v_np, d_np


def _sgd_epoch(model: torch.nn.Module, opt: torch.optim.Optimizer, x: torch.Tensor, y: torch.Tensor) -> None:
    n = x.shape[0]
    perm = torch.randperm(n, device=x.device)
    model.train()
    for i in range(0, n, BATCH):
        b = perm[i : i + BATCH]
        mu = model.split_heads(model(x[b]))["speed"]
        loss = F.smooth_l1_loss(mu, y[b])
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
        opt.step()


def _train_absolute(
    x: torch.Tensor, y: torch.Tensor, epochs: int, device: str
) -> torch.nn.Module:
    from backbone import build_model  # noqa: PLC0415

    torch.manual_seed(SEED)
    model = build_model(in_ch=6).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=2e-3, weight_decay=1e-5)
    for _ in range(epochs):
        _sgd_epoch(model, opt, x, y)
    model.eval()
    return model


def train_residual(
    packs: list[dict[str, np.ndarray]],
    epochs: int,
    device: str,
    cap: int,
    rng: np.random.Generator,
    p_max: float = SS_P_MAX,
) -> tuple[torch.nn.Module, Any]:
    """Train the 7-channel residual model with scheduled sampling.

    Standardiser is fitted on the teacher-forced (true v_prev) training
    windows. Targets are always ``speed − v_prev_used`` so Huber is on the
    residual the head actually emits. NLL / log-variance is not trained.
    """
    from backbone import build_model  # noqa: PLC0415
    from run_speed_bakeoff import Standardiser  # noqa: PLC0415

    imu = np.concatenate([p["imu"] for p in packs], axis=0)
    spd = np.concatenate([p["speed"] for p in packs], axis=0)
    vpr = np.concatenate([p["vpr"] for p in packs], axis=0)
    if cap and imu.shape[0] > cap:
        sel = rng.choice(imu.shape[0], size=cap, replace=False)
        imu_tf, spd_tf, vpr_tf = imu[sel], spd[sel], vpr[sel]
    else:
        imu_tf, spd_tf, vpr_tf = imu, spd, vpr

    std = Standardiser(_with_vprev(imu_tf, vpr_tf))
    x_tf = torch.from_numpy(_standardise_windows(std, imu_tf, vpr_tf)).to(device)
    y_tf = torch.from_numpy((spd_tf - vpr_tf).astype(np.float32)).to(device)

    torch.manual_seed(SEED)
    model = build_model(in_ch=7).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=2e-3, weight_decay=1e-5)

    for epoch in range(epochs):
        p = _ss_prob(epoch, epochs, p_max)
        if p <= 0.0:
            _sgd_epoch(model, opt, x_tf, y_tf)
            continue
        delta_tf = _predict_delta(model, std, imu, vpr, device)
        v_used_parts: list[np.ndarray] = []
        off = 0
        for pack in packs:
            n = int(pack["vpr"].shape[0])
            v_used_parts.append(
                _mix_vprev(
                    pack["vpr"],
                    delta_tf[off : off + n],
                    pack["pred_idx"],
                    pack["has_hist"],
                    p,
                    rng,
                )
            )
            off += n
        v_used = np.concatenate(v_used_parts, axis=0)
        if cap and imu.shape[0] > cap:
            sel = rng.choice(imu.shape[0], size=cap, replace=False)
            imu_e, spd_e, v_e = imu[sel], spd[sel], v_used[sel]
        else:
            imu_e, spd_e, v_e = imu, spd, v_used
        x = torch.from_numpy(_standardise_windows(std, imu_e, v_e)).to(device)
        y = torch.from_numpy((spd_e - v_e).astype(np.float32)).to(device)
        _sgd_epoch(model, opt, x, y)
        del x, y

    model.eval()
    return model, std


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--folds", type=int, default=0, help="0 = all clean drives")
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--cap", type=int, default=60_000)
    ap.add_argument("--ss-max", type=float, default=SS_P_MAX)
    args = ap.parse_args()

    from run_speed_bakeoff import Standardiser, _hold_label  # noqa: PLC0415

    raw = REPO / "data" / "raw" / "IO-VNBD"
    device = "cuda" if torch.cuda.is_available() else "cpu"
    drives = clean_or_fail(raw)
    if drives is None:
        return 1
    folds = drives if args.folds <= 0 else drives[: args.folds]
    print(
        f"device={device}  n_clean={len(drives)}  n_folds={len(folds)}  "
        f"epochs={args.epochs}  ss_max={args.ss_max}"
    )

    rng = np.random.default_rng(SEED)
    rows: list[dict] = []
    t0 = time.time()

    for fi, held in enumerate(folds, 1):
        print(f"fold {fi}/{len(folds)} held={held.name} n={len(held)}", flush=True)
        try:
            train = [d for d in drives if d.name != held.name]
            imu = np.concatenate([d.imu for d in train], axis=0)
            spd = np.concatenate([d.speed for d in train], axis=0)
            if imu.shape[0] > args.cap:
                sel = rng.choice(imu.shape[0], size=args.cap, replace=False)
                imu_abs, spd_abs = imu[sel], spd[sel]
            else:
                imu_abs, spd_abs = imu, spd

            h_imu = held.imu
            h_y = held.speed.astype(np.float64)
            h_vpr = _hold_label(held).astype(np.float64)
            hold_rmse = _rmse(h_vpr, h_y)

            std6 = Standardiser(imu_abs)
            x6 = torch.from_numpy(std6(imu_abs)).to(device)
            y_abs = torch.from_numpy(spd_abs).to(device)
            m_abs = _train_absolute(x6, y_abs, args.epochs, device)
            with torch.no_grad():
                p_abs = (
                    m_abs.split_heads(m_abs(torch.from_numpy(std6(h_imu)).to(device)))["speed"]
                    .cpu()
                    .numpy()
                    .astype(np.float64)
                )
            del x6, y_abs, m_abs

            packs = [_pack_drive(d, _hold_label(d)) for d in train]
            m_res, std7 = train_residual(packs, args.epochs, device, args.cap, rng, args.ss_max)

            d_tf = _predict_delta(m_res, std7, h_imu, h_vpr.astype(np.float32), device)
            p_tf = h_vpr + d_tf
            p_roll, d_roll = _rollout_predict(
                m_res, std7, h_imu, h_vpr.astype(np.float32), held.t_end.astype(np.float64), device
            )
            del m_res

            row = {
                "held": held.name,
                "n": int(len(h_y)),
                "hold_rmse": hold_rmse,
                "abs_rmse": _rmse(p_abs, h_y),
                "res_tf_rmse": _rmse(p_tf, h_y),
                "res_roll_rmse": _rmse(p_roll, h_y),
                "mean_abs_delta_tf": float(np.mean(np.abs(d_tf))),
                "mean_abs_delta_roll": float(np.mean(np.abs(d_roll))),
                "hold_cl": _closed_loop_err(h_vpr, h_y, held.t_end.astype(np.float64)),
                "abs_cl": _closed_loop_err(p_abs, h_y, held.t_end.astype(np.float64)),
                "res_tf_cl": _closed_loop_err(p_tf, h_y, held.t_end.astype(np.float64)),
                "res_roll_cl": _closed_loop_err(p_roll, h_y, held.t_end.astype(np.float64)),
            }
            rows.append(row)
            print(
                f"  {held.name:<10} hold {hold_rmse:6.3f} | abs {row['abs_rmse']:6.3f} "
                f"| tf {row['res_tf_rmse']:6.3f} | roll {row['res_roll_rmse']:6.3f}  "
                f"(|d|_tf {row['mean_abs_delta_tf']:.3f} |d|_roll {row['mean_abs_delta_roll']:.3f})",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001 — keep other folds; never invent a row
            print(f"  FAIL {held.name}: {type(exc).__name__}: {exc}", flush=True)
            if device == "cuda":
                torch.cuda.empty_cache()
            continue
        if device == "cuda":
            torch.cuda.empty_cache()

    if not rows:
        print("No folds completed.")
        return 1

    def med(k: str) -> float | None:
        v = [r[k] for r in rows if r[k] is not None]
        return float(statistics.median(v)) if v else None

    n = len(rows)
    agg = {
        "n_folds": n,
        "n_clean_drives": len(drives),
        "epochs": args.epochs,
        "cap": args.cap,
        "device": device,
        "wall_s": round(time.time() - t0, 1),
        "scheduled_sampling": {
            "p_max": args.ss_max,
            "warmup_epochs": max(1, args.epochs // 3),
            "chained": True,
            "lag_s": WINDOW_S,
        },
        "headline": "rollout_closed_loop",
        "hold_rmse": med("hold_rmse"),
        "abs_rmse": med("abs_rmse"),
        "res_tf_rmse": med("res_tf_rmse"),
        "res_roll_rmse": med("res_roll_rmse"),
        "mean_abs_delta_tf": med("mean_abs_delta_tf"),
        "mean_abs_delta_roll": med("mean_abs_delta_roll"),
        "hold_cl": med("hold_cl"),
        "abs_cl": med("abs_cl"),
        "res_tf_cl": med("res_tf_cl"),
        "res_roll_cl": med("res_roll_cl"),
        "abs_beats_hold": sum(1 for r in rows if r["abs_rmse"] < r["hold_rmse"]),
        "res_tf_beats_hold": sum(1 for r in rows if r["res_tf_rmse"] < r["hold_rmse"]),
        "res_roll_beats_hold": sum(1 for r in rows if r["res_roll_rmse"] < r["hold_rmse"]),
        "res_roll_beats_abs": sum(1 for r in rows if r["res_roll_rmse"] < r["abs_rmse"]),
        "copier": (med("mean_abs_delta_roll") or 0.0) < COPIER_ABS_DELTA,
        "copier_threshold": COPIER_ABS_DELTA,
        # Headline aliases: anything still reading the old keys gets rollout.
        "res_rmse": med("res_roll_rmse"),
        "mean_abs_delta": med("mean_abs_delta_roll"),
        "res_cl": med("res_roll_cl"),
        "res_beats_hold": sum(1 for r in rows if r["res_roll_rmse"] < r["hold_rmse"]),
        "rows": rows,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "report.json").write_text(json.dumps(agg, indent=2), encoding="utf-8")
    (OUT / "summary.md").write_text(_render(agg), encoding="utf-8")
    print(f"\nwrote {OUT / 'summary.md'}")
    return 0


def clean_or_fail(raw: Path) -> list | None:
    from speed_data import clean_drives, load_corpus  # noqa: PLC0415

    if not raw.is_dir():
        print(
            f"IO-VNBD missing at {raw}. Failing honestly; "
            "not inventing numbers or substituting synthetic."
        )
        return None
    drives = clean_drives(load_corpus(verbose=False))
    if not drives:
        print(
            f"No clean CAN-labelled drives under {raw}. Failing honestly; "
            "not inventing numbers or substituting synthetic."
        )
        return None
    return drives


def _fmt(v: float | None, spec: str = "{:.1f}") -> str:
    return spec.format(v) if v is not None else "—"


def _verdict(a: dict) -> str:
    n = a["n_folds"]
    copier = bool(a.get("copier")) or (a.get("mean_abs_delta_roll") or 0.0) < COPIER_ABS_DELTA
    cl = (
        f"Median 60 s closed-loop distance error (rollout / headline): residual "
        f"**{_fmt(a['res_roll_cl'])} m** vs persistence {_fmt(a['hold_cl'])} m "
        f"and absolute {_fmt(a['abs_cl'])} m. Teacher-forced residual closed-loop "
        f"is {_fmt(a['res_tf_cl'])} m (diagnostic)."
    )
    if copier:
        return (
            f"**The residual model is a copier, not a fix.** Mean |Δ̂| under "
            f"rollout is {a['mean_abs_delta_roll']:.3f} m/s -- it has learned to "
            f"emit ~0 and reproduce the baseline. It can tie teacher-forced RMSE "
            f"without contributing anything. Reject. {cl}"
        )
    if a["res_roll_beats_hold"] > a["abs_beats_hold"]:
        return (
            f"**Reformulating as a residual works under rollout.** Headlines are "
            f"closed-loop / rollout, not teacher-forced per-window RMSE. The "
            f"absolute model beats persistence on **{a['abs_beats_hold']}/{n}** "
            f"folds; the residual model beats it on **{a['res_roll_beats_hold']}/{n}** "
            f"by rollout RMSE. Teacher-forced residual wins were "
            f"{a['res_tf_beats_hold']}/{n} (diagnostic). Median rollout RMSE "
            f"{a['abs_rmse']:.3f} → **{a['res_roll_rmse']:.3f} m/s** against a "
            f"{a['hold_rmse']:.3f} baseline (teacher-forced residual "
            f"{a['res_tf_rmse']:.3f} m/s). Mean |Δ̂| (rollout) is "
            f"{a['mean_abs_delta_roll']:.3f} m/s, so the corrections are real "
            f"rather than a learned zero. {cl}"
        )
    return (
        f"**No improvement on rollout.** Absolute beats persistence on "
        f"{a['abs_beats_hold']}/{n} folds, residual rollout on "
        f"{a['res_roll_beats_hold']}/{n} (teacher-forced residual "
        f"{a['res_tf_beats_hold']}/{n}). The reformulation did not help under "
        f"the deployment contract and should not be adopted on this evidence. {cl}"
    )


def _claims_note(a: dict) -> str:
    n = a["n_folds"]
    win = (not a.get("copier")) and a["res_roll_beats_hold"] > a["abs_beats_hold"]
    fields = (
        f"| suggested claim | report.json field | measured value |\n"
        f"|---|---|---:|\n"
        f"| n_folds | `n_folds` | {n} |\n"
        f"| hold per-window RMSE (median) | `hold_rmse` | {a['hold_rmse']:.6f} |\n"
        f"| absolute per-window RMSE (median) | `abs_rmse` | {a['abs_rmse']:.6f} |\n"
        f"| residual teacher-forced RMSE (median, diagnostic) | `res_tf_rmse` | {a['res_tf_rmse']:.6f} |\n"
        f"| residual **rollout** RMSE (median, headline) | `res_roll_rmse` | {a['res_roll_rmse']:.6f} |\n"
        f"| hold 60 s distance error (median) | `hold_cl` | {_fmt(a['hold_cl'], '{:.6f}')} |\n"
        f"| absolute 60 s distance error (median) | `abs_cl` | {_fmt(a['abs_cl'], '{:.6f}')} |\n"
        f"| residual teacher-forced 60 s (median, diagnostic) | `res_tf_cl` | {_fmt(a['res_tf_cl'], '{:.6f}')} |\n"
        f"| residual **rollout** 60 s (median, headline) | `res_roll_cl` | {_fmt(a['res_roll_cl'], '{:.6f}')} |\n"
        f"| mean \\|Δ̂\\| teacher-forced | `mean_abs_delta_tf` | {a['mean_abs_delta_tf']:.6f} |\n"
        f"| mean \\|Δ̂\\| **rollout** (copier guard) | `mean_abs_delta_roll` | {a['mean_abs_delta_roll']:.6f} |\n"
        f"| absolute fold-wins vs hold | `abs_beats_hold` | {a['abs_beats_hold']}/{n} |\n"
        f"| residual rollout fold-wins vs hold | `res_roll_beats_hold` | {a['res_roll_beats_hold']}/{n} |\n"
        f"| residual teacher-forced fold-wins vs hold | `res_tf_beats_hold` | {a['res_tf_beats_hold']}/{n} |\n"
        f"| copier (`mean_abs_delta_roll` < {COPIER_ABS_DELTA}) | `copier` | {str(bool(a.get('copier'))).lower()} |\n"
        f"| epochs | `epochs` | {a['epochs']} |\n"
        f"| ss p_max | `scheduled_sampling.p_max` | {a['scheduled_sampling']['p_max']} |\n"
    )
    if win:
        return (
            "## Claims registration (parent only — do not hand-edit CLAIMS.json)\n\n"
            "Source: `lab/models/results/residual_speed/report.json`. "
            "This run met the gate (rollout fold-wins beat absolute, and mean "
            f"|Δ̂| ≥ {COPIER_ABS_DELTA} m/s). Register from these fields:\n\n"
            f"{fields}\n"
        )
    return (
        "## Claims registration — do not register this run\n\n"
        "Source: `lab/models/results/residual_speed/report.json`. "
        "The rollout gate was not met (need residual rollout fold-wins > "
        f"absolute fold-wins, and mean |Δ̂| ≥ {COPIER_ABS_DELTA} m/s). "
        "Numbers below are measured, not product claims:\n\n"
        f"{fields}\n"
    )


def _render(a: dict) -> str:
    n = a["n_folds"]
    verdict = _verdict(a)
    claims = _claims_note(a)
    rows = "\n".join(
        f"| `{r['held']}` | {r['n']} | {r['hold_rmse']:.3f} | {r['abs_rmse']:.3f} | "
        f"{r['res_tf_rmse']:.3f} | {r['res_roll_rmse']:.3f} | "
        f"{r['mean_abs_delta_tf']:.3f} | {r['mean_abs_delta_roll']:.3f} |"
        for r in a["rows"]
    )
    ss = a["scheduled_sampling"]
    return f"""# Residual-on-persistence speed model

Reproduce: `python -m lab.models.run_residual_speed --epochs 12`

{claims}COAST-VNet-1 loses to "hold the last known speed" on every leave-file-out fold.
The diagnosis is structural: the 6-channel model sees only `(20, 6)` accelerometer
and gyroscope, and is never shown the previous speed -- the sole input the
baseline uses. This tests supplying it and predicting a correction:

    v̂ = v_prev + Δ̂        v_prev appended as a 7th input channel

**n_folds = {n}** leave-file-out (all clean CAN-labelled drives this run:
{a.get('n_clean_drives', n)}). `--folds 0` means every clean drive, not a
smoke subset. Headlines below are **rollout / closed-loop**. Teacher-forced
per-window RMSE is a diagnostic: in deployment `v_prev` is the model's own
estimate.

## Verdict

{verdict}

## Results ({n} folds, {a['epochs']} epochs, Huber on the mean, scheduled sampling p→{ss['p_max']} after {ss['warmup_epochs']} warmup epochs, {a['device']}, {a['wall_s']}s)

| model | median per-window RMSE | beats persistence | median 60 s distance error |
|---|---:|---:|---:|
| Hold last speed (baseline) | **{a['hold_rmse']:.3f} m/s** | — | {_fmt(a['hold_cl'])} m |
| Absolute (current 6-ch design) | {a['abs_rmse']:.3f} m/s | {a['abs_beats_hold']}/{n} | {_fmt(a['abs_cl'])} m |
| Residual, teacher-forced (diagnostic) | {a['res_tf_rmse']:.3f} m/s | {a['res_tf_beats_hold']}/{n} | {_fmt(a['res_tf_cl'])} m |
| **Residual, rollout (headline)** | **{a['res_roll_rmse']:.3f} m/s** | **{a['res_roll_beats_hold']}/{n}** | **{_fmt(a['res_roll_cl'])} m** |

Mean |Δ̂| teacher-forced = {a['mean_abs_delta_tf']:.3f} m/s. Mean |Δ̂| **rollout**
= **{a['mean_abs_delta_roll']:.3f} m/s**. Copier guard: reject if rollout
mean |Δ̂| < {COPIER_ABS_DELTA} m/s (this run: **{'copier — reject' if a.get('copier') else 'not a copier'}**).

## Why persistence can no longer win outright on teacher-forcing

Emitting Δ̂ = 0 reproduces the baseline exactly when `v_prev` is the true
previous speed, so the baseline is the model's floor rather than its competitor
on the teacher-forced metric. Rollout is the honest test: the first window uses
the true `v_prev`, then each later window's 7th channel is the model's own
estimate from ~{WINDOW_S:.1f} s earlier (the same lag `_hold_label` uses).

## Limitations

- Scheduled sampling mixes the model's own `v_prev` with probability rising
  from 0 to {ss['p_max']} after {ss['warmup_epochs']} teacher-forced warmup
  epochs; it is not always-on full rollout training.
- Huber loss on the mean only. The log-variance head is not trained here,
  deliberately: the NLL coupling is what produced the variance-inflation
  pathology documented in `../nll_diagnosis/`.
- Closed-loop error is along-track distance from integrating speed. It does not
  include heading error, so it is not a full position result.
- Sampling is 10 Hz, so Nyquist is 5 Hz. The architecture's high-frequency
  branch was designed for road and engine vibration at 20–100 Hz and cannot
  observe it at this rate. Resampling the IMU to 50–100 Hz may be worth more
  than further architecture changes.

## Per fold

| held-out | n | hold RMSE | absolute | residual TF | residual rollout | mean \\|Δ̂\\| TF | mean \\|Δ̂\\| roll |
|---|---:|---:|---:|---:|---:|---:|---:|
{rows}
"""


if __name__ == "__main__":
    raise SystemExit(main())
