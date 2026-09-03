"""
Car-style heading integrator — the Act 2 villain.

    ψ̇ = ω_z          (WRONG on two-wheelers)

Textbook single-track kinematics (Titterton & Weston; bible F1–F2):

    ω_body = [ φ̇ ,  ψ̇ sin φ ,  ψ̇ cos φ ]

so the phone's vertical gyro is ``ω_z = ψ̇ · cos(φ)``. Every published
vehicle-DR stack (Brossard AI-IMU, Qian AVNet, OdoNet, …) was trained on
cars, where φ ≈ 0 and the substitution is harmless. On a scooter at 26°
lean the heading rate is short by ~10 %; on a same-direction route that
compounding error is the 23 % drift in finding F3.

This module does one thing: treat ``gz`` as yaw rate and dead-reckon
with speed. The lean-aware fix lives in ``compare.py`` (fixed-point
solver copied inline — do not import from ``core/ts``).

Golden rule: both methods feed the same ``(dt, speed, ·)`` into
``integrate_heading_speed``. Only the yaw-rate series differs.
"""

from __future__ import annotations

import numpy as np

G = 9.80665
SEED = 26168


def wrap_pi(angle: np.ndarray | float) -> np.ndarray:
    """Wrap to (−π, π]."""
    a = np.asarray(angle, dtype=np.float64)
    return (a + np.pi) % (2.0 * np.pi) - np.pi


def car_style_yaw_rate(gz: np.ndarray | float) -> np.ndarray:
    """
    The wrong equation: ψ̇ = ω_z.

    On a leaning bike this equals the true heading rate times cos(φ).
    """
    return np.asarray(gz, dtype=np.float64)


def dt_from_t(t: np.ndarray) -> np.ndarray:
    """``dt[0] = 0``; ``dt[i] = t[i] − t[i−1]`` for i > 0."""
    t = np.asarray(t, dtype=np.float64).ravel()
    dt = np.zeros_like(t)
    if t.size > 1:
        dt[1:] = np.diff(t)
    return dt


def integrate_heading_speed(
    dt: np.ndarray | float,
    speed: np.ndarray,
    yaw_rate: np.ndarray,
    *,
    x0: float = 0.0,
    y0: float = 0.0,
    yaw0: float = 0.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Shared dead-reckon step. ENU metres, nav yaw (0 = north).

        yaw[i] = wrap(yaw[i-1] + yaw_rate[i-1] * dt[i])
        x[i]   = x[i-1] + speed[i-1] * sin(yaw[i-1]) * dt[i]   # east
        y[i]   = y[i-1] + speed[i-1] * cos(yaw[i-1]) * dt[i]   # north

    Left-Euler, identical for every caller. Do not "improve" one
    baseline with RK4 and leave the other on Euler — that would break
    comparability.
    """
    speed = np.asarray(speed, dtype=np.float64).ravel()
    yaw_rate = np.asarray(yaw_rate, dtype=np.float64).ravel()
    n = speed.size
    if yaw_rate.size != n:
        raise ValueError("speed and yaw_rate must be the same length")
    dt_arr = np.broadcast_to(np.asarray(dt, dtype=np.float64), (n,)).copy()
    dt_arr = np.maximum(dt_arr, 0.0)

    x = np.empty(n, dtype=np.float64)
    y = np.empty(n, dtype=np.float64)
    yaw = np.empty(n, dtype=np.float64)
    x[0] = float(x0)
    y[0] = float(y0)
    yaw[0] = float(yaw0)
    for i in range(1, n):
        dti = float(dt_arr[i])
        yaw[i] = float(wrap_pi(yaw[i - 1] + yaw_rate[i - 1] * dti))
        x[i] = x[i - 1] + speed[i - 1] * np.sin(yaw[i - 1]) * dti
        y[i] = y[i - 1] + speed[i - 1] * np.cos(yaw[i - 1]) * dti
    return x, y, yaw


def integrate_car_style(
    t: np.ndarray,
    speed: np.ndarray,
    gz: np.ndarray,
    *,
    x0: float = 0.0,
    y0: float = 0.0,
    yaw0: float = 0.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Convenience: car-style yaw rates through the shared integrator."""
    return integrate_heading_speed(
        dt_from_t(t),
        speed,
        car_style_yaw_rate(gz),
        x0=x0,
        y0=y0,
        yaw0=yaw0,
    )


if __name__ == "__main__":
    rng = np.random.default_rng(SEED)
    t = np.arange(50, dtype=np.float64) * 0.05
    speed = np.full(50, 8.0)
    gz = np.full(50, 0.2)
    x, y, yaw = integrate_car_style(t, speed, gz)
    assert x.shape == (50,)
    assert np.isfinite(x).all()
    print(f"car_style.py self-check ok  end=({x[-1]:.3f}, {y[-1]:.3f})")
