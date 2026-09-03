"""F1–F2: textbook roll/yaw kinematics (Titterton & Weston).

Do not claim discovery. Claim: car-derived DR uses ψ̇ ≈ ω_z and is therefore
wrong by cos(lean), exactly during turns.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib.pyplot as plt
import numpy as np

from kinematics import DEG, body_rates, yaw_rate_from_lean
from util import save_json, save_plot


NAME = "exp1_f1_f2_kinematics"
BIBLE = {
    "omega_body": " [phidot, psidot*sin(phi), psidot*cos(phi)]",
    "exact_psidot": "wy*sin(phi) + wz*cos(phi)",
    "claim": "textbook kinematics — application, not discovery",
}


def run(seed: int = 26168) -> dict:
    psi_dot = 0.6  # rad/s, a brisk scooter turn
    phi = np.linspace(-50 * DEG, 50 * DEG, 401)
    wx, wy, wz = body_rates(phi, 0.0, psi_dot)
    recovered = yaw_rate_from_lean(wy, wz, phi)
    car = wz.copy()
    residual = recovered - psi_dot
    max_resid = float(np.max(np.abs(residual)))

    # Cosine error of the car-style model.
    car_rel = 1.0 - np.cos(phi)

    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.2))
    ax = axes[0]
    ax.plot(phi / DEG, wy, label=r"$\omega_y = \dot\psi\sin\phi$", color="#1f4e79")
    ax.plot(phi / DEG, wz, label=r"$\omega_z = \dot\psi\cos\phi$", color="#c45911")
    ax.plot(phi / DEG, np.full_like(phi, psi_dot), "--", color="#7f7f7f", label=r"true $\dot\psi$")
    ax.set_xlabel("lean φ (deg)")
    ax.set_ylabel("rad/s")
    ax.set_title("F1  ·  ω_body at ψ̇ = 0.6 rad/s")
    ax.legend(loc="upper right")

    ax = axes[1]
    ax.plot(phi / DEG, recovered, color="#2e7d32", label="F2  ψ̇ = ωy sinφ + ωz cosφ")
    ax.plot(phi / DEG, car, color="#c45911", label="car-style  ψ̇ ≈ ωz")
    ax.set_xlabel("lean φ (deg)")
    ax.set_ylabel("estimated yaw rate (rad/s)")
    ax.set_title("F2  ·  exact correction vs car-style")
    ax.legend(loc="lower left")
    fig.suptitle("Textbook kinematics (Titterton & Weston) — not a discovery", y=1.02)
    save_plot(fig, NAME)

    # Spot-check the identity at a few leans.
    checks = {}
    for d in (0.0, 11.0, 26.0, 34.0, 45.0):
        p = d * DEG
        _, wy_i, wz_i = body_rates(p, 0.15, psi_dot)
        rec = float(yaw_rate_from_lean(wy_i, wz_i, p))
        checks[f"phi_{int(d)}_deg"] = {
            "wy": float(wy_i),
            "wz": float(wz_i),
            "F2_psidot": rec,
            "true_psidot": psi_dot,
            "car_psidot": float(wz_i),
            "car_rel_error": float(1.0 - np.cos(p)),
        }

    payload = {
        "finding": "F1-F2",
        "name": NAME,
        "bible": BIBLE,
        "max_F2_residual": max_resid,
        "F2_holds": max_resid < 1e-12,
        "car_style_error_at_45deg": float(1.0 - np.cos(45 * DEG)),
        "checks": checks,
        "note": "ω_body and the F2 inversion are textbook. The contribution is applying them to two-wheeler smartphone DR.",
        "seed": seed,
    }
    save_json(NAME, payload)
    return payload


if __name__ == "__main__":
    out = run()
    print(f"F1/F2  max F2 residual {out['max_F2_residual']:.3e}  car-style @45° {out['car_style_error_at_45deg']*100:.1f}%")
