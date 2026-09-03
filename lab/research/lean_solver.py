"""Fixed-point coordinated-turn lean solver [F5].

Substitute the exact yaw-rate identity [F2] into the coordinated-turn law:

    φ = arctan( v · (ω_y sin φ + ω_z cos φ) / g )

Iterate 3–5 times. Scale error of the resulting yaw rate is cos(φ − φ̂) [F6],
so it depends on lean *error*, not lean *angle*.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from kinematics import G, wrap_pi, yaw_rate_from_lean

MAX_ITERS = 8
TOL = 1e-9
PHI_LIMIT = 1.2  # ~69°, beyond which a street scooter has crashed


@dataclass
class LeanSolution:
    phi: float
    psi_dot: float
    phi_dot: float
    iterations: int
    residual: float
    coordinated: bool


def solve_lean(
    wy: float,
    wz: float,
    speed: float,
    *,
    wx: float = 0.0,
    phi0: float | None = None,
    max_iters: int = MAX_ITERS,
    tol: float = TOL,
) -> LeanSolution:
    """Fixed-point iteration. Returns 0 lean when nearly stopped (unobservable)."""
    v = max(0.0, float(speed))
    gy = float(wy)
    gz = float(wz)
    gx = float(wx)
    if v < 0.4:
        return LeanSolution(0.0, gz, gx, 0, 0.0, False)

    phi = float(np.arctan2(v * gz, G) if phi0 is None else phi0)
    phi = float(np.clip(phi, -PHI_LIMIT, PHI_LIMIT))
    residual = 1.0
    i = 0
    for i in range(1, max_iters + 1):
        psi_dot = float(yaw_rate_from_lean(gy, gz, phi))
        nxt = float(np.arctan2(v * psi_dot, G))
        nxt = float(np.clip(nxt, -PHI_LIMIT, PHI_LIMIT))
        residual = abs(float(wrap_pi(nxt - phi)))
        phi = nxt
        if residual < tol:
            break
    psi_dot = float(yaw_rate_from_lean(gy, gz, phi))
    return LeanSolution(
        phi=phi,
        psi_dot=psi_dot,
        phi_dot=gx,
        iterations=i,
        residual=residual,
        coordinated=abs(v * psi_dot) > 0.15,
    )


def solve_lean_series(
    wy: np.ndarray,
    wz: np.ndarray,
    speed: np.ndarray | float,
    *,
    wx: np.ndarray | None = None,
    phi0: float = 0.0,
    max_iters: int = 5,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Warm-started fixed-point along a trajectory. Returns φ, ψ̇, iters."""
    wy = np.asarray(wy, dtype=float)
    wz = np.asarray(wz, dtype=float)
    n = wy.size
    if np.isscalar(speed):
        speed_arr = np.full(n, float(speed))
    else:
        speed_arr = np.asarray(speed, dtype=float)
    wx_arr = np.zeros(n) if wx is None else np.asarray(wx, dtype=float)
    phi = np.empty(n)
    psid = np.empty(n)
    iters = np.empty(n, dtype=int)
    p = float(phi0)
    for k in range(n):
        sol = solve_lean(
            wy[k], wz[k], speed_arr[k], wx=wx_arr[k], phi0=p, max_iters=max_iters
        )
        phi[k] = sol.phi
        psid[k] = sol.psi_dot
        iters[k] = sol.iterations
        p = sol.phi
    return phi, psid, iters


def heading_rate_scale_error(dphi: np.ndarray | float) -> np.ndarray | float:
    """F6 closed form: ψ̇_est / ψ̇_true = cos(Δφ)."""
    return np.cos(dphi)
