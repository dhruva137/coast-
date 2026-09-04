"""GNSS-denied outage replay on real IO-VNBD trajectories.

Protocol
--------
1. Use GNSS (lat/lon/speed/bearing) for the first ``T0`` seconds to seed pose.
2. FORCE DENY for duration ``D`` — hold out GNSS as ground truth.
3. Dead-reckon with three methods and score against held-out GNSS.

Methods
-------
A) ``car_style``  — ψ̇ = g_z, where the loader's validated mount mapping gives
   g_z = -IO-VNBD ``GYROSCOPE Pitch``; integrate held GPS speed
B) ``inekf_basic`` — simple body-to-ENU INS (accel + gyro); honest phone INS
C) ``idr_lean``   — F2 + F5 fixed-point lean → yaw rate, then same integrator as A

On cars (IO-VNBD), lean ≈ 0 so C should track A closely — that is a sanity
check, not a claim that lean-aware wins on cars.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

_STRESS = Path(__file__).resolve().parent
_LAB = _STRESS.parent
for _p in (_STRESS, _LAB / "eval", _LAB / "baselines"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from load_iovnbd import (  # noqa: E402
    IoVnbdLfsError,
    attach_vehicle_truth,
    load_smartphone_csv,
    verify_csv_not_lfs_stub,
)
from metrics import ate, drift_pct, lla_to_enu, path_length, position_errors  # noqa: E402

try:
    from car_style import integrate_heading_speed, wrap_pi  # noqa: E402
except ImportError:
    from baselines.car_style import integrate_heading_speed, wrap_pi  # type: ignore  # noqa: E402

G = 9.80665
SEED = 26168
_MAX_ITERS = 8
_TOL = 1e-9


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def yaw_rate_from_lean(gy: float, gz: float, phi: float) -> float:
    """F2: ψ̇ = ω_y sin φ + ω_z cos φ."""
    return gy * math.sin(phi) + gz * math.cos(phi)


def solve_lean(
    gy: float,
    gz: float,
    speed: float,
    gx: float = 0.0,
    phi0: float | None = None,
) -> dict[str, float | int | bool]:
    """Fixed-point coordinated-turn lean (inline port of lab/baselines)."""
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
        nxt = _clamp(nxt, -1.2, 1.2)
        residual = abs(float(wrap_pi(nxt - phi)))
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


def lean_aware_yaw_rates(
    gy: np.ndarray,
    gz: np.ndarray,
    speed: np.ndarray,
    gx: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
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
        phi[i] = float(sol["phi"])
        psi[i] = float(sol["psiDot"])
        phi0 = float(sol["phi"])
    return psi, phi


def _fill_speed(speed: np.ndarray, outage_slice: slice) -> np.ndarray:
    """Hold last good speed into the outage window (GPS speed hold)."""
    s = np.asarray(speed, dtype=np.float64).copy()
    last = 0.0
    for i in range(s.size):
        if np.isfinite(s[i]) and s[i] >= 0.0:
            last = float(s[i])
        else:
            s[i] = last
    # During forced outage, freeze at the last pre-outage value.
    i0 = outage_slice.start or 0
    if i0 > 0 and np.isfinite(s[i0 - 1]):
        hold = float(s[i0 - 1])
        s[outage_slice] = hold
    return s


def _bearing_to_yaw_rad(bearing_deg: np.ndarray, i: int) -> float:
    b = float(bearing_deg[i])
    if not np.isfinite(b):
        # Fall back: search nearby
        for j in range(i, max(-1, i - 50), -1):
            if np.isfinite(bearing_deg[j]):
                b = float(bearing_deg[j])
                break
        else:
            return 0.0
    # IO-VNBD GPS orientation is degrees; nav yaw 0 = north.
    if abs(b) > 2.0 * math.pi + 0.5:
        return math.radians(b)
    return float(b)


def _rot_body_to_nav(yaw: float, roll: float, pitch: float) -> np.ndarray:
    """ZYX (yaw-pitch-roll) body→nav for phone roughly upright."""
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cr, sr = math.cos(roll), math.sin(roll)
    # R = Rz(yaw) @ Ry(pitch) @ Rx(roll); nav: x=east, y=north, z=up
    # With nav yaw 0=north: v_e = v sin yaw, v_n = v cos yaw.
    Rz = np.array([[cy, -sy, 0.0], [sy, cy, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
    # Remap: standard math yaw from +x; we use nav yaw from +y (north).
    # Use: east = sin(yaw), north = cos(yaw) via custom mapping below.
    Ry = np.array([[cp, 0.0, sp], [0.0, 1.0, 0.0], [-sp, 0.0, cp]], dtype=np.float64)
    Rx = np.array([[1.0, 0.0, 0.0], [0.0, cr, -sr], [0.0, sr, cr]], dtype=np.float64)
    R_std = Rz @ Ry @ Rx
    # Convert std (+x forward east-ish) to nav (0 yaw = north):
    # rotate so that body-x projects with nav convention.
    # Simpler planar INS used by inekf_basic ignores pitch/roll for velocity
    # and only uses yaw for horizontal; keep R for accel tilt.
    _ = R_std
    c, s = math.cos(yaw), math.sin(yaw)
    # Body x≈forward, y≈right, z≈up → ENU with yaw from north:
    # e =  ax*sin(yaw) + ay*cos(yaw)   (approx for level phone)
    # n =  ax*cos(yaw) - ay*sin(yaw)
    R = np.array(
        [
            [s * cp, c * cr + s * sp * sr, c * sr - s * sp * cr],
            [c * cp, -s * cr + c * sp * sr, -s * sr - c * sp * cr],
            [-sp, cp * sr, cp * cr],
        ],
        dtype=np.float64,
    )
    return R


def dead_reckon_car_style(
    t: np.ndarray,
    speed: np.ndarray,
    gz: np.ndarray,
    *,
    x0: float,
    y0: float,
    yaw0: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    dt = np.zeros_like(t)
    if t.size > 1:
        dt[1:] = np.diff(t)
    return integrate_heading_speed(dt, speed, gz, x0=x0, y0=y0, yaw0=yaw0)


def dead_reckon_idr_lean(
    t: np.ndarray,
    speed: np.ndarray,
    gx: np.ndarray,
    gy: np.ndarray,
    gz: np.ndarray,
    *,
    x0: float,
    y0: float,
    yaw0: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    psi, phi = lean_aware_yaw_rates(gy, gz, speed, gx)
    dt = np.zeros_like(t)
    if t.size > 1:
        dt[1:] = np.diff(t)
    x, y, yaw = integrate_heading_speed(dt, speed, psi, x0=x0, y0=y0, yaw0=yaw0)
    return x, y, yaw, phi


def dead_reckon_inekf_basic(
    t: np.ndarray,
    ax: np.ndarray,
    ay: np.ndarray,
    az: np.ndarray,
    gx: np.ndarray,
    gy: np.ndarray,
    gz: np.ndarray,
    *,
    x0: float,
    y0: float,
    yaw0: float,
    speed0: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Minimal INS: integrate gyro attitude, rotate accel, double-integrate.

    No bias estimation — deliberately crude so phone-grade blow-up is visible.
    Velocity is softly pulled toward ``speed0`` magnitude (NHC-ish) to keep
    the baseline from instantly exploding, but still honest about tilt errors.
    """
    n = t.size
    x = np.empty(n, dtype=np.float64)
    y = np.empty(n, dtype=np.float64)
    yaw = np.empty(n, dtype=np.float64)
    x[0], y[0], yaw[0] = x0, y0, yaw0
    roll = 0.0
    pitch = 0.0
    ve = speed0 * math.sin(yaw0)
    vn = speed0 * math.cos(yaw0)
    for i in range(1, n):
        dt = float(t[i] - t[i - 1])
        if dt <= 0.0 or dt > 0.5:
            x[i], y[i], yaw[i] = x[i - 1], y[i - 1], yaw[i - 1]
            continue
        # Integrate body rates (small-angle cascade).
        roll = float(wrap_pi(roll + gx[i - 1] * dt))
        pitch = float(wrap_pi(pitch + gy[i - 1] * dt))
        yaw[i] = float(wrap_pi(yaw[i - 1] + gz[i - 1] * dt))
        R = _rot_body_to_nav(yaw[i - 1], roll, pitch)
        acc_b = np.array([ax[i - 1], ay[i - 1], az[i - 1]], dtype=np.float64)
        acc_n = R @ acc_b
        acc_n[2] -= G
        ve = ve + float(acc_n[0]) * dt
        vn = vn + float(acc_n[1]) * dt
        # Soft speed hold toward last GPS speed magnitude (prevents free fall).
        spd = math.hypot(ve, vn)
        if spd > 1e-3 and speed0 > 0.5:
            scale = speed0 / spd
            # Blend: 70% kinematic speed hold, 30% free INS.
            ve = 0.7 * (ve * scale) + 0.3 * ve
            vn = 0.7 * (vn * scale) + 0.3 * vn
        x[i] = x[i - 1] + ve * dt
        y[i] = y[i - 1] + vn * dt
    return x, y, yaw


def score_outage(
    est_xy: np.ndarray,
    gt_xy: np.ndarray,
    *,
    distance_m: float | None = None,
) -> dict[str, float]:
    errs = position_errors(est_xy, gt_xy)
    final = float(errs[-1]) if errs.size else float("inf")
    max_err = float(np.max(errs)) if errs.size else float("inf")
    # Prefer caller-supplied distance (e.g. from GPS speed·dt). Raw 10 Hz
    # interpolated LLA path_length is inflated by GPS zigzag noise.
    if distance_m is None:
        dist = path_length(gt_xy)
    else:
        dist = float(distance_m)
    return {
        "ate_m": float(ate(est_xy, gt_xy, align=False)),
        "final_error_m": final,
        "max_error_m": max_err,
        "drift_pct": float(drift_pct(final, dist)),
        "distance_m": float(dist),
        "n": int(min(len(est_xy), len(gt_xy))),
    }


def _interp_lla(
    t: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Piecewise-linear interpolate lat/lon across 1 Hz GPS holds to 10 Hz."""
    t = np.asarray(t, dtype=np.float64)
    lat = np.asarray(lat, dtype=np.float64)
    lon = np.asarray(lon, dtype=np.float64)
    if t.size < 2:
        return lat.copy(), lon.copy()
    changed = np.ones(t.size, dtype=bool)
    changed[1:] = (np.abs(np.diff(lat)) > 1e-10) | (np.abs(np.diff(lon)) > 1e-10)
    changed[0] = True
    # Always keep last sample.
    changed[-1] = True
    idx = np.where(changed)[0]
    if idx.size < 2:
        return lat.copy(), lon.copy()
    lat_i = np.interp(t, t[idx], lat[idx])
    lon_i = np.interp(t, t[idx], lon[idx])
    return lat_i, lon_i


def run_outage_replay(
    data: dict[str, Any],
    *,
    t0_s: float = 30.0,
    deny_s: float = 60.0,
    start_idx: int | None = None,
    seed: int = SEED,
) -> dict[str, Any]:
    """Force GNSS deny for ``deny_s`` after a seed window; score three DRs.

    If ``start_idx`` is set, the seed window ends at that index (outage starts
    there). Otherwise outage starts at the first sample with t ≥ ``t0_s`` from
    the beginning of the loaded array (caller should slice the segment).
    """
    _ = seed  # reserved for deterministic adversarial callers
    t = np.asarray(data["t_s"], dtype=np.float64)
    n = t.size
    if n < 100:
        raise ValueError("trajectory too short for outage replay")

    if start_idx is None:
        # Relative to this array's own clock.
        t_rel = t - t[0]
        i0 = int(np.searchsorted(t_rel, t0_s, side="left"))
    else:
        i0 = int(start_idx)
    i0 = max(10, min(i0, n - 20))
    i1 = i0
    t_end = t[i0] + float(deny_s)
    while i1 < n and t[i1] < t_end:
        i1 += 1
    i1 = min(i1, n)
    if i1 - i0 < 10:
        raise ValueError(f"outage window too short: {i1 - i0} samples")

    # Ground truth ENU from held-out GNSS.
    #
    # Prefer the paired V-*.csv CAN log: it carries a true 10 Hz fix, whereas
    # the smartphone table holds each fix for ~9 s (S-S1: 498 unique positions
    # across 51 746 rows against the CAN log's 40 684). Interpolating that
    # staircase and scoring against it measures the interpolation as much as
    # the estimator, so it is now a labelled fallback, not the default.
    sl = slice(0, i1)
    truth_source = str(data.get("truth_source", "phone_gnss_interpolated"))
    if truth_source == "can_10hz" and int(data.get("can_n", 0)) >= i1:
        truth_lat = np.asarray(data["can_lat"][sl], dtype=np.float64)
        truth_lon = np.asarray(data["can_lon"][sl], dtype=np.float64)
    else:
        truth_source = "phone_gnss_interpolated"
        truth_lat, truth_lon = _interp_lla(t[sl], data["lat"][sl], data["lon"][sl])
    origin_lat = float(truth_lat[0])
    origin_lon = float(truth_lon[0])
    gt_all = lla_to_enu(truth_lat, truth_lon, origin_lat, origin_lon)
    gt_out = gt_all[i0:]  # outage portion only

    yaw0 = _bearing_to_yaw_rad(data["bearing_deg"], i0 - 1)
    x0, y0 = float(gt_all[i0 - 1, 0]), float(gt_all[i0 - 1, 1])
    # During outage: hold last good speed, but prefer a short pre-outage mean
    # so a single slow GPS tick does not starve the whole deny window.
    speed_raw = np.asarray(data["speed_mps"][:i1], dtype=np.float64)
    speed_hold = _fill_speed(speed_raw, slice(i0, i1))
    pre = speed_raw[max(0, i0 - int(2.0 * 10)) : i0]  # ~2 s pre-outage
    pre = pre[np.isfinite(pre)]
    if pre.size:
        speed0 = float(np.median(pre))
        speed_hold[i0:i1] = speed0
    else:
        speed0 = float(speed_hold[i0 - 1]) if i0 > 0 else float(speed_hold[i0])

    t_o = t[i0:i1]
    t_dr = np.concatenate([[t[i0 - 1]], t_o])
    spd_dr = np.concatenate([[speed0], speed_hold[i0:i1]])
    gx_dr = np.concatenate([[data["gx"][i0 - 1]], data["gx"][i0:i1]])
    gy_dr = np.concatenate([[data["gy"][i0 - 1]], data["gy"][i0:i1]])
    gz_dr = np.concatenate([[data["gz"][i0 - 1]], data["gz"][i0:i1]])
    ax_dr = np.concatenate([[data["ax"][i0 - 1]], data["ax"][i0:i1]])
    ay_dr = np.concatenate([[data["ay"][i0 - 1]], data["ay"][i0:i1]])
    az_dr = np.concatenate([[data["az"][i0 - 1]], data["az"][i0:i1]])

    xc, yc, yaw_c = dead_reckon_car_style(t_dr, spd_dr, gz_dr, x0=x0, y0=y0, yaw0=yaw0)
    xl, yl, yaw_l, phi = dead_reckon_idr_lean(
        t_dr, spd_dr, gx_dr, gy_dr, gz_dr, x0=x0, y0=y0, yaw0=yaw0
    )
    xi, yi, yaw_i = dead_reckon_inekf_basic(
        t_dr, ax_dr, ay_dr, az_dr, gx_dr, gy_dr, gz_dr,
        x0=x0, y0=y0, yaw0=yaw0, speed0=speed0,
    )

    est = {
        "car_style": np.column_stack([xc[1:], yc[1:]]),
        "inekf_basic": np.column_stack([xi[1:], yi[1:]]),
        "idr_lean": np.column_stack([xl[1:], yl[1:]]),
    }
    # Distance from held-out *speed* (not the zigzagging lat/lon polyline).
    # CAN indicated speed where the pair exists, else the phone's GNSS speed.
    truth_speed = (
        data["can_speed_mps"] if truth_source == "can_10hz" else data["speed_mps"]
    )
    spd_out = np.asarray(truth_speed[i0:i1], dtype=np.float64)
    spd_out = np.where(np.isfinite(spd_out), np.maximum(spd_out, 0.0), speed0)
    dt_out = np.diff(t[i0:i1], prepend=t[i0])
    dt_out = np.clip(dt_out, 0.0, 0.5)
    dist_gt = float(np.sum(spd_out * dt_out))
    if dist_gt < 1.0:
        dist_gt = float(path_length(gt_out))

    scores = {name: score_outage(xy, gt_out, distance_m=dist_gt) for name, xy in est.items()}

    fe_c = scores["car_style"]["final_error_m"]
    fe_l = scores["idr_lean"]["final_error_m"]
    ratio = float(fe_l / fe_c) if fe_c > 1e-6 else float("nan")

    return {
        "truth_source": truth_source,
        "t0_s": float(t[i0] - t[0]),
        "deny_s": float(t[i1 - 1] - t[i0]) if i1 > i0 else 0.0,
        "i0": i0,
        "i1": i1,
        "speed0_mps": speed0,
        "scores": scores,
        "est": est,
        "gt_out": gt_out,
        "phi_mean_deg": float(np.rad2deg(np.mean(np.abs(phi)))),
        "car_vs_lean_final_ratio": ratio,
        "yaw": {"car_style": yaw_c[1:], "inekf_basic": yaw_i[1:], "idr_lean": yaw_l[1:]},
    }


def run_outage_on_csv(
    path: Path | str,
    *,
    t0_s: float = 30.0,
    deny_s: float = 60.0,
    start_idx: int | None = None,
    seed: int = SEED,
) -> dict[str, Any]:
    path = Path(path)
    verify_csv_not_lfs_stub(path)
    data = attach_vehicle_truth(load_smartphone_csv(path))
    result = run_outage_replay(
        data, t0_s=t0_s, deny_s=deny_s, start_idx=start_idx, seed=seed
    )
    result["csv"] = str(path)
    result["name"] = data["name"]
    result["file_bytes"] = data["file_bytes"]
    result["hz_est"] = data["hz_est"]
    return result


if __name__ == "__main__":
    from load_iovnbd import find_smartphone_csvs

    csvs = find_smartphone_csvs()
    if not csvs:
        raise SystemExit("no real S-*.csv found")
    r = run_outage_on_csv(csvs[0], t0_s=30.0, deny_s=40.0)
    print(r["name"], r["deny_s"], r["scores"])
