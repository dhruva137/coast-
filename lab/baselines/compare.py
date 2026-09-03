"""
Act 2: car-style (ψ̇ = ω_z) vs lean-aware (F2 + F5) on the same IMU.

Golden rule: one synthetic log, two yaw-rate series, one integrator
(``integrate_heading_speed``). Drift % is the printed score.

The fixed-point lean solver is copied inline from ``core/ts``
``leansolver/index.ts``. Do **not** import the TypeScript (or any
``core/``) module from this file — lab baselines stay self-contained.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
_EVAL = _HERE.parent / "eval"
for _p in (_HERE, _EVAL):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from car_style import (  # noqa: E402
    G,
    SEED,
    car_style_yaw_rate,
    dt_from_t,
    integrate_heading_speed,
)
from metrics import drift_pct, loop_closure_error, path_length  # noqa: E402

# ---------------------------------------------------------------------------
# Fixed-point coordinated-turn solver — verbatim port of core/ts leansolver.
#   ψ̇ = ω_y sin φ + ω_z cos φ                         [exact, F2]
#   φ  = arctan( v · ψ̇ / g )                           [coordinated turn]
# Substitute and iterate. Converges in 3–5 steps. Lean RMSE 0.5–1.0° in sim.
# Insensitivity [F6]: ψ̇_est = ψ̇ · cos(φ − φ̂)
# ---------------------------------------------------------------------------

_MAX_ITERS = 8
_TOL = 1e-9


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def _wrap_pi_s(a: float) -> float:
    while a > math.pi:
        a -= 2.0 * math.pi
    while a < -math.pi:
        a += 2.0 * math.pi
    return a


def yaw_rate_from_lean(gy: float, gz: float, phi: float) -> float:
    """F2: ψ̇ = ω_y sin φ + ω_z cos φ."""
    return gy * math.sin(phi) + gz * math.cos(phi)


def solve_lean(
    gy: float,
    gz: float,
    speed: float,
    gx: float = 0.0,
    phi0: float | None = None,
) -> dict:
    """
    Solve φ = arctan( v (ω_y sin φ + ω_z cos φ) / g ) by fixed-point
    iteration. Returns 0 lean when nearly stopped (no observability).
    Control flow matches ``solveLean`` in core/ts (iteration counter
    increments past the converging step).
    """
    v = max(0.0, float(speed))
    if v < 0.4:
        return {
            "phi": 0.0,
            "psiDot": float(gz),
            "phiDot": float(gx),
            "iterations": 0,
            "residual": 0.0,
            "coordinated": False,
        }
    phi = math.atan2(v * gz, G) if phi0 is None else float(phi0)
    phi = _clamp(phi, -1.2, 1.2)
    residual = 1.0
    i = 0
    while i < _MAX_ITERS:
        psi_dot = yaw_rate_from_lean(gy, gz, phi)
        nxt = math.atan2(v * psi_dot, G)
        residual = abs(_wrap_pi_s(nxt - phi))
        phi = nxt
        if residual < _TOL:
            i += 1
            break
        i += 1
    psi_dot = yaw_rate_from_lean(gy, gz, phi)
    return {
        "phi": phi,
        "psiDot": psi_dot,
        "phiDot": float(gx),
        "iterations": i,
        "residual": residual,
        "coordinated": abs(v * psi_dot) > 0.15,
    }


def generate_leaning_log(
    *,
    seed: int = SEED,
    hz: float = 50.0,
    speed: float = 8.0,
    lean_deg: float = 26.0,
    n_laps: int = 2,
    x0: float = 0.0,
    y0: float = 0.0,
    yaw0: float = 0.0,
) -> dict[str, np.ndarray]:
    """
    Coordinated-turn two-wheeler, noise-free, deterministic.

    Constant lean, constant yaw rate, ``n_laps`` of a circle. Body rates
    from F1: ω = [φ̇, ψ̇ sin φ, ψ̇ cos φ] with φ̇ = 0. Ground-truth
    position is integrated with the *true* heading rate so the marked
    start is a real loop-closure (p_end_true ≈ p_start).

    26° is the F3 working example (car-style ~23 % drift on a
    same-direction route). Physics is honest; we do not bake that
    number in.
    """
    rng = np.random.default_rng(int(seed))
    _ = rng  # reserved so future noise stays seeded
    phi = math.radians(float(lean_deg))
    v = float(speed)
    psi_dot = (G * math.tan(phi)) / v  # coordinated-turn inverse
    period = 2.0 * math.pi / psi_dot
    t_end = n_laps * period
    n = int(round(t_end * hz)) + 1
    t = np.arange(n, dtype=np.float64) / float(hz)
    dt = 1.0 / float(hz)

    x = np.empty(n, dtype=np.float64)
    y = np.empty(n, dtype=np.float64)
    yaw = np.empty(n, dtype=np.float64)
    x[0], y[0], yaw[0] = float(x0), float(y0), float(yaw0)
    for i in range(1, n):
        yaw[i] = _wrap_pi_s(yaw[i - 1] + psi_dot * dt)
        x[i] = x[i - 1] + v * math.sin(yaw[i - 1]) * dt
        y[i] = y[i - 1] + v * math.cos(yaw[i - 1]) * dt

    gy = np.full(n, psi_dot * math.sin(phi), dtype=np.float64)
    gz = np.full(n, psi_dot * math.cos(phi), dtype=np.float64)
    gx = np.zeros(n, dtype=np.float64)
    speed_arr = np.full(n, v, dtype=np.float64)
    lean = np.full(n, phi, dtype=np.float64)

    return {
        "t": t,
        "x": x,
        "y": y,
        "yaw": yaw,
        "speed": speed_arr,
        "gx": gx,
        "gy": gy,
        "gz": gz,
        "lean": lean,
        "psi_dot_true": np.full(n, psi_dot, dtype=np.float64),
    }


def lean_aware_yaw_rates(
    gy: np.ndarray,
    gz: np.ndarray,
    speed: np.ndarray,
    gx: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Run the inline solver along the log; warm-start with previous φ."""
    gy = np.asarray(gy, dtype=np.float64).ravel()
    gz = np.asarray(gz, dtype=np.float64).ravel()
    speed = np.asarray(speed, dtype=np.float64).ravel()
    n = gy.size
    gx_arr = np.zeros(n) if gx is None else np.asarray(gx, dtype=np.float64).ravel()
    psi = np.empty(n, dtype=np.float64)
    phi = np.empty(n, dtype=np.float64)
    phi0: float | None = None
    for i in range(n):
        sol = solve_lean(float(gy[i]), float(gz[i]), float(speed[i]), float(gx_arr[i]), phi0)
        phi[i] = sol["phi"]
        psi[i] = sol["psiDot"]
        phi0 = sol["phi"]
    return psi, phi


def run_comparison(seed: int = SEED, lean_deg: float = 26.0, n_laps: int = 2) -> dict:
    log = generate_leaning_log(seed=seed, lean_deg=lean_deg, n_laps=n_laps)
    dt = dt_from_t(log["t"])
    x0, y0, yaw0 = float(log["x"][0]), float(log["y"][0]), float(log["yaw"][0])

    psi_car = car_style_yaw_rate(log["gz"])
    psi_ours, phi_hat = lean_aware_yaw_rates(log["gy"], log["gz"], log["speed"], log["gx"])

    x_car, y_car, yaw_car = integrate_heading_speed(
        dt, log["speed"], psi_car, x0=x0, y0=y0, yaw0=yaw0
    )
    x_ours, y_ours, yaw_ours = integrate_heading_speed(
        dt, log["speed"], psi_ours, x0=x0, y0=y0, yaw0=yaw0
    )

    gt_xy = np.column_stack([log["x"], log["y"]])
    car_xy = np.column_stack([x_car, y_car])
    ours_xy = np.column_stack([x_ours, y_ours])
    marker = gt_xy[0]
    distance = path_length(gt_xy)

    car_lc = loop_closure_error(car_xy, marker=marker)
    ours_lc = loop_closure_error(ours_xy, marker=marker)
    return {
        "seed": seed,
        "lean_deg": lean_deg,
        "n_laps": n_laps,
        "n": int(len(log["t"])),
        "distance_m": distance,
        "car": {
            "xy": car_xy,
            "yaw": yaw_car,
            "loop_closure_m": car_lc,
            "drift_pct": drift_pct(car_lc, distance),
        },
        "ours": {
            "xy": ours_xy,
            "yaw": yaw_ours,
            "phi": phi_hat,
            "loop_closure_m": ours_lc,
            "drift_pct": drift_pct(ours_lc, distance),
        },
        "gt": {"xy": gt_xy, "yaw": log["yaw"], "lean": log["lean"], "t": log["t"]},
    }


def _fmt(value: float, spec: str = ".3f") -> str:
    if not np.isfinite(value):
        return "n/a"
    return format(value, spec)


def print_table(result: dict) -> None:
    car = result["car"]
    ours = result["ours"]
    print()
    print("SIH26168  Act 2 - car-style vs lean-aware")
    print(
        f"seed={result['seed']}  same IMU+speed  n={result['n']}  "
        f"distance={result['distance_m']:.2f} m  lean={result['lean_deg']:.1f} deg  "
        f"laps={result['n_laps']}"
    )
    print("integrator: integrate_heading_speed  (identical Euler)")
    print("-" * 64)
    print(f"{'method':<28} {'loop_closure_m':>16} {'drift_%':>12}")
    print("-" * 64)
    print(
        f"{'car_style  (psi_dot = gz)':<28} "
        f"{_fmt(car['loop_closure_m'], '16.4f')} {_fmt(car['drift_pct'], '12.3f')}"
    )
    print(
        f"{'lean_aware (F2 + F5)':<28} "
        f"{_fmt(ours['loop_closure_m'], '16.4f')} {_fmt(ours['drift_pct'], '12.3f')}"
    )
    print("-" * 64)
    print("car_style is WRONG on two-wheelers; it is the Act 2 villain.")
    print()


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    p = argparse.ArgumentParser(description="Act 2 car-style vs lean-aware drift %")
    p.add_argument("--seed", type=int, default=SEED)
    p.add_argument("--lean-deg", type=float, default=26.0)
    p.add_argument("--laps", type=int, default=2)
    args = p.parse_args(argv)
    result = run_comparison(seed=args.seed, lean_deg=args.lean_deg, n_laps=args.laps)
    print_table(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
