"""AI-IMU-DR-style loosely-coupled GNSS+INS: learn diag(R), not the motion.

PS 26168 asks for an "AI based Sensor Fusion Algorithm". The frozen classical
loosely-coupled EKF in ``lab/stress/results/gnss_ins_fusion/`` measured **1.07×
vs phone GNSS — a wash**. IO-VNBD has no pseudoranges or carrier phase, so a
true tightly-coupled (range-domain) filter cannot be run on this corpus. This
script does not pretend otherwise.

Recipe (Brossard, Barrau, Bonnabel 2020; MIT-licensed
github.com/mbrossar/ai-imu-dr):
  * Keep the EKF structure of ``run_gnss_ins_fusion.py``.
  * A small network sets measurement covariance R online (diagonal).
  * Between GNSS fixes, three pseudo-measurements: non-holonomic constraint
    (zero *lateral* velocity; planar state has no vertical channel), COAST
    speed if ONNX loads else CAN-speed ORACLE + persistence/hold-speed
    ablations (labelled), and ZUPT when stopped.
  * Two-stage: freeze / skip speed *mean*; optimise only the covariance head
    against **60 s integrated position error**, not NLL.

Writes ``lab/stress/results/gnss_ins_fusion_ai/{report.json,summary.md}``.
Does **not** overwrite the frozen classical report.

CPU only. A measured negative is a valid answer.

Run:
    python lab/stress/run_ai_imu_fusion.py
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")

_STRESS = Path(__file__).resolve().parent
_LAB = _STRESS.parent
_FROZEN_FUSION = _STRESS / "results" / "gnss_ins_fusion"
for _p in (_STRESS, _LAB / "eval"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from ai_fusion_r import (  # noqa: E402
    FEATURE_NAMES,
    OUT_GNSS,
    OUT_NHC,
    OUT_SPEED,
    OUT_ZUPT,
    LogVarRHead,
    fit_feature_norm,
    fusion_features,
    highband_energy,
    nelder_mead_bias,
    probe_coast_onnx,
    spsa_fit,
)
from learned_gnss_policy import split_drive_paths  # noqa: E402
from load_iovnbd import find_smartphone_csvs  # noqa: E402
from metrics import lla_to_enu  # noqa: E402
from run_gnss_ins_fusion import (  # noqa: E402
    DEGRADED_ACC_H_M,
    GYRO_CUTOFF_HZ,
    WINDOW_S,
    _eligible_windows,
    _enu_err,
    _fused_track,
    _ins_only_track,
    _prepare_data as _prepare_iovnbd_classical,
    _wrap_pi,
    _yaw0_from_truth,
)

N_STATE = 6  # e, n, v_fwd, v_lat, yaw, bg
ZUPT_SPEED_MPS = 0.4
ZUPT_GYRO_RAD_S = 0.05
MIN_FIX_CHANGE_DEG = 1e-7


def _joseph_update(
    x: np.ndarray, P: np.ndarray, z: np.ndarray, H: np.ndarray, R: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    y = z - H @ x
    S = H @ P @ H.T + R
    try:
        K = np.linalg.solve(S, H @ P).T
    except np.linalg.LinAlgError:
        return x, P
    dx = K @ y
    i_kh = np.eye(N_STATE) - K @ H
    P_new = i_kh @ P @ i_kh.T + K @ R @ K.T
    P_new = 0.5 * (P_new + P_new.T)
    x_new = x + dx
    x_new[4] = _wrap_pi(float(x_new[4]))
    x_new[2] = max(float(x_new[2]), 0.0)
    return x_new, P_new


def _ai_seed(v0: float, yaw0: float, acc_h: float) -> tuple[np.ndarray, np.ndarray]:
    r = max(float(acc_h), 2.0) ** 2
    P = np.diag(
        [
            r,
            r,
            1.0,
            0.25,
            (10.0 * math.pi / 180.0) ** 2,
            (0.05) ** 2,
        ]
    ).astype(np.float64)
    x = np.array([0.0, 0.0, max(float(v0), 0.0), 0.0, float(yaw0), 0.0], dtype=np.float64)
    return x, P


def _ai_propagate(
    x: np.ndarray, P: np.ndarray, dt: float, gz: float
) -> tuple[np.ndarray, np.ndarray]:
    if dt <= 0.0 or dt > 0.5:
        return x, P
    e, n, vf, vl, yaw, bg = (float(v) for v in x)
    yaw_rate = gz - bg
    e2 = e + (vf * math.sin(yaw) + vl * math.cos(yaw)) * dt
    n2 = n + (vf * math.cos(yaw) - vl * math.sin(yaw)) * dt
    yaw2 = _wrap_pi(yaw + yaw_rate * dt)
    x2 = np.array([e2, n2, vf, vl, yaw2, bg], dtype=np.float64)

    F = np.eye(N_STATE)
    F[0, 2] = math.sin(yaw) * dt
    F[0, 3] = math.cos(yaw) * dt
    F[0, 4] = (vf * math.cos(yaw) - vl * math.sin(yaw)) * dt
    F[1, 2] = math.cos(yaw) * dt
    F[1, 3] = -math.sin(yaw) * dt
    F[1, 4] = (-vf * math.sin(yaw) - vl * math.cos(yaw)) * dt
    F[4, 5] = -dt
    qe = (0.5 * dt) ** 2
    Q = np.diag(
        [qe, qe, (0.8 * dt) ** 2, (0.8 * dt) ** 2, (0.05 * dt) ** 2, (1e-4 * dt) ** 2]
    )
    P2 = F @ P @ F.T + Q
    P2 = 0.5 * (P2 + P2.T)
    return x2, P2


def _hold_speed(speed: np.ndarray, fix_changed: np.ndarray) -> np.ndarray:
    """Persistence: last unique-fix phone speed (online; not CAN)."""
    n = speed.size
    out = np.zeros(n, dtype=np.float64)
    last = 0.0
    seeded = False
    for i in range(n):
        s = float(speed[i])
        if np.isfinite(s) and (not seeded or bool(fix_changed[i])):
            last = max(s, 0.0)
            seeded = True
        out[i] = last
    return out


def _oracle_speed(can_speed: np.ndarray, persist: np.ndarray) -> np.ndarray:
    out = persist.copy()
    finite = np.isfinite(can_speed)
    out[finite] = np.maximum(can_speed[finite], 0.0)
    return out


@dataclass
class AiRollout:
    xy: np.ndarray
    mean_sigma: dict[str, float]
    n_nhc: int
    n_zupt: int
    n_speed: int
    n_gnss: int
    features_at_gnss: list[np.ndarray]


def _ai_fused_track(
    t: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    acc_h: np.ndarray,
    gz: np.ndarray,
    energy: np.ndarray,
    speed_src: np.ndarray,
    fix_changed: np.ndarray,
    lat0: float,
    lon0: float,
    yaw0: float,
    head: LogVarRHead,
    *,
    collect_features: bool = False,
) -> AiRollout:
    n = t.size
    xy = np.empty((n, 2), dtype=np.float64)
    v0 = float(speed_src[0]) if np.isfinite(speed_src[0]) else 0.0
    x, P = _ai_seed(v0, yaw0, float(acc_h[0]) if np.isfinite(acc_h[0]) else 5.0)
    xy[0] = (x[0], x[1])
    last_fix_t = float(t[0])
    sig_acc = np.zeros(4, dtype=np.float64)
    n_sig = 0
    n_nhc = n_zupt = n_speed = n_gnss = 0
    feats: list[np.ndarray] = []

    H_gnss = np.zeros((2, N_STATE))
    H_gnss[0, 0] = 1.0
    H_gnss[1, 1] = 1.0
    H_speed = np.zeros((1, N_STATE))
    H_speed[0, 2] = 1.0
    H_nhc = np.zeros((1, N_STATE))
    H_nhc[0, 3] = 1.0
    H_zupt = np.zeros((2, N_STATE))
    H_zupt[0, 2] = 1.0
    H_zupt[1, 3] = 1.0

    for i in range(1, n):
        dt = float(t[i] - t[i - 1])
        x, P = _ai_propagate(x, P, dt, float(gz[i - 1]))
        spd = float(speed_src[i]) if np.isfinite(speed_src[i]) else float(x[2])
        stopped = spd < ZUPT_SPEED_MPS and abs(float(gz[i])) < ZUPT_GYRO_RAD_S
        a_h = float(acc_h[i]) if np.isfinite(acc_h[i]) else 5.0
        sigma = math.sqrt(max(float(P[0, 0] + P[1, 1]), 0.0) / 2.0)
        gnss_now = bool(fix_changed[i]) and np.isfinite(lat[i]) and np.isfinite(lon[i])
        innov = 0.0
        enu = None
        if gnss_now:
            enu = lla_to_enu(
                np.array([lat[i]]),
                np.array([lon[i]]),
                origin_lat_deg=lat0,
                origin_lon_deg=lon0,
            )[0]
            innov = math.hypot(float(enu[0]) - float(x[0]), float(enu[1]) - float(x[1]))
        feat = fusion_features(
            a_h,
            innov,
            sigma,
            float(t[i] - last_fix_t),
            abs(float(gz[i])),
            float(energy[i]),
            spd,
            1.0 if stopped else 0.0,
        )
        var = head.variances(feat)
        sig_acc += np.sqrt(np.maximum(var, 1e-12))
        n_sig += 1
        if collect_features and (gnss_now or i % 10 == 0):
            feats.append(feat)

        if stopped:
            R = np.diag([float(var[OUT_ZUPT]), float(var[OUT_ZUPT])])
            x, P = _joseph_update(x, P, np.zeros(2), H_zupt, R)
            n_zupt += 1
        else:
            x, P = _joseph_update(
                x,
                P,
                np.zeros(1),
                H_nhc,
                np.array([[float(var[OUT_NHC])]], dtype=np.float64),
            )
            n_nhc += 1
            if np.isfinite(speed_src[i]):
                x, P = _joseph_update(
                    x,
                    P,
                    np.array([spd], dtype=np.float64),
                    H_speed,
                    np.array([[float(var[OUT_SPEED])]], dtype=np.float64),
                )
                n_speed += 1

        if gnss_now and enu is not None:
            r = float(var[OUT_GNSS])
            x, P = _joseph_update(
                x,
                P,
                np.array([float(enu[0]), float(enu[1])], dtype=np.float64),
                H_gnss,
                np.diag([r, r]),
            )
            last_fix_t = float(t[i])
            n_gnss += 1
        xy[i] = (x[0], x[1])

    denom = max(n_sig, 1)
    return AiRollout(
        xy=xy,
        mean_sigma={
            "gnss_m": float(sig_acc[OUT_GNSS] / denom),
            "speed_mps": float(sig_acc[OUT_SPEED] / denom),
            "nhc_mps": float(sig_acc[OUT_NHC] / denom),
            "zupt_mps": float(sig_acc[OUT_ZUPT] / denom),
        },
        n_nhc=n_nhc,
        n_zupt=n_zupt,
        n_speed=n_speed,
        n_gnss=n_gnss,
        features_at_gnss=feats,
    )


def _stats(err: np.ndarray, mask: np.ndarray | None = None) -> dict[str, float]:
    e = err if mask is None else err[mask]
    e = e[np.isfinite(e)]
    if e.size == 0:
        return {
            "n": 0,
            "rmse_m": float("nan"),
            "median_m": float("nan"),
            "p90_m": float("nan"),
            "end_m": float("nan"),
        }
    return {
        "n": int(e.size),
        "rmse_m": float(np.sqrt(np.mean(e * e))),
        "median_m": float(np.median(e)),
        "p90_m": float(np.percentile(e, 90)),
        "end_m": float(e[-1]),
    }


def _prepare_data(path: Path) -> tuple[dict[str, Any], np.ndarray, np.ndarray] | None:
    """Same IO-VNBD CAN-paired load as ``run_gnss_ins_fusion._prepare_data``.

    Adds high-band accel energy for the R-head features only.
    """
    prepared = _prepare_iovnbd_classical(path)
    if prepared is None:
        return None
    data, gz, fix_changed = prepared
    n = int(data["_t"].size)
    try:
        ax = np.asarray(data["ax"][:n], dtype=np.float64)
        ay = np.asarray(data["ay"][:n], dtype=np.float64)
        az = np.asarray(data["az"][:n], dtype=np.float64)
    except (KeyError, TypeError, ValueError):
        return None
    data["_ax"] = ax
    data["_ay"] = ay
    data["_az"] = az
    data["_energy"] = highband_energy(ax, ay, az)
    return data, gz, fix_changed


def _window_rmse(
    data: dict[str, Any],
    i0: int,
    i1: int,
    gz: np.ndarray,
    fix_changed: np.ndarray,
    speed_src: np.ndarray,
    head: LogVarRHead,
) -> float | None:
    yaw0 = _yaw0_from_truth(data["_cla"], data["_clo"], i0)
    if yaw0 is None:
        return None
    sl = slice(i0, i1)
    lat0, lon0 = float(data["_cla"][i0]), float(data["_clo"][i0])
    truth = lla_to_enu(data["_cla"][sl], data["_clo"][sl], origin_lat_deg=lat0, origin_lon_deg=lon0)
    roll = _ai_fused_track(
        data["_t"][sl],
        data["_lat"][sl],
        data["_lon"][sl],
        data["_acc"][sl],
        gz[sl],
        data["_energy"][sl],
        speed_src[sl],
        fix_changed[sl],
        lat0,
        lon0,
        yaw0,
        head,
    )
    err = _enu_err(roll.xy, truth)
    err = err[np.isfinite(err)]
    if err.size == 0:
        return None
    return float(np.sqrt(np.mean(err * err)))


def run_window(
    data: dict[str, Any],
    i0: int,
    i1: int,
    gz: np.ndarray,
    fix_changed: np.ndarray,
    persist: np.ndarray,
    oracle: np.ndarray,
    head: LogVarRHead,
    *,
    split: str,
) -> dict[str, Any] | None:
    t = data["_t"]
    lat, lon = data["_lat"], data["_lon"]
    speed = data["_v"]
    bearing = data["_bearing"]
    acc_h = data["_acc"]
    cla, clo = data["_cla"], data["_clo"]
    yaw0 = _yaw0_from_truth(cla, clo, i0)
    if yaw0 is None:
        return None
    lat0, lon0 = float(cla[i0]), float(clo[i0])
    e0, n0 = 0.0, 0.0
    sl = slice(i0, i1)
    n_samp = i1 - i0
    if n_samp < 30:
        return None

    truth = lla_to_enu(cla[sl], clo[sl], origin_lat_deg=lat0, origin_lon_deg=lon0)
    gnss_xy = lla_to_enu(lat[sl], lon[sl], origin_lat_deg=lat0, origin_lon_deg=lon0)
    ins_xy = _ins_only_track(t[sl], speed[sl], gz[sl], e0, n0, yaw0)
    fused_xy = _fused_track(
        t[sl],
        lat[sl],
        lon[sl],
        speed[sl],
        bearing[sl],
        acc_h[sl],
        gz[sl],
        fix_changed[sl],
        lat0,
        lon0,
        e0,
        n0,
        yaw0,
    )
    ai_p = _ai_fused_track(
        t[sl],
        lat[sl],
        lon[sl],
        acc_h[sl],
        gz[sl],
        data["_energy"][sl],
        persist[sl],
        fix_changed[sl],
        lat0,
        lon0,
        yaw0,
        head,
    )
    ai_o = _ai_fused_track(
        t[sl],
        lat[sl],
        lon[sl],
        acc_h[sl],
        gz[sl],
        data["_energy"][sl],
        oracle[sl],
        fix_changed[sl],
        lat0,
        lon0,
        yaw0,
        head,
    )

    err_g = _enu_err(gnss_xy, truth)
    err_i = _enu_err(ins_xy, truth)
    err_f = _enu_err(fused_xy, truth)
    err_ap = _enu_err(ai_p.xy, truth)
    err_ao = _enu_err(ai_o.xy, truth)

    acc = np.asarray(acc_h[sl], dtype=np.float64)
    degraded = np.isfinite(acc) & (acc >= DEGRADED_ACC_H_M)
    held = ~fix_changed[sl]
    held[0] = False
    soft_degraded = degraded | held

    methods_all = {
        "gnss_only": _stats(err_g),
        "ins_only": _stats(err_i),
        "fused": _stats(err_f),
        "ai_fused_persistence": _stats(err_ap),
        "ai_fused_oracle_can": _stats(err_ao),
    }
    methods_deg = {
        "gnss_only": _stats(err_g, soft_degraded),
        "ins_only": _stats(err_i, soft_degraded),
        "fused": _stats(err_f, soft_degraded),
        "ai_fused_persistence": _stats(err_ap, soft_degraded),
        "ai_fused_oracle_can": _stats(err_ao, soft_degraded),
        "n_mask": int(np.sum(soft_degraded)),
        "n_acc_h_ge": int(np.sum(degraded)),
        "n_held": int(np.sum(held)),
    }
    dt = np.diff(t[sl], prepend=t[i0])
    dist = float(np.nansum(np.clip(data["_cv"][sl], 0, None) * np.clip(dt, 0, 0.5)))
    return {
        "start_idx": int(i0),
        "n_samples": n_samp,
        "duration_s": float(t[i1 - 1] - t[i0]),
        "distance_m": dist,
        "n_gnss_fixes": int(np.sum(fix_changed[sl])),
        "split": split,
        "all": methods_all,
        "degraded": methods_deg,
        "ai_persistence_sigma": ai_p.mean_sigma,
        "ai_oracle_sigma": ai_o.mean_sigma,
        "ai_persistence_counts": {
            "n_nhc": ai_p.n_nhc,
            "n_zupt": ai_p.n_zupt,
            "n_speed": ai_p.n_speed,
            "n_gnss": ai_p.n_gnss,
        },
        "fused_beats_gnss_median": bool(
            methods_all["fused"]["median_m"] < methods_all["gnss_only"]["median_m"]
        ),
        "ai_persist_beats_gnss_median": bool(
            methods_all["ai_fused_persistence"]["median_m"]
            < methods_all["gnss_only"]["median_m"]
        ),
        "ai_persist_beats_classical_median": bool(
            methods_all["ai_fused_persistence"]["median_m"]
            < methods_all["fused"]["median_m"]
        ),
        "ai_persist_beats_gnss_degraded": bool(
            methods_deg["ai_fused_persistence"]["median_m"]
            < methods_deg["gnss_only"]["median_m"]
        ),
    }


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"n_windows": 0}

    def gather(bucket: str, method: str, key: str) -> np.ndarray:
        vals = []
        for r in rows:
            block = r[bucket].get(method)
            if not isinstance(block, dict):
                continue
            v = block.get(key, float("nan"))
            if np.isfinite(v):
                vals.append(v)
        return np.asarray(vals, dtype=np.float64)

    methods = [
        name
        for name in (
            "gnss_only",
            "ins_only",
            "fused",
            "ai_fused_persistence",
            "ai_fused_oracle_can",
        )
        if name in rows[0]["all"]
    ]
    out: dict[str, Any] = {"n_windows": len(rows), "methods": methods}
    for bucket in ("all", "degraded"):
        block: dict[str, Any] = {}
        for method in methods:
            med = gather(bucket, method, "median_m")
            rmse = gather(bucket, method, "rmse_m")
            p90 = gather(bucket, method, "p90_m")
            block[method] = {
                "median_of_medians_m": float(np.median(med)) if med.size else float("nan"),
                "median_of_rmse_m": float(np.median(rmse)) if rmse.size else float("nan"),
                "median_of_p90_m": float(np.median(p90)) if p90.size else float("nan"),
            }
        g = block["gnss_only"]["median_of_medians_m"]
        i = block["ins_only"]["median_of_medians_m"]
        f = block["fused"]["median_of_medians_m"]
        ap = block["ai_fused_persistence"]["median_of_medians_m"]
        ao = block["ai_fused_oracle_can"]["median_of_medians_m"]

        def _x(num: float, den: float) -> float:
            if np.isfinite(num) and np.isfinite(den) and den > 1e-9:
                return float(num / den)
            return float("nan")

        block["fused_vs_gnss_x"] = _x(g, f)
        block["fused_vs_ins_x"] = _x(i, f)
        block["fused_beats_gnss"] = bool(np.isfinite(f) and np.isfinite(g) and f < g)
        block["fused_beats_ins"] = bool(np.isfinite(f) and np.isfinite(i) and f < i)
        block["ai_persistence_vs_gnss_x"] = _x(g, ap)
        block["ai_oracle_vs_gnss_x"] = _x(g, ao)
        block["fused_vs_classical_ekf"] = _x(f, ap)  # >1 ⇒ persistence AI beats classical
        block["ai_persistence_vs_classical_ekf"] = _x(f, ap)
        block["ai_oracle_vs_classical_ekf"] = _x(f, ao)
        block["ai_persistence_beats_gnss"] = bool(
            np.isfinite(ap) and np.isfinite(g) and ap < g
        )
        block["ai_persistence_beats_classical"] = bool(
            np.isfinite(ap) and np.isfinite(f) and ap < f
        )
        block["ai_oracle_beats_classical"] = bool(
            np.isfinite(ao) and np.isfinite(f) and ao < f
        )
        out[bucket] = block

    out["windows_fused_beats_gnss"] = int(sum(r["fused_beats_gnss_median"] for r in rows))
    out["windows_ai_persist_beats_gnss"] = int(
        sum(r["ai_persist_beats_gnss_median"] for r in rows)
    )
    out["windows_ai_persist_beats_classical"] = int(
        sum(r["ai_persist_beats_classical_median"] for r in rows)
    )
    out["windows_ai_persist_beats_gnss_degraded"] = int(
        sum(r["ai_persist_beats_gnss_degraded"] for r in rows)
    )
    return out


def write_summary(path: Path, report: dict[str, Any]) -> None:
    s = report.get("summary") or {}
    held = report.get("held_out_summary") or {}
    lim = report.get("limitations") or []
    train = report.get("training") or {}
    onnx = report.get("coast_onnx") or {}
    lines = [
        "# AI-IMU-DR-style GNSS+INS fusion (learned diag(R))",
        "",
        "Falsification test for PS 26168 expected solution 4: an **AI-based**",
        "sensor-fusion algorithm. The frozen classical loosely-coupled EKF measured",
        "**1.07× vs phone GNSS — a wash** (`lab/stress/results/gnss_ins_fusion/`).",
        "This run keeps that EKF structure, adds NHC / speed / ZUPT",
        "pseudo-measurements, and trains a small log-variance head to emit",
        "`diag(R)` against **60 s integrated position error** (not NLL).",
        "",
        "**Coupling:** loosely-coupled (position-domain). IO-VNBD has **no",
        "pseudoranges / carrier** — true tight coupling is not runnable on this corpus.",
        "",
        f"Drives used: **{report.get('n_files', 0)}** | windows: **{s.get('n_windows', 0)}** | ",
        f"window length: {report.get('window_s', WINDOW_S):.0f} s | ",
        f"gyro LP causal {GYRO_CUTOFF_HZ} Hz | ",
        f"degraded: acc_h ≥ {DEGRADED_ACC_H_M:.0f} m **or** held phone fix. ",
        "Truth: paired CAN 10 Hz (`truth_source=can_10hz` only).",
        "",
        "Speed mean: **frozen / skipped** (no exported residual-speed ONNX). "
        f"ONNX probe: `{onnx.get('reason', 'not recorded')}`.",
        "",
        "Speed ablations (labelled):",
        "- `ai_fused_persistence` — hold last unique-fix **phone** speed (online).",
        "- `ai_fused_oracle_can` — CAN indicated speed at 10 Hz (**ORACLE**, not a product claim).",
        "",
        f"Training (drive-level split, seed {train.get('seed', 26168)}): "
        f"stage-2a Nelder-Mead on global log-R bias, then SPSA on the MLP, ",
        f"loss = mean 60 s position RMSE on training windows only. "
        f"Init loss {train.get('init_loss', float('nan'))} → "
        f"final {train.get('final_loss', float('nan'))}.",
        "",
        "## All samples (same windowing as classical fusion defaults)",
        "",
        "| Estimator | median of window medians | median of RMSEs | median of p90 |",
        "|---|---:|---:|---:|",
    ]
    labels = (
        ("GNSS-only (phone hold)", "gnss_only"),
        ("INS-only (open DR)", "ins_only"),
        ("Classical LC-EKF (reimplemented)", "fused"),
        ("AI fused + persistence speed", "ai_fused_persistence"),
        ("AI fused + CAN speed (ORACLE)", "ai_fused_oracle_can"),
    )
    if s.get("n_windows", 0) == 0:
        lines += ["", "**No scored windows.** See limitations.", ""]
    else:
        a = s["all"]
        for name, key in labels:
            if key not in a:
                continue
            b = a[key]
            lines.append(
                f"| {name} | {b['median_of_medians_m']:.2f} m | "
                f"{b['median_of_rmse_m']:.2f} m | {b['median_of_p90_m']:.2f} m |"
            )
        ai_vs_c = a.get("fused_vs_classical_ekf", float("nan"))
        sign = (
            "POSITIVE (AI persistence beats classical median-of-medians)"
            if a.get("ai_persistence_beats_classical")
            else "NEGATIVE (AI persistence does **not** beat classical)"
        )
        lines += [
            "",
            f"Classical fused vs GNSS-only: **{a['fused_vs_gnss_x']:.2f}×** "
            f"({'beats' if a['fused_beats_gnss'] else 'DOES NOT beat'} GNSS-only).",
            f"AI persistence vs GNSS-only: **{a['ai_persistence_vs_gnss_x']:.2f}×** "
            f"({'beats' if a['ai_persistence_beats_gnss'] else 'DOES NOT beat'} GNSS-only).",
            f"AI persistence vs classical EKF: **{ai_vs_c:.2f}×** — **{sign}**.",
            f"AI oracle-CAN vs classical EKF: **{a['ai_oracle_vs_classical_ekf']:.2f}×** "
            f"(ORACLE speed; not a product number).",
            f"Windows AI-persistence median < GNSS: "
            f"**{s['windows_ai_persist_beats_gnss']}/{s['n_windows']}**.",
            f"Windows AI-persistence median < classical: "
            f"**{s['windows_ai_persist_beats_classical']}/{s['n_windows']}**.",
            "",
            "## Degraded subset (acc_h ≥ threshold OR held phone fix)",
            "",
            "| Estimator | median of window medians | median of RMSEs | median of p90 |",
            "|---|---:|---:|---:|",
        ]
        d = s["degraded"]
        for name, key in labels:
            if key not in d:
                continue
            b = d[key]
            lines.append(
                f"| {name} | {b['median_of_medians_m']:.2f} m | "
                f"{b['median_of_rmse_m']:.2f} m | {b['median_of_p90_m']:.2f} m |"
            )
        lines += [
            "",
            f"AI persistence vs GNSS-only (degraded): **{d['ai_persistence_vs_gnss_x']:.2f}×**.",
            f"AI persistence vs classical EKF (degraded): **{d['fused_vs_classical_ekf']:.2f}×**.",
            f"Windows where AI-persistence beats GNSS on degraded mask: "
            f"**{s['windows_ai_persist_beats_gnss_degraded']}/{s['n_windows']}**.",
            "",
        ]

    if held.get("n_windows"):
        ha = held["all"]
        lines += [
            "## Held-out drives only (leakage-safe)",
            "",
            f"Windows: **{held['n_windows']}**. R-head was not fit on these basenames.",
            "",
            f"Classical vs GNSS: **{ha['fused_vs_gnss_x']:.2f}×**. ",
            f"AI persistence vs GNSS: **{ha['ai_persistence_vs_gnss_x']:.2f}×**. ",
            f"AI persistence vs classical: **{ha['fused_vs_classical_ekf']:.2f}×**.",
            "",
        ]

    lines += [
        "## Method notes",
        "",
        "- Precedent: Brossard et al. learn NHC covariance inside an IEKF; they do",
        "  **not** learn the motion. Same split here: EKF kinematics + learned `diag(R)`.",
        "- Classical LC-EKF is the in-script reimplementation of",
        "  `run_gnss_ins_fusion.py` (5-state, GNSS R from `acc_h`) on the **same** windows.",
        "- AI state is 6-D planar: east, north, v_fwd, v_lat, yaw, gyro bias.",
        "- Pseudo-measurements between unique phone fixes: NHC `v_lat≈0`, speed",
        "  (persistence or oracle CAN), ZUPT when speed < 0.4 m/s and |gyro| < 0.05 rad/s.",
        "- Vertical NHC is not applied (no `v_up` in the planar state).",
        "- Feature-dependent MLP (8 → hidden → 4 log-variances) + output-bias fit.",
        f"- Features: {', '.join(FEATURE_NAMES)}.",
        "",
        "## Limitations",
        "",
    ]
    if lim:
        for item in lim:
            lines.append(f"- {item}")
    else:
        lines.append("- None recorded.")
    lines += [
        "",
        "Do not quote this as tightly-coupled fusion. Do not quote oracle-CAN as an",
        "on-device result. A measured negative vs the classical 1.07× EKF is still",
        "the honest answer to the AI-fusion requirement.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _empty_report(limitations: list[str], window_s: float, out_dir: Path) -> int:
    report = {
        "coupling": "loosely-coupled position-domain + learned diag(R)",
        "tight_coupling_possible": False,
        "window_s": window_s,
        "n_files": 0,
        "summary": {"n_windows": 0},
        "limitations": limitations,
        "files": [],
        "precedent": "Brossard et al. AI-IMU-DR (MIT, github.com/mbrossar/ai-imu-dr)",
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_summary(out_dir / "summary.md", report)
    print("NO DATA — wrote empty summary with limitation")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", type=int, default=0, help="Cap S-*.csv (0=all, same as classical defaults)")
    ap.add_argument("--segments", type=int, default=8, help="Windows per file (classical default 8)")
    ap.add_argument("--window-s", type=float, default=WINDOW_S)
    ap.add_argument("--eval-fraction", type=float, default=0.3)
    ap.add_argument("--bias-iters", type=int, default=20)
    ap.add_argument("--spsa-iters", type=int, default=8)
    ap.add_argument("--train-windows", type=int, default=24)
    ap.add_argument("--n-hidden", type=int, default=8)
    ap.add_argument("--output-dir")
    args = ap.parse_args()

    out_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else (_STRESS / "results" / "gnss_ins_fusion_ai")
    )
    if out_dir.resolve() == _FROZEN_FUSION.resolve():
        raise ValueError("refusing to overwrite frozen lab/stress/results/gnss_ins_fusion")

    limitations: list[str] = [
        "IO-VNBD exposes LLA/speed/acc_h only — loosely-coupled fusion, not tight (no pseudoranges).",
        "Phone GNSS is sparse (~0.1 Hz unique fixes held across ~10 Hz rows).",
        "IMU is 10 Hz (Nyquist 5 Hz). AI-IMU-DR used automotive IMU at 100–200 Hz; "
        "road/engine vibration the high-band was designed for is already aliased.",
        "Planar EKF: vertical NHC (v_up≈0) is not applied; lateral NHC is v_lat≈0.",
        "Phone mount yaw vs vehicle is weakly observable (online alignment measured a wash); "
        "NHC assumes a vehicle-frame lateral axis we do not perfectly have.",
        "Speed mean is skipped (residual/COAST ONNX not loaded). Persistence is online; "
        "CAN indicated speed is an ORACLE ablation and must be labelled as such.",
        "Covariance head is trained against 60 s position RMSE, not NLL "
        "(NLL caused variance inflation in lab/models/results/nll_diagnosis/).",
        "IO-VNBD drives scored here are cars; untilted NHC is the wrong model on two-wheelers.",
    ]

    csvs = find_smartphone_csvs()
    if args.files:
        csvs = csvs[: args.files]
    if not csvs:
        limitations.insert(
            0,
            "No real S-*.csv (>1 MB) under data/raw/IO-VNBD — cannot score.",
        )
        return _empty_report(limitations, args.window_s, out_dir)

    onnx_info = probe_coast_onnx()
    print(f"ONNX: loaded={onnx_info.get('loaded')} — {onnx_info.get('reason')}")
    if not onnx_info.get("loaded"):
        limitations.append(str(onnx_info.get("reason")))

    t_load = time.perf_counter()
    prepared: list[tuple[Path, dict[str, Any], np.ndarray, np.ndarray]] = []
    for p in csvs:
        item = _prepare_data(p)
        if item is None:
            print(f"  skip {p.name}: no usable CAN-paired drive")
            continue
        data, gz, fix_changed = item
        prepared.append((p, data, gz, fix_changed))
        print(f"  loaded {data['name']:16s} n={data['_t'].size}")
    print(f"prepared {len(prepared)} CAN-paired drives in {time.perf_counter() - t_load:.1f}s")
    if len(prepared) < 2:
        limitations.append("Fewer than two CAN-paired drives after filtering.")
        return _empty_report(limitations, args.window_s, out_dir)

    paths = [p for p, *_ in prepared]
    training_paths, eval_paths = split_drive_paths(paths, eval_fraction=args.eval_fraction)
    train_names = {p.name for p in training_paths}
    eval_names = {p.name for p in eval_paths}
    print(f"split train={len(training_paths)} eval={len(eval_paths)}")

    TrainWin = tuple[dict[str, Any], int, int, np.ndarray, np.ndarray, np.ndarray]
    train_wins: list[TrainWin] = []
    for p, data, gz, fix_changed in prepared:
        if p.name not in train_names:
            continue
        persist = _hold_speed(data["_v"], fix_changed)
        for i0, i1 in _eligible_windows(data, args.segments, args.window_s):
            if _yaw0_from_truth(data["_cla"], data["_clo"], i0) is None:
                continue
            train_wins.append((data, int(i0), int(i1), gz, fix_changed, persist))
    rng = np.random.default_rng(26168)
    if len(train_wins) > args.train_windows:
        idx = rng.choice(len(train_wins), size=int(args.train_windows), replace=False)
        train_wins = [train_wins[i] for i in sorted(int(j) for j in idx)]
    print(f"training windows used: {len(train_wins)}")
    if len(train_wins) < 4:
        print("ABORT: fewer than 4 training windows")
        return 2

    head = LogVarRHead.zeros(n_hidden=args.n_hidden, rng=rng)

    n_loss_calls = 0

    def _mean_train_rmse(h: LogVarRHead) -> float:
        nonlocal n_loss_calls
        vals: list[float] = []
        for data, i0, i1, gz, fix_changed, persist in train_wins:
            rmse = _window_rmse(data, i0, i1, gz, fix_changed, persist, h)
            if rmse is not None and math.isfinite(rmse):
                vals.append(rmse)
        n_loss_calls += 1
        mean = float(np.mean(vals)) if vals else 1e6
        if n_loss_calls == 1 or n_loss_calls % 8 == 0:
            print(f"    loss eval {n_loss_calls:3d}: mean 60s RMSE {mean:.3f} m")
        return mean

    init_loss = _mean_train_rmse(head)
    print(f"init train mean RMSE: {init_loss:.3f} m")

    # Feature norm from a dry rollout of the untrained head (train windows).
    feat_samples: list[np.ndarray] = []
    for data, i0, i1, gz, fix_changed, persist in train_wins[: min(12, len(train_wins))]:
        yaw0 = _yaw0_from_truth(data["_cla"], data["_clo"], i0)
        if yaw0 is None:
            continue
        sl = slice(i0, i1)
        roll = _ai_fused_track(
            data["_t"][sl],
            data["_lat"][sl],
            data["_lon"][sl],
            data["_acc"][sl],
            gz[sl],
            data["_energy"][sl],
            persist[sl],
            fix_changed[sl],
            float(data["_cla"][i0]),
            float(data["_clo"][i0]),
            yaw0,
            head,
            collect_features=True,
        )
        feat_samples.extend(roll.features_at_gnss)
    mean, scale = fit_feature_norm(feat_samples)
    head.set_feature_norm(mean, scale)

    t_fit = time.perf_counter()
    bias_info = nelder_mead_bias(head, _mean_train_rmse, maxiter=int(args.bias_iters))
    print(
        f"stage2a bias: {bias_info['init_loss']:.3f} -> {bias_info['final_loss']:.3f} m "
        f"({bias_info['method']}, evals={bias_info['n_evals']})"
    )
    spsa_info = spsa_fit(
        head, _mean_train_rmse, iters=int(args.spsa_iters), rng=rng
    )
    print(
        f"stage2b SPSA: {spsa_info['init_loss']:.3f} -> {spsa_info['final_loss']:.3f} m "
        f"evals={spsa_info['n_evals']}"
    )
    final_loss = float(_mean_train_rmse(head))
    print(f"train mean RMSE after fit: {final_loss:.3f} m  ({time.perf_counter() - t_fit:.1f}s)")

    rows: list[dict[str, Any]] = []
    per_file: list[dict[str, Any]] = []
    n_files_used = 0
    for p, data, gz, fix_changed in prepared:
        persist = _hold_speed(data["_v"], fix_changed)
        oracle = _oracle_speed(data["_cv"], persist)
        split = "eval" if p.name in eval_names else "train"
        file_rows: list[dict[str, Any]] = []
        for i0, i1 in _eligible_windows(data, args.segments, args.window_s):
            row = run_window(
                data, int(i0), i1, gz, fix_changed, persist, oracle, head, split=split
            )
            if row is None:
                continue
            row["file"] = data["name"]
            file_rows.append(row)
            rows.append(row)
        if not file_rows:
            continue
        n_files_used += 1

        def _med(key: str) -> float:
            return float(np.median([r["all"][key]["median_m"] for r in file_rows]))

        print(
            f"  {data['name']:16s} {split:5s} n={len(file_rows):2d}  "
            f"gnss={_med('gnss_only'):6.1f}m  ekf={_med('fused'):6.1f}m  "
            f"aiP={_med('ai_fused_persistence'):6.1f}m  "
            f"aiO={_med('ai_fused_oracle_can'):6.1f}m"
        )
        per_file.append(
            {
                "name": data["name"],
                "split": split,
                "n_windows": len(file_rows),
                "med_gnss_m": _med("gnss_only"),
                "med_ins_m": _med("ins_only"),
                "med_fused_m": _med("fused"),
                "med_ai_persist_m": _med("ai_fused_persistence"),
                "med_ai_oracle_m": _med("ai_fused_oracle_can"),
            }
        )

    summary = summarise(rows)
    held_rows = [r for r in rows if r.get("split") == "eval"]
    held_summary = summarise(held_rows)
    limitations.append(
        "All-corpus AI numbers include training-drive windows (R was fit there). "
        "Use the held-out table for the leakage-safe claim."
    )

    report = {
        "coupling": "loosely-coupled position-domain + learned diag(R)",
        "tight_coupling_possible": False,
        "precedent": {
            "paper": "Brossard, Barrau, Bonnabel 2020 AI-IMU Dead-Reckoning",
            "code": "https://github.com/mbrossar/ai-imu-dr",
            "license": "MIT",
            "what_we_copied": "learn diag(R) of pseudo-measurements; do not learn the motion",
        },
        "window_s": args.window_s,
        "degraded_acc_h_m": DEGRADED_ACC_H_M,
        "gyro_cutoff_hz": GYRO_CUTOFF_HZ,
        "n_files": n_files_used,
        "n_candidates_scanned": len(csvs),
        "device": "cpu",
        "speed_mean": "skipped",
        "speed_ablations": {
            "ai_fused_persistence": "hold last unique-fix phone GNSS speed (online)",
            "ai_fused_oracle_can": "CAN indicated vehicle speed (ORACLE; labelled)",
        },
        "coast_onnx": onnx_info,
        "evaluation_protocol": {
            "split_unit": "drive basename",
            "seed": 26168,
            "training_drives": sorted(train_names),
            "evaluation_drives": sorted(eval_names),
            "overlap": sorted(train_names & eval_names),
            "windowing": "same as run_gnss_ins_fusion.py defaults (segments=8, window_s=60, files=all unless capped)",
            "classical_ekf": "reimplemented in-script via run_gnss_ins_fusion._fused_track on the same windows",
        },
        "training": {
            "seed": 26168,
            "objective": "mean 60s ENU RMSE vs CAN (not NLL)",
            "n_train_windows": len(train_wins),
            "n_hidden": args.n_hidden,
            "n_parameters": head.n_parameters(),
            "init_loss": init_loss,
            "final_loss": final_loss,
            "stage2a_bias": bias_info,
            "stage2b_spsa": spsa_info,
            "model": head.to_dict(),
        },
        "summary": summary,
        "held_out_summary": held_summary,
        "limitations": limitations,
        "files": per_file,
        "windows": rows,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(
        json.dumps(report, indent=2, default=float), encoding="utf-8"
    )
    write_summary(out_dir / "summary.md", report)

    print(f"\nfiles={n_files_used} windows={summary.get('n_windows', 0)}")
    if summary.get("n_windows"):
        a, d = summary["all"], summary["degraded"]
        print(
            f"ALL      gnss={a['gnss_only']['median_of_medians_m']:.2f}  "
            f"ekf={a['fused']['median_of_medians_m']:.2f}  "
            f"aiP={a['ai_fused_persistence']['median_of_medians_m']:.2f}  "
            f"aiO={a['ai_fused_oracle_can']['median_of_medians_m']:.2f}  "
            f"aiP_vs_gnss={a['ai_persistence_vs_gnss_x']:.2f}×  "
            f"aiP_vs_ekf={a['fused_vs_classical_ekf']:.2f}×"
        )
        print(
            f"DEGRADED gnss={d['gnss_only']['median_of_medians_m']:.2f}  "
            f"ekf={d['fused']['median_of_medians_m']:.2f}  "
            f"aiP={d['ai_fused_persistence']['median_of_medians_m']:.2f}  "
            f"aiP_vs_ekf={d['fused_vs_classical_ekf']:.2f}×"
        )
        if held_summary.get("n_windows"):
            ha = held_summary["all"]
            print(
                f"HELD-OUT n={held_summary['n_windows']}  "
                f"aiP_vs_gnss={ha['ai_persistence_vs_gnss_x']:.2f}×  "
                f"aiP_vs_ekf={ha['fused_vs_classical_ekf']:.2f}×"
            )
    print(f"wrote {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
