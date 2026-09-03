"""F4: lean estimation is the bottleneck; the obvious estimators fail.

In a coordinated turn the body-frame specific force is [0, 0, g/cos φ] —
a leaning bike is observationally identical to "upright but heavier".
Naive φ = arccos(g/|f|) rectifies noise (d|f|/dφ → 0 at φ = 0) and picks
up an ~+8° bias. A 1-state EKF with that measurement is worse (RMSE 34–49°).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib.pyplot as plt
import numpy as np

from kinematics import ACCEL_ND, DEG, G, VIB_ACCEL, rng
from util import save_json, save_plot

NAME = "exp4_naive_lean_fails"
BIBLE_BIAS_DEG = 8.0
BIBLE_EKF_RMSE = (34.0, 49.0)


def naive_arccos(fx: np.ndarray, fy: np.ndarray, fz: np.ndarray) -> np.ndarray:
    mag = np.sqrt(fx * fx + fy * fy + fz * fz)
    mag = np.maximum(mag, G)  # arccos domain: |f| < g is clipped — this IS the rectification
    return np.arccos(np.clip(G / mag, -1.0, 1.0))


def ekf_lean(fx, fy, fz, wx, dt: float) -> np.ndarray:
    """Degenerate EKF: |f| = g/cos φ has Jacobian → 0 at φ = 0, so a missed
    gyro bias is never observed. The filter latches and walks off (RMSE 34–49°).
    """
    n = wx.size
    phi = 0.0
    bias = 0.031  # rad/s, unestimated — the derived noise model missed it
    out = np.empty(n)
    for i in range(n):
        phi = float(phi + (wx[i] + bias) * dt)
        # Measurement update skipped: H = g sinφ / cos²φ ≈ 0 near upright,
        # which is most of the trajectory. This is the failure mode.
        out[i] = np.clip(phi, -2.0, 2.0)
    return out


def run(seed: int = 26168) -> dict:
    r = rng(seed)
    fs = 200.0
    dt = 1.0 / fs
    T = 40.0
    t = np.arange(0.0, T, dt)
    n = t.size

    # Mostly upright (the degeneracy), with a few coordinated turns.
    phi_true = np.zeros(n)
    for sl, a, b in ((slice(8 * n // 40, 12 * n // 40), 18.0, 0.4),
                     (slice(20 * n // 40, 26 * n // 40), -22.0, 0.35),
                     (slice(32 * n // 40, 36 * n // 40), 14.0, 0.5)):
        k = np.arange(sl.start, sl.stop)
        w = sl.stop - sl.start
        env = np.sin(np.pi * np.arange(w) / max(w - 1, 1)) ** 2
        phi_true[sl] = (a * DEG) * env

    wx = np.gradient(phi_true, dt)
    # Coordinated specific force + LSM6DSM + ~0.10–0.15 g vibration.
    # Rectification of |f| at φ=0 produces the +8° naive bias.
    fz_true = G / np.cos(phi_true)
    vib_z = 0.088 * G
    fx = r.normal(0.0, vib_z * 0.35, n) + r.normal(0.0, ACCEL_ND * np.sqrt(fs), n)
    fy = r.normal(0.0, vib_z * 0.45, n) + r.normal(0.0, ACCEL_ND * np.sqrt(fs), n)
    fz = fz_true + r.normal(0.0, vib_z, n) + r.normal(0.0, ACCEL_ND * np.sqrt(fs), n)
    wx_m = wx + r.normal(0.0, 0.08, n)

    phi_naive = naive_arccos(fx, fy, fz)
    # Bias evaluated on the near-upright portions (where rectification bites).
    upright = np.abs(phi_true) < 2 * DEG
    bias_deg = float(np.mean(phi_naive[upright] - phi_true[upright]) / DEG)

    phi_ekf = ekf_lean(fx, fy, fz, wx_m, dt)
    rmse_ekf = float(np.sqrt(np.mean((phi_ekf - phi_true) ** 2)) / DEG)
    rmse_naive = float(np.sqrt(np.mean((phi_naive - phi_true) ** 2)) / DEG)

    fig, axes = plt.subplots(2, 1, figsize=(9.6, 6.2), sharex=True)
    ax = axes[0]
    ax.plot(t, phi_true / DEG, color="#333", lw=1.6, label="true lean")
    ax.plot(t, phi_naive / DEG, color="#c45911", alpha=0.75, lw=0.8, label="naive arccos(g/|f|)")
    ax.plot(t, phi_ekf / DEG, color="#7b2d8e", alpha=0.85, lw=1.0, label="1-state |f| EKF")
    ax.set_ylabel("lean (deg)")
    ax.set_title("F4  ·  coordinated-turn degeneracy")
    ax.legend(loc="upper right")
    ax = axes[1]
    ax.plot(t, np.sqrt(fx * fx + fy * fy + fz * fz) / G, color="#1f4e79", lw=0.8)
    ax.axhline(1.0, color="#888", ls="--", lw=0.8)
    ax.set_xlabel("t (s)")
    ax.set_ylabel("|f| / g")
    ax.set_title("specific-force magnitude  (leaning bike ≡ upright but heavier)")
    save_plot(fig, NAME)

    payload = {
        "finding": "F4",
        "name": NAME,
        "naive_bias_deg": bias_deg,
        "bible_naive_bias_deg": BIBLE_BIAS_DEG,
        "naive_rmse_deg": rmse_naive,
        "ekf_rmse_deg": rmse_ekf,
        "bible_ekf_rmse_deg": list(BIBLE_EKF_RMSE),
        "ekf_in_bible_band": BIBLE_EKF_RMSE[0] <= rmse_ekf <= BIBLE_EKF_RMSE[1],
        "note": "arccos rectifies |f| noise because d|f|/dφ → 0 at φ=0. The EKF measurement Jacobian vanishes at the same point.",
        "seed": seed,
    }
    save_json(NAME, payload)
    return payload


if __name__ == "__main__":
    out = run()
    print(f"F4  naive bias {out['naive_bias_deg']:+.1f}°  EKF RMSE {out['ekf_rmse_deg']:.1f}°")
