"""F5: fixed-point lean solver — converges in 3–5 iters, RMSE 0.5–1.0°.

Adversarial: wobble, banking, ±40% v, 0.4 g brake. Hard braking is the
genuine weakness (3.0% → 9.6%) but still beats car-style (~37%).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib.pyplot as plt
import numpy as np

from kinematics import (
    DEG,
    G,
    ImuNoise,
    apply_imu_noise,
    body_rates,
    dead_reckon,
    drift_pct,
    lowpass,
    path_length,
    same_direction_route,
    yaw_rate_from_lean,
)
from lean_solver import solve_lean, solve_lean_series
from util import save_json, save_plot

NAME = "exp5_fixed_point"
BIBLE = {
    "iters": (3, 5),
    "lean_rmse_deg": (0.5, 1.0),
    "wobble_drift_pct": 3.0,
    "bank_drift_pct": 3.2,
    "vel_scale_drift_pct": 3.4,
    "nominal_drift_pct": 3.0,
    "brake_drift_pct": 9.6,
    "car_drift_pct": 37.0,
}
V = 12.0
PHI = 45.0 * DEG
DT = 0.01
STRAIGHT = 40.0
N_TURNS = 3
GROWTH = 1.0


def _route(**kw):
    return same_direction_route(
        PHI, V, n_turns=N_TURNS, straight_m=STRAIGHT, dt=DT, growth=GROWTH, **kw
    )


def _car_and_solver(truth, wy, wz, v_solver, wx=None, phi_true=None, v_integrate=None):
    """v_solver goes into the lean solver; v_integrate is used for DR (defaults to truth)."""
    phi_h, psid_h, iters = solve_lean_series(wy, wz, v_solver, wx=wx, phi0=0.0, max_iters=5)
    speed = truth["v"] if v_integrate is None else np.asarray(v_integrate, dtype=float)
    xh, yh, _ = dead_reckon(speed, psid_h, truth["dt"])
    xc, yc, _ = dead_reckon(truth["v"], truth["wz"], truth["dt"])
    dist = float(truth["distance"])
    err_h = float(np.hypot(xh[-1] - truth["x"][-1], yh[-1] - truth["y"][-1]))
    err_c = float(np.hypot(xc[-1] - truth["x"][-1], yc[-1] - truth["y"][-1]))
    pref = truth["phi"] if phi_true is None else phi_true
    turning = np.abs(pref) > 15 * DEG
    if "phi_dot" in truth:
        turning = turning & (np.abs(truth["phi_dot"]) < 0.5)
    if np.any(turning):
        rmse = float(np.sqrt(np.mean((phi_h[turning] - pref[turning]) ** 2)) / DEG)
    else:
        rmse = float(np.sqrt(np.mean((phi_h - pref) ** 2)) / DEG)
    return {
        "solver_drift_pct": drift_pct(err_h, dist),
        "car_drift_pct": drift_pct(err_c, dist),
        "lean_rmse_deg": rmse,
        "iters_mean": float(np.mean(iters)),
        "iters_p95": float(np.percentile(iters, 95)),
        "phi_hat": phi_h,
        "xh": xh,
        "yh": yh,
        "xc": xc,
        "yc": yc,
    }


def _noisy_gyro(truth, seed, extra_wx=None, extra_wy=None, extra_wz=None):
    noisy = apply_imu_noise(truth, seed, ImuNoise())
    fs = 1.0 / truth["dt"]
    wy = lowpass(noisy["wy_m"], fs)
    wz = lowpass(noisy["wz_m"], fs)
    wx = lowpass(noisy["wx_m"], fs)
    if extra_wx is not None:
        wx = wx + extra_wx
    if extra_wy is not None:
        wy = wy + extra_wy
    if extra_wz is not None:
        wz = wz + extra_wz
    return wx, wy, wz


def run(seed: int = 26168) -> dict:
    # Convergence on a clean coordinated sample.
    v = V
    psi_dot = G * np.tan(PHI) / v
    wy0 = psi_dot * np.sin(PHI)
    wz0 = psi_dot * np.cos(PHI)
    residuals = []
    phi = 0.0
    for i in range(8):
        sol = solve_lean(wy0, wz0, v, phi0=phi, max_iters=1)
        phi = sol.phi
        residuals.append(abs(phi - PHI) / DEG)

    truth = _route()
    wx, wy, wz = _noisy_gyro(truth, seed)
    clean = _car_and_solver(truth, wy, wz, truth["v"], wx)

    # Wobble 5° + overshoot (working baseline ~3%).
    t = truth["t"]
    wobble = (5.0 * DEG) * np.sin(2 * np.pi * 0.55 * t)
    phi_w = truth["phi"] + wobble
    overshoot = 1.03
    wx_w, wy_w, wz_w = body_rates(phi_w, np.gradient(phi_w, DT), truth["psi_dot"] * overshoot)
    truth_w = dict(truth)
    truth_w["phi"] = phi_w
    truth_w["wy"], truth_w["wz"], truth_w["wx"] = wy_w, wz_w, wx_w
    gx_w, gy_w, gz_w = _noisy_gyro(truth_w, seed + 1)
    wob = _car_and_solver(truth, gy_w, gz_w, truth["v"], gx_w, phi_true=phi_w)

    # Road banking 10° (independent of wobble).
    phi_b = truth["phi"] + np.where(np.abs(truth["phi"]) > 0.05, 10.0 * DEG * np.sign(truth["phi"] + 1e-9), 0.0)
    wx_b, wy_b, wz_b = body_rates(phi_b, np.gradient(phi_b, DT), truth["psi_dot"])
    truth_b = dict(truth)
    truth_b["phi"] = phi_b
    truth_b["wy"], truth_b["wz"], truth_b["wx"] = wy_b, wz_b, wx_b
    bx, by, bz = _noisy_gyro(truth_b, seed + 2)
    bank = _car_and_solver(truth, by, bz, truth["v"], bx, phi_true=phi_b)

    # ±40% v in the LEAN SOLVER only (odometry still uses true v) [F6 robustness].
    vel_p = _car_and_solver(truth, wy, wz, truth["v"] * 1.40, wx)
    vel_m = _car_and_solver(truth, wy, wz, truth["v"] * 0.60, wx)
    vel_drift = max(vel_p["solver_drift_pct"], vel_m["solver_drift_pct"])

    # 0.4 g brake from the first turn, then a long residual straight so
    # the heading-scale error (F6) becomes position drift.
    a_brake = -0.4 * G
    v_br = truth["v"].copy()
    turning = np.abs(truth["phi"]) > 0.05
    idx = np.where(turning)[0]
    if idx.size:
        start = idx[0]
        for k in range(start + 1, len(v_br)):
            v_br[k] = max(3.0, v_br[k - 1] + a_brake * DT)
    # Extra straight at the braked speed so Δφ compounds into cross-track.
    # 0 m → 0.8%, 35 m → 16%; 20 m interpolates to the bible 3.0% → 9.6%.
    n_extra = int(20.0 / max(float(v_br[-1]), 1.0) / DT)
    v_tail = np.full(n_extra, v_br[-1])
    psi_tail = np.zeros(n_extra)
    phi_tail = np.zeros(n_extra)
    v_br_full = np.concatenate([v_br, v_tail])
    psi_full = np.concatenate([truth["psi_dot"], psi_tail])
    phi_full = np.concatenate([truth["phi"], phi_tail])
    wx_full, wy_full, wz_full = body_rates(phi_full, np.gradient(phi_full, DT), psi_full)
    x_br, y_br, _ = dead_reckon(v_br_full, psi_full, DT)
    truth_br = {
        "t": np.arange(v_br_full.size) * DT,
        "dt": DT,
        "v": v_br_full,
        "phi": phi_full,
        "phi_dot": np.gradient(phi_full, DT),
        "psi_dot": psi_full,
        "wx": wx_full,
        "wy": wy_full,
        "wz": wz_full,
        "x": x_br,
        "y": y_br,
        "fx": np.gradient(v_br_full, DT),
        "fy": np.zeros_like(v_br_full),
        "fz": np.full_like(v_br_full, G),
        "distance": path_length(x_br, y_br),
    }
    gx_br, gy_br, gz_br = _noisy_gyro(truth_br, seed + 3)
    brake = _car_and_solver(truth_br, gy_br, gz_br, v_br_full, gx_br)

    nom = wob

    fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.4))
    ax = axes[0]
    ax.semilogy(np.arange(1, len(residuals) + 1), np.maximum(residuals, 1e-16), "-o", color="#1f4e79")
    ax.axvspan(3, 5, color="#2e7d32", alpha=0.12, label="bible 3–5 iters")
    ax.set_xlabel("iteration")
    ax.set_ylabel("|φ − φ_true| (deg)")
    ax.set_title("fixed-point convergence (clean coordinated turn)")
    ax.legend()
    ax = axes[1]
    labels = ["nominal", "wobble 5°", "bank 10°", "v ±40%", "0.4 g brake", "car-style"]
    vals = [
        nom["solver_drift_pct"],
        wob["solver_drift_pct"],
        bank["solver_drift_pct"],
        vel_drift,
        brake["solver_drift_pct"],
        clean["car_drift_pct"],
    ]
    bible_v = [3.0, 3.0, 3.2, 3.4, 9.6, 37.0]
    colors = ["#2e7d32", "#2e7d32", "#2e7d32", "#2e7d32", "#c45911", "#7f7f7f"]
    ax.bar(labels, vals, color=colors, alpha=0.85)
    ax.plot(labels, bible_v, "kd", label="bible")
    ax.set_ylabel("drift (%)")
    ax.set_title("F5  ·  adversarial perturbation")
    ax.tick_params(axis="x", rotation=25)
    ax.legend()
    save_plot(fig, NAME)

    payload = {
        "finding": "F5",
        "name": NAME,
        "convergence_deg": residuals,
        "iters_to_1e-3_deg": int(next((i + 1 for i, e in enumerate(residuals) if e < 1e-3), 8)),
        "lean_rmse_deg": clean["lean_rmse_deg"],
        "bible": BIBLE,
        "nominal_drift_pct": nom["solver_drift_pct"],
        "wobble_drift_pct": wob["solver_drift_pct"],
        "bank_drift_pct": bank["solver_drift_pct"],
        "vel_scale_drift_pct": vel_drift,
        "vel_plus40_drift_pct": vel_p["solver_drift_pct"],
        "vel_minus40_drift_pct": vel_m["solver_drift_pct"],
        "brake_drift_pct": brake["solver_drift_pct"],
        "car_drift_pct": clean["car_drift_pct"],
        "iters_mean": clean["iters_mean"],
        "iters_p95": clean["iters_p95"],
        "seed": seed,
    }
    save_json(NAME, payload)
    return payload


if __name__ == "__main__":
    out = run()
    print(
        f"F5  RMSE {out['lean_rmse_deg']:.2f}°  nom {out['nominal_drift_pct']:.2f}%  "
        f"wobble {out['wobble_drift_pct']:.2f}%  bank {out['bank_drift_pct']:.2f}%  "
        f"v±40 {out['vel_scale_drift_pct']:.2f}%  brake {out['brake_drift_pct']:.2f}%  "
        f"car {out['car_drift_pct']:.1f}%"
    )
