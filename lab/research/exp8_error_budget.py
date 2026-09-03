"""F8: heading, not speed, is the binding constraint.

Equal-effort at 300 m: 1% speed → 3.0 m; 1% heading (3.6°) → 18.9 m;
heading is 6.3× more damaging. Table rows use the same 300 m equal-effort
geometry; drift is vs a 125 s / 1.327 km reference outage (the gyro-bias
duration in the bible).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib.pyplot as plt
import numpy as np

from kinematics import DEG, G, dead_reckon, drift_pct
from util import save_json, save_plot

NAME = "exp8_error_budget"
D_EQ = 300.0  # equal-effort baseline (m)
V = 10.619048  # m/s  so that 125 s × v = 1327.381 m
T_BIAS = 125.0
D_REF = V * T_BIAS  # 1327.38 m  → 15.0/1327.38 = 1.13%
BIBLE = {
    "vel_m": 15.0,
    "vel_pct": 1.13,
    "att_m": 52.3,
    "att_pct": 3.94,
    "lean_m": 84.9,
    "lean_pct": 6.40,
    "gyro_m": 188.5,
    "gyro_pct": 14.20,
    "speed_1pct_m": 3.0,
    "heading_1pct_m": 18.9,
    "heading_vs_speed": 6.3,
}


def _straight(v, psi_dot, dt, n, psi0=0.0):
    vv = np.full(n, v)
    wd = np.full(n, psi_dot) if np.isscalar(psi_dot) else psi_dot
    return dead_reckon(vv, wd, dt, psi0=psi0)


def run(seed: int = 26168) -> dict:
    dt = 0.01
    n_eq = int(round(D_EQ / V / dt))
    t_eq = n_eq * dt

    # Truth: 300 m straight.
    xt, yt, psit = _straight(V, 0.0, dt, n_eq)
    dist_eq = float(np.hypot(xt[-1] - xt[0], yt[-1] - yt[0]))

    # 1% and 5% speed scale (AVNet ~0.5 m/s ≈ 5% at 10 m/s).
    x1, y1, _ = _straight(V * 1.01, 0.0, dt, n_eq)
    x5, y5, _ = _straight(V * 1.05, 0.0, dt, n_eq)
    speed_1pct_m = float(np.hypot(x1[-1] - xt[-1], y1[-1] - yt[-1]))
    vel_m = float(np.hypot(x5[-1] - xt[-1], y5[-1] - yt[-1]))

    # 1% heading = 3.6° constant offset; 10° AVNet attitude.
    xh, yh, _ = _straight(V, 0.0, dt, n_eq, psi0=3.6 * DEG)
    xa, ya, _ = _straight(V, 0.0, dt, n_eq, psi0=10.0 * DEG)
    heading_1pct_m = float(np.hypot(xh[-1] - xt[-1], yh[-1] - yt[-1]))
    att_m = float(np.hypot(xa[-1] - xt[-1], ya[-1] - yt[-1]))

    # cos(lean) at 34°: 90° coordinated turn then the remaining 300 m straight
    # so the heading-scale error is converted into cross-track (F3 mechanism).
    phi = 34.0 * DEG
    R = V**2 / (G * np.tan(phi))
    psi_dot = V / R
    n_arc = int(round((0.5 * np.pi) / psi_dot / dt))
    n_str = n_eq
    v_arc = np.full(n_arc + n_str, V)
    w_true = np.concatenate([np.full(n_arc, psi_dot), np.zeros(n_str)])
    w_car = np.concatenate([np.full(n_arc, psi_dot * np.cos(phi)), np.zeros(n_str)])
    xlt, ylt, _ = dead_reckon(v_arc, w_true, dt)
    xlc, ylc, _ = dead_reckon(v_arc, w_car, dt)
    lean_m = float(np.hypot(xlc[-1] - xlt[-1], ylc[-1] - ylt[-1]))

    # Gyro bias 0.3 °/s accumulated over 125 s, applied as the equivalent
    # heading offset on the equal-effort 300 m (error-budget static equivalent).
    # Also integrate the actual ramp on 125 s for the figure.
    bias = 0.3 * DEG  # rad/s
    n_g = int(round(T_BIAS / dt))
    w_g = np.full(n_g, bias)
    xgt, ygt, _ = _straight(V, 0.0, dt, n_g)
    xgg, ygg, _ = dead_reckon(np.full(n_g, V), w_g, dt)
    gyro_ramp_m = float(np.hypot(xgg[-1] - xgt[-1], ygg[-1] - ygt[-1]))
    xgs, ygs, _ = _straight(V, 0.0, dt, n_eq, psi0=bias * T_BIAS)
    gyro_m = float(np.hypot(xgs[-1] - xt[-1], ygs[-1] - yt[-1]))

    heading_vs_speed = heading_1pct_m / max(speed_1pct_m, 1e-12)

    rows = [
        {
            "source": "AVNet velocity error (0.5 m/s ≈ 5%)",
            "position_m": vel_m,
            "drift_pct": drift_pct(vel_m, D_REF),
            "bible_m": BIBLE["vel_m"],
            "bible_pct": BIBLE["vel_pct"],
        },
        {
            "source": "AVNet attitude error (~10°)",
            "position_m": att_m,
            "drift_pct": drift_pct(att_m, D_REF),
            "bible_m": BIBLE["att_m"],
            "bible_pct": BIBLE["att_pct"],
        },
        {
            "source": "cos(lean) error at 34° lean",
            "position_m": lean_m,
            "drift_pct": drift_pct(lean_m, D_REF),
            "bible_m": BIBLE["lean_m"],
            "bible_pct": BIBLE["lean_pct"],
        },
        {
            "source": "Phone gyro bias 0.3°/s over 125 s",
            "position_m": gyro_m,
            "drift_pct": drift_pct(gyro_m, D_REF),
            "bible_m": BIBLE["gyro_m"],
            "bible_pct": BIBLE["gyro_pct"],
            "ramp_integrated_m": gyro_ramp_m,
        },
    ]

    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.4))
    ax = axes[0]
    labs = ["vel 5%", "att 10°", "cos(lean) 34°", "gyro 0.3°/s"]
    ax.bar(np.arange(4) - 0.18, [r["position_m"] for r in rows], 0.36, color="#1f4e79", label="simulated")
    ax.bar(np.arange(4) + 0.18, [r["bible_m"] for r in rows], 0.36, color="#c45911", alpha=0.7, label="bible")
    ax.set_xticks(np.arange(4), labs)
    ax.set_ylabel("position error (m)")
    ax.set_title(f"F8  ·  equal-effort {D_EQ:.0f} m")
    ax.legend()
    ax = axes[1]
    ax.bar([0, 1], [speed_1pct_m, heading_1pct_m], color=["#2e7d32", "#c45911"])
    ax.set_xticks([0, 1], ["1% speed", "1% heading (3.6°)"])
    ax.set_ylabel("position error (m)")
    ax.set_title(f"heading is {heading_vs_speed:.1f}× more damaging")
    save_plot(fig, NAME)

    payload = {
        "finding": "F8",
        "name": NAME,
        "D_equal_m": D_EQ,
        "D_ref_m": D_REF,
        "V_mps": V,
        "T_bias_s": T_BIAS,
        "rows": rows,
        "speed_1pct_m": speed_1pct_m,
        "heading_1pct_m": heading_1pct_m,
        "heading_vs_speed": heading_vs_speed,
        "bible": BIBLE,
        "seed": seed,
    }
    save_json(NAME, payload)
    return payload


if __name__ == "__main__":
    out = run()
    print(f"F8  1% speed {out['speed_1pct_m']:.2f} m  1% heading {out['heading_1pct_m']:.2f} m  "
          f"ratio {out['heading_vs_speed']:.2f}×")
    for r in out["rows"]:
        print(f"  {r['source'][:40]:40s}  {r['position_m']:7.2f} m  {r['drift_pct']:6.2f}%")
