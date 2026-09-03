"""F6: ψ̇_est = ψ̇ cos(φ − φ̂). Scale error depends on lean ERROR, not lean angle.

Verified to ~2.2×10⁻¹⁶. Car-style at 40° lean: 23.4%. Ours with a sloppy
10° lean estimate: 1.5%. You need lean only to ~10°; the solver delivers 0.5–1°.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib.pyplot as plt
import numpy as np

from kinematics import DEG, body_rates, yaw_rate_from_lean
from lean_solver import heading_rate_scale_error
from util import save_json, save_plot

NAME = "exp6_cos_dphi"
BIBLE = {
    "identity_residual": 2.2e-16,
    "car_40deg_pct": 23.4,
    "ours_10deg_err_pct": 1.5,
}


def run(seed: int = 26168) -> dict:
    psi_dot = 0.55
    phi = np.linspace(-50 * DEG, 50 * DEG, 801)
    dphi = np.linspace(-40 * DEG, 40 * DEG, 801)

    # Grid: true lean vs estimated lean.
    phi_t = 40.0 * DEG
    wx, wy, wz = body_rates(phi_t, 0.0, psi_dot)
    phi_hat = phi_t + dphi
    est = yaw_rate_from_lean(wy, wz, phi_hat)
    ratio = est / psi_dot
    analytic = np.cos(dphi)
    resid = ratio - analytic
    max_resid = float(np.max(np.abs(resid)))
    # machine epsilon around cos: typically 1–3 ulp
    median_resid = float(np.median(np.abs(resid)))

    car_40 = float(1.0 - np.cos(40.0 * DEG))
    ours_10 = float(1.0 - np.cos(10.0 * DEG))

    # Sweep true lean: car-style error vs 10° lean-error solver.
    phi_sweep = np.linspace(0.0, 50.0 * DEG, 251)
    car_err = 1.0 - np.cos(phi_sweep)
    ours_err = np.full_like(phi_sweep, 1.0 - np.cos(10.0 * DEG))

    fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.3))
    ax = axes[0]
    ax.plot(dphi / DEG, ratio, color="#1f4e79", lw=2.0, label=r"simulated $\dot\psi_{\mathrm{est}}/\dot\psi$")
    ax.plot(dphi / DEG, analytic, "--", color="#c45911", lw=1.4, label=r"$\cos(\phi-\hat\phi)$")
    ax.set_xlabel(r"lean error  $\phi-\hat\phi$  (deg)")
    ax.set_ylabel("yaw-rate scale")
    ax.set_title(f"F6 identity  ·  max |resid| = {max_resid:.2e}")
    ax.legend()
    ax = axes[1]
    ax.plot(phi_sweep / DEG, 100 * car_err, color="#c45911", lw=2.0, label="car-style (error = lean)")
    ax.plot(phi_sweep / DEG, 100 * ours_err, color="#2e7d32", lw=2.0, label="ours with 10° lean error")
    ax.axhline(23.4, color="#c45911", ls=":", lw=0.8)
    ax.axhline(1.5, color="#2e7d32", ls=":", lw=0.8)
    ax.set_xlabel("true lean (deg)")
    ax.set_ylabel("heading-rate error (%)")
    ax.set_title("error depends on Δφ, not φ")
    ax.legend()
    save_plot(fig, NAME)

    payload = {
        "finding": "F6",
        "name": NAME,
        "max_identity_residual": max_resid,
        "median_identity_residual": median_resid,
        "bible_identity_residual": BIBLE["identity_residual"],
        "identity_ok_1e15": max_resid < 1e-15,
        "car_40deg_pct": 100.0 * car_40,
        "bible_car_40deg_pct": BIBLE["car_40deg_pct"],
        "ours_10deg_err_pct": 100.0 * ours_10,
        "bible_ours_10deg_err_pct": BIBLE["ours_10deg_err_pct"],
        "closed_form_check": float(heading_rate_scale_error(10 * DEG)),
        "seed": seed,
    }
    save_json(NAME, payload)
    return payload


if __name__ == "__main__":
    out = run()
    print(
        f"F6  resid {out['max_identity_residual']:.3e}  "
        f"car@40° {out['car_40deg_pct']:.1f}%  ours 10° err {out['ours_10deg_err_pct']:.1f}%"
    )
