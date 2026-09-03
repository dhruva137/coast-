"""Shared two-wheeler / IMU physics for the SIH26168 research lab.

Textbook roll/yaw kinematics (Titterton & Weston). We claim the APPLICATION
to smartphone two-wheeler dead reckoning, not discovery of the identities.

    ω_body = [ φ̇ , ψ̇ sin φ , ψ̇ cos φ ]          [F1]
    ψ̇     = ω_y sin φ + ω_z cos φ                [F2, exact]
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.signal import butter, filtfilt

G = 9.80665  # m/s², standard gravity
DEG = np.pi / 180.0
RAD = 180.0 / np.pi

# STMicro LSM6DSM (AVNet / Qian et al. 2025), SI units.
GYRO_ARW_DPS = 3.8e-3  # °/s/√Hz
GYRO_ARW = GYRO_ARW_DPS * DEG  # rad/s/√Hz
ACCEL_ND_UG = 90.0  # µg/√Hz
ACCEL_ND = ACCEL_ND_UG * 1e-6 * G  # m/s²/√Hz

# IO-VNBD-derived two-wheeler vibration (project bible §4).
VIB_ACCEL_G = 0.15
VIB_ACCEL = VIB_ACCEL_G * G  # m/s² RMS
VIB_GYRO = 0.08  # rad/s RMS

PLOT_DIR = Path(__file__).resolve().parents[1] / "plots"
MOTION_CUTOFF_HZ = 2.0


def wrap_pi(a: np.ndarray | float) -> np.ndarray | float:
    return (np.asarray(a) + np.pi) % (2.0 * np.pi) - np.pi


def deg(x: np.ndarray | float) -> np.ndarray | float:
    return np.asarray(x) * RAD


def rad(x: np.ndarray | float) -> np.ndarray | float:
    return np.asarray(x) * DEG


def rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(int(seed))


def body_rates(phi: np.ndarray | float, phi_dot: np.ndarray | float, psi_dot: np.ndarray | float):
    """F1: ω_body = [φ̇, ψ̇ sin φ, ψ̇ cos φ]."""
    phi = np.asarray(phi, dtype=float)
    phi_dot = np.asarray(phi_dot, dtype=float)
    psi_dot = np.asarray(psi_dot, dtype=float)
    wx = phi_dot
    wy = psi_dot * np.sin(phi)
    wz = psi_dot * np.cos(phi)
    return wx, wy, wz


def yaw_rate_from_lean(wy: np.ndarray | float, wz: np.ndarray | float, phi: np.ndarray | float):
    """F2: exact ψ̇ = ω_y sin φ + ω_z cos φ."""
    return np.asarray(wy) * np.sin(phi) + np.asarray(wz) * np.cos(phi)


def coordinated_psi_dot(v: float, phi: float) -> float:
    """Coordinated-turn yaw rate: tan φ = v ψ̇ / g  ⇒  ψ̇ = g tan φ / v."""
    if abs(v) < 1e-9:
        return 0.0
    return G * np.tan(phi) / v


def coordinated_phi(v: float, psi_dot: float) -> float:
    return float(np.arctan2(v * psi_dot, G))


def specific_force_coordinated(phi: float, a_fwd: float = 0.0) -> tuple[float, float, float]:
    """Body-frame specific force in a coordinated turn: [a_fwd, 0, g/cos φ]."""
    c = np.cos(phi)
    az = G / c if abs(c) > 1e-6 else np.sign(c) * 1e6
    return a_fwd, 0.0, float(az)


@dataclass
class ImuNoise:
    gyro_arw: float = GYRO_ARW
    accel_nd: float = ACCEL_ND
    vib_accel: float = VIB_ACCEL
    vib_gyro: float = VIB_GYRO
    bias_gyro: np.ndarray | None = None  # rad/s, length 3


def lsm6dsm_noise(
    n: int,
    fs: float,
    noise: ImuNoise,
    seed: int,
    *,
    vib_highpass_hz: float = 10.0,
) -> tuple[np.ndarray, np.ndarray]:
    """MEMS white noise + band-limited vibration (accel m/s², gyro rad/s).

    Vibration lives above ~10 Hz (F7). Sensor densities follow LSM6DSM.
    Discrete white-noise std = density * sqrt(fs).
    """
    r = rng(seed)
    sqrt_fs = np.sqrt(fs)
    gyro = r.normal(0.0, noise.gyro_arw * sqrt_fs, size=(n, 3))
    accel = r.normal(0.0, noise.accel_nd * sqrt_fs, size=(n, 3))
    if noise.bias_gyro is not None:
        gyro = gyro + np.asarray(noise.bias_gyro, dtype=float).reshape(1, 3)

    vib_g = _band_limited(r.normal(0.0, 1.0, size=(n, 3)), fs, vib_highpass_hz, high=True)
    vib_w = _band_limited(r.normal(0.0, 1.0, size=(n, 3)), fs, vib_highpass_hz, high=True)
    vib_g = _scale_rms(vib_g, noise.vib_accel)
    vib_w = _scale_rms(vib_w, noise.vib_gyro)
    # Body-axis mix: vertical accel + roll/yaw gyro take most of the road energy.
    accel = accel + vib_g * np.array([0.35, 0.45, 1.0])
    gyro = gyro + vib_w * np.array([1.0, 0.55, 0.45])
    return accel, gyro


def _scale_rms(x: np.ndarray, rms: float) -> np.ndarray:
    cur = float(np.sqrt(np.mean(x * x)))
    if cur < 1e-18:
        return x
    return x * (rms / cur)


def _band_limited(x: np.ndarray, fs: float, cutoff: float, high: bool) -> np.ndarray:
    nyq = 0.5 * fs
    w = min(0.99, max(1e-4, cutoff / nyq))
    b, a = butter(2, w, btype="highpass" if high else "lowpass")
    return filtfilt(b, a, x, axis=0)


def lowpass(x: np.ndarray, fs: float, cutoff: float = MOTION_CUTOFF_HZ, axis: int = 0) -> np.ndarray:
    """F7 motion-band filter. Vehicle dynamics live below 2 Hz."""
    if x.shape[axis] < 16:
        return x
    nyq = 0.5 * fs
    w = min(0.99, max(1e-4, cutoff / nyq))
    b, a = butter(2, w, btype="lowpass")
    return filtfilt(b, a, x, axis=axis)


def dead_reckon(
    v: np.ndarray,
    psi_dot: np.ndarray,
    dt: float,
    xy0: tuple[float, float] = (0.0, 0.0),
    psi0: float = 0.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Integrate heading and planar position. v and ψ̇ are samples at dt."""
    v = np.asarray(v, dtype=float)
    psi_dot = np.asarray(psi_dot, dtype=float)
    psi = psi0 + np.concatenate([[0.0], np.cumsum(psi_dot[:-1] * dt)])
    x = np.empty_like(psi)
    y = np.empty_like(psi)
    x[0], y[0] = xy0
    x[1:] = xy0[0] + np.cumsum(v[:-1] * np.cos(psi[:-1]) * dt)
    y[1:] = xy0[1] + np.cumsum(v[:-1] * np.sin(psi[:-1]) * dt)
    return x, y, psi


def path_length(x: np.ndarray, y: np.ndarray) -> float:
    return float(np.sum(np.hypot(np.diff(x), np.diff(y))))


def drift_pct(err_m: float, distance_m: float) -> float:
    if distance_m < 1e-9:
        return 0.0
    return 100.0 * err_m / distance_m


def same_direction_route(
    phi: float,
    v: float,
    n_turns: int = 5,
    straight_m: float = 55.0,
    dt: float = 0.01,
    *,
    radius: float | None = None,
    growth: float = 1.0,
    ramp_s: float = 0.08,
) -> dict:
    """Same-direction left turns so cos(lean) heading error accumulates [F3].

    Default: five 90° arcs (450° of turning) → at 45° lean, heading error
    Θ(1 − cos φ) ≈ −131.8° (bible: −135°). Growing straights convert that
    heading error into position drift (a pure circle bounds error by ~2R).
    """
    if radius is None:
        radius = v**2 / (G * np.tan(phi)) if abs(phi) > 1e-6 else 1e6
    psi_dot_turn = v / radius
    arc_t = (0.5 * np.pi) / max(abs(psi_dot_turn), 1e-9)

    segs: list[tuple[str, float, float]] = []
    L = straight_m
    for _ in range(n_turns):
        segs.append(("straight", L / max(v, 1e-9), 0.0))
        segs.append(("turn", arc_t, phi))
        L *= growth

    chunks_t = []
    chunks_phi = []
    chunks_psid = []
    t0 = 0.0
    n_ramp = max(2, int(round(ramp_s / dt)))
    prev_phi = 0.0
    for kind, dur, tgt in segs:
        n = max(1, int(round(dur / dt)))
        tt = t0 + np.arange(n) * dt
        if kind == "turn":
            ph = np.full(n, tgt)
            n_r = min(n_ramp, max(2, n // 3))
            ph[:n_r] = np.linspace(prev_phi, tgt, n_r)
            ph[-n_r:] = np.linspace(tgt, 0.0, n_r)
            chunks_phi.append(ph)
            chunks_psid.append(np.full(n, psi_dot_turn))
            prev_phi = 0.0
        else:
            chunks_phi.append(np.zeros(n))
            chunks_psid.append(np.zeros(n))
            prev_phi = 0.0
        chunks_t.append(tt)
        t0 = float(tt[-1] + dt)
    t_arr = np.concatenate(chunks_t)
    phi_arr = np.concatenate(chunks_phi)
    psid = np.concatenate(chunks_psid)
    v_arr = np.full_like(t_arr, v)
    phi_dot = np.gradient(phi_arr, dt)
    wx, wy, wz = body_rates(phi_arr, phi_dot, psid)
    ax = np.gradient(v_arr, dt)
    fy = np.zeros_like(ax)
    fz = np.array([specific_force_coordinated(p, 0.0)[2] for p in phi_arr])
    x, y, psi = dead_reckon(v_arr, psid, dt)
    return {
        "t": t_arr,
        "dt": dt,
        "v": v_arr,
        "phi": phi_arr,
        "phi_dot": phi_dot,
        "psi_dot": psid,
        "psi": psi,
        "wx": wx,
        "wy": wy,
        "wz": wz,
        "fx": ax,
        "fy": fy,
        "fz": fz,
        "x": x,
        "y": y,
        "radius": radius,
        "distance": path_length(x, y),
    }


def apply_imu_noise(truth: dict, seed: int, noise: ImuNoise | None = None) -> dict:
    noise = noise or ImuNoise()
    n = truth["t"].size
    fs = 1.0 / truth["dt"]
    a_n, g_n = lsm6dsm_noise(n, fs, noise, seed)
    out = dict(truth)
    out["fx_m"] = truth["fx"] + a_n[:, 0]
    out["fy_m"] = truth["fy"] + a_n[:, 1]
    out["fz_m"] = truth["fz"] + a_n[:, 2]
    out["wx_m"] = truth["wx"] + g_n[:, 0]
    out["wy_m"] = truth["wy"] + g_n[:, 1]
    out["wz_m"] = truth["wz"] + g_n[:, 2]
    out["fs"] = fs
    return out


def ensure_plot_dir() -> Path:
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    return PLOT_DIR
