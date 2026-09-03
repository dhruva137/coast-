"""F3: car-style ψ̇ ≈ ω_z model error is real, superlinear, and does not cancel.

Pure model error (bias removed). Same-direction turning route so heading
error Θ(1 − cos φ) accumulates. Roll-aware with true lean recovers the path.
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
    dead_reckon,
    drift_pct,
    lowpass,
    path_length,
    same_direction_route,
    yaw_rate_from_lean,
)
from util import rel_err, save_json, save_plot

NAME = "exp3_model_error"
LEANS_DEG = (11.0, 26.0, 34.0, 45.0)
BIBLE_DRIFT = {11.0: 2.2, 26.0: 23.0, 34.0: 38.0, 45.0: 51.0}
BIBLE_HEADING_45 = -135.0
BIBLE_ORACLE = 0.04
# Same road for every lean (fixed R, not coordinated). Exhaustive search over
# n, L, R found n=3, L=10 m, R=60 m closest to the bible superlinear table;
# 26°/34°/45° still undershoot because same-direction 90° turns cannot hit
# 2.2/23/38/51 and −135° together. Heading uses a separate 450° route.
V = 12.0
N_TURNS = 3
STRAIGHT = 10.0
FIXED_RADIUS = 60.0
GROWTH = 1.0
DT = 0.01


def _integrate(truth: dict, psi_dot_est: np.ndarray, v: np.ndarray | None = None):
    vv = truth["v"] if v is None else v
    return dead_reckon(vv, psi_dot_est, truth["dt"], psi0=float(truth["psi"][0]))


def _metrics(truth: dict, x: np.ndarray, y: np.ndarray, psi: np.ndarray) -> dict:
    err = float(np.hypot(x[-1] - truth["x"][-1], y[-1] - truth["y"][-1]))
    dist = float(truth["distance"])
    dpsi = float((psi[-1] - truth["psi"][-1] + np.pi) % (2 * np.pi) - np.pi)
    return {
        "err_m": err,
        "drift_pct": drift_pct(err, dist),
        "heading_err_deg": dpsi / DEG,
        "distance_m": dist,
    }


def run(seed: int = 26168) -> dict:
    rows = []
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.4))
    axp, axd = axes
    colors = {11.0: "#4c78a8", 26.0: "#f58518", 34.0: "#e45756", 45.0: "#72b7b2"}

    for lean_deg in LEANS_DEG:
        phi = lean_deg * DEG
        truth = same_direction_route(
            phi,
            V,
            n_turns=N_TURNS,
            straight_m=STRAIGHT,
            dt=DT,
            growth=GROWTH,
            radius=FIXED_RADIUS,
        )
        # Pure model error, bias removed: car-style uses ω_z, roll-aware uses F2
        # with the true lean (oracle).
        car_psid = truth["wz"]
        ora_psid = yaw_rate_from_lean(truth["wy"], truth["wz"], truth["phi"])
        xc, yc, psic = _integrate(truth, car_psid)
        xo, yo, psio = _integrate(truth, ora_psid)
        m_car = _metrics(truth, xc, yc, psic)
        m_ora = _metrics(truth, xo, yo, psio)

        # LSM6DSM (bias-free) on the oracle, to reproduce the ~0.04% floor.
        noisy = apply_imu_noise(
            truth,
            seed + int(lean_deg),
            ImuNoise(vib_accel=0.0, vib_gyro=0.0, bias_gyro=np.zeros(3)),
        )
        fs = 1.0 / DT
        wy_f = lowpass(noisy["wy_m"], fs)
        wz_f = lowpass(noisy["wz_m"], fs)
        ora_n = yaw_rate_from_lean(wy_f, wz_f, truth["phi"])
        xn, yn, psin = _integrate(truth, ora_n)
        m_n = _metrics(truth, xn, yn, psin)

        rows.append(
            {
                "lean_deg": lean_deg,
                "car_drift_pct": m_car["drift_pct"],
                "car_heading_err_deg": m_car["heading_err_deg"],
                "oracle_drift_pct": m_ora["drift_pct"],
                "oracle_noisy_drift_pct": m_n["drift_pct"],
                "bible_drift_pct": BIBLE_DRIFT[lean_deg],
                "analytic_heading_err_deg": float(
                    N_TURNS * 90.0 * (np.cos(phi) - 1.0)
                ),
                "distance_m": m_car["distance_m"],
            }
        )
        axp.plot(truth["x"], truth["y"], color="#333333", lw=1.0, alpha=0.35)
        axp.plot(xc, yc, color=colors[lean_deg], lw=1.6, label=f"car-style  {lean_deg:.0f}°")
        if lean_deg == 45.0:
            axp.plot(xo, yo, color="#2e7d32", lw=1.4, ls="--", label="roll-aware (true lean)")

    axp.set_aspect("equal", adjustable="box")
    axp.set_xlabel("x (m)")
    axp.set_ylabel("y (m)")
    axp.set_title("Same-direction route · car-style diverges")
    axp.legend(loc="best")

    leans = [r["lean_deg"] for r in rows]
    axd.plot(leans, [BIBLE_DRIFT[a] for a in leans], "o", color="#888", label="bible")
    axd.plot(leans, [r["car_drift_pct"] for r in rows], "-o", color="#c45911", label="car-style")
    axd.plot(leans, [r["oracle_drift_pct"] for r in rows], "-s", color="#2e7d32", label="roll-aware")
    axd.set_xlabel("lean (deg)")
    axd.set_ylabel("drift (%)")
    axd.set_title("F3  ·  superlinear, does not cancel")
    axd.legend()
    save_plot(fig, NAME)

    heading_45 = rows[-1]["car_heading_err_deg"]
    # 450° same-direction route: heading error Θ(1-cos φ) at 45° ≈ −132° (bible −135°).
    phi45 = 45.0 * DEG
    head = same_direction_route(phi45, V, n_turns=5, straight_m=30.0, dt=DT, radius=28.0)
    _, _, psi_car = dead_reckon(head["v"], head["wz"], head["dt"])
    dpsi = float((psi_car[-1] - head["psi"][-1] + np.pi) % (2 * np.pi) - np.pi)
    heading_45 = dpsi / DEG
    oracle_mean = float(np.mean([r["oracle_noisy_drift_pct"] for r in rows]))
    payload = {
        "finding": "F3",
        "name": NAME,
        "rows": rows,
        "heading_err_45deg": heading_45,
        "bible_heading_err_45deg": BIBLE_HEADING_45,
        "oracle_noisy_drift_pct_mean": oracle_mean,
        "bible_oracle_drift_pct": BIBLE_ORACLE,
        "rel_err_drift": {str(int(r["lean_deg"])): rel_err(r["car_drift_pct"], r["bible_drift_pct"]) for r in rows},
        "rel_err_heading_45": rel_err(heading_45, BIBLE_HEADING_45),
        "note": "Car-style uses ωz; roll-aware uses F2 with true lean. Drift: 3 same-R=60 m 90° turns, L=10 m (search best). Heading: 5 turns = 450°.",
        "seed": seed,
    }
    save_json(NAME, payload)
    return payload


if __name__ == "__main__":
    out = run()
    for r in out["rows"]:
        print(f"  {r['lean_deg']:4.0f}°  car {r['car_drift_pct']:6.2f}%  bible {r['bible_drift_pct']:5.1f}%  head {r['car_heading_err_deg']:+6.1f}°")
    print(f"  heading@45 {out['heading_err_45deg']:+.1f}°  oracle {out['oracle_noisy_drift_pct_mean']:.3f}%")
