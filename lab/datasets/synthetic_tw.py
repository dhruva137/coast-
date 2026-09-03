"""Seeded synthetic leaning two-wheeler + car IMU windows.

IO-VNBD is 10 Hz. AVNet's 200-sample @ 200 Hz windows are wrong here.
We emit 2.0 s windows → 20 samples at 10 Hz.

Coordinated-turn kinematics (bible F1–F5)::

    ω_body = [φ̇, ψ̇ sin φ, ψ̇ cos φ]
    φ      = arctan(v · ψ̇ / g)
    f_body ≈ [a_fwd, 0, g / cos φ]     # coordinated: lateral specific force ~ 0

Car (φ = 0)::

    ω_body ≈ [0, 0, ψ̇]
    f_body ≈ [a_fwd, v · ψ̇, g]

Noise matches the TS simulator: vibration ~0.15 g / 0.08 rad/s, LSM6DSM densities.
Motion power is synthesised below 2 Hz ([F7]); vibration is the high band.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

try:
    from .log_schema import (
        G,
        IMU_HZ_IO_VNBD,
        MOTION_BAND_HZ,
        WINDOW_SAMPLES,
        WINDOW_SECONDS,
    )
except ImportError:  # script / path-bootstrap import
    from log_schema import (  # type: ignore
        G,
        IMU_HZ_IO_VNBD,
        MOTION_BAND_HZ,
        WINDOW_SAMPLES,
        WINDOW_SECONDS,
    )

VehicleKind = Literal["tw", "car"]

# LSM6DSM-class MEMS + IO-VNBD-reported vibration (bible §4, simulate.ts).
GYRO_ARW = 3.8e-3 * np.pi / 180.0  # rad/s/√Hz
ACCEL_ND = 90e-6 * G  # m/s²/√Hz
VIB_A = 0.15 * G
VIB_W = 0.08
PHI_CLAMP = 1.2  # rad, ~69°


@dataclass
class WindowBatch:
    """Stacked 2.0 s @ 10 Hz windows for AVNet-tiny."""

    imu: np.ndarray  # (N, T, 6) ax,ay,az,gx,gy,gz
    speed: np.ndarray  # (N,) body-frame speed, m/s
    psi_dot: np.ndarray  # (N,) world-z yaw rate, rad/s
    roll_res: np.ndarray  # (N,) lean minus coordinated-turn model, rad
    pitch_res: np.ndarray  # (N,) pitch minus flat-road model, rad
    phi: np.ndarray  # (N,) true lean, rad
    vehicle: np.ndarray  # (N,) 1 = two-wheeler, 0 = car
    hz: float = IMU_HZ_IO_VNBD
    window_s: float = WINDOW_SECONDS

    def __len__(self) -> int:
        return int(self.imu.shape[0])

    def y(self) -> np.ndarray:
        """(N, 4) speed, psi_dot, roll_res, pitch_res."""
        return np.stack([self.speed, self.psi_dot, self.roll_res, self.pitch_res], axis=1).astype(
            np.float32
        )


def _lowband(t: np.ndarray, rng: np.random.Generator, amp: float, fmax: float) -> np.ndarray:
    """Sum of slow sines strictly inside the motion band (< 2 Hz)."""
    fmax = min(float(fmax), MOTION_BAND_HZ - 0.15)
    y = np.zeros_like(t)
    if amp <= 0:
        return y
    for _ in range(3):
        f = float(rng.uniform(0.04, max(0.05, fmax)))
        ph = float(rng.uniform(0.0, 2.0 * np.pi))
        a = float(rng.uniform(0.25, 1.0)) * amp
        y = y + a * np.sin(2.0 * np.pi * f * t + ph)
    return y


def _bump(t: np.ndarray, rng: np.random.Generator, amp: float, width: tuple[float, float]) -> np.ndarray:
    if t.size < 4:
        return np.zeros_like(t)
    t0 = float(rng.uniform(t[1], t[-2]))
    w = float(rng.uniform(*width))
    return amp * np.exp(-0.5 * ((t - t0) / max(w, 1e-3)) ** 2)


def generate_trace(
    kind: VehicleKind,
    duration_s: float = 6.0,
    *,
    hz: float = IMU_HZ_IO_VNBD,
    rng: np.random.Generator | None = None,
    seed: int | None = None,
) -> dict[str, np.ndarray]:
    """One continuous IMU + label trace. Motion < 2 Hz; vibration is additive."""
    if rng is None:
        rng = np.random.default_rng(seed)
    n = max(WINDOW_SAMPLES, int(round(duration_s * hz)))
    dt = 1.0 / hz
    t = np.arange(n, dtype=np.float64) * dt
    bw = np.sqrt(hz)

    if kind == "tw":
        v_lo, v_hi, yaw_amp = 1.5, 18.0, 0.42
    else:
        v_lo, v_hi, yaw_amp = 2.0, 28.0, 0.28

    v0 = float(rng.uniform(v_lo, v_hi))
    # ~35% textbook coordinated-turn / constant-yaw windows: speed is
    # observable from |f| and yaw-rate (az ≈ sqrt(g² + (v ψ̇)²) or ay = v ψ̇).
    circle = bool(rng.random() < 0.50)
    if circle:
        speed = np.full(n, v0, dtype=np.float64)
        psi0 = float(rng.choice([-1.0, 1.0]) * rng.uniform(0.12, 0.55 if kind == "tw" else 0.40))
        psi_dot = np.full(n, psi0, dtype=np.float64)
    else:
        speed = np.clip(v0 + _lowband(t, rng, amp=min(2.8, 0.28 * v0), fmax=0.7), 0.0, 40.0)
        if rng.random() < 0.4:
            speed = np.clip(speed + _bump(t, rng, float(rng.uniform(-3.5, 2.8)), (0.5, 1.3)), 0.0, 40.0)
        psi_dot = _lowband(t, rng, amp=yaw_amp, fmax=0.85)
        if rng.random() < 0.75:
            amp = float(rng.choice([-1.0, 1.0]) * rng.uniform(0.12, 0.55))
            psi_dot = psi_dot + _bump(t, rng, amp, (0.45, 1.15))
        # Persistent yaw so |a| and gyro still constrain speed on "free" traces.
        psi_dot = psi_dot + float(rng.choice([-1.0, 1.0]) * rng.uniform(0.08, 0.30))

    a_fwd = np.gradient(speed, dt)

    phi_coord = np.arctan2(speed * psi_dot, G)
    wobble = _lowband(t, rng, amp=float(np.deg2rad(rng.uniform(0.5, 5.0))), fmax=1.2) if kind == "tw" else 0.0
    banking = float(np.deg2rad(rng.uniform(-3.0, 3.0))) if (kind == "tw" and rng.random() < 0.25) else 0.0
    if kind == "car":
        phi = np.zeros_like(speed)
        roll_res = np.zeros_like(speed)
    else:
        phi = np.clip(phi_coord + wobble + banking, -PHI_CLAMP, PHI_CLAMP)
        roll_res = phi - phi_coord
    phi_dot = np.gradient(phi, dt)
    pitch = _lowband(t, rng, amp=float(np.deg2rad(rng.uniform(0.2, 2.5))), fmax=0.4)
    if rng.random() < 0.2:
        pitch = pitch + _bump(t, rng, float(np.deg2rad(rng.uniform(-2.0, 2.0))), (0.8, 1.6))

    # Body gyro [F1]
    gx = phi_dot.copy()
    gy = psi_dot * np.sin(phi)
    gz = psi_dot * np.cos(phi) if kind == "tw" else psi_dot.copy()
    if kind == "car":
        gx = gx + 0.02 * _lowband(t, rng, amp=0.04, fmax=0.5)
        gy = gy + 0.02 * _lowband(t, rng, amp=0.04, fmax=0.5)

    if kind == "tw":
        cphi = np.clip(np.cos(phi), 1e-3, None)
        ax = a_fwd
        ay = np.zeros_like(a_fwd)
        az = G / cphi
    else:
        ax = a_fwd
        ay = speed * psi_dot
        az = np.full_like(a_fwd, G)

    # Small pitch (road grade) leaks g into body-x; model assumes pitch = 0.
    ax = ax - G * np.sin(pitch)
    az = az * np.cos(pitch)

    # MEMS white + IO-VNBD vibration (high band) + slow bias.
    bg = rng.normal(0.0, 0.004, size=3)
    ba = rng.normal(0.0, 0.05, size=3)
    ax = ax + ba[0] + VIB_A * 0.3 * rng.normal(size=n) + ACCEL_ND * bw * rng.normal(size=n)
    ay = ay + ba[1] + VIB_A * 0.4 * rng.normal(size=n) + ACCEL_ND * bw * rng.normal(size=n)
    az = az + ba[2] + VIB_A * rng.normal(size=n) + ACCEL_ND * bw * rng.normal(size=n)
    gx = gx + bg[0] + VIB_W * rng.normal(size=n) + GYRO_ARW * bw * rng.normal(size=n)
    gy = gy + bg[1] + VIB_W * 0.5 * rng.normal(size=n) + GYRO_ARW * bw * rng.normal(size=n)
    gz = gz + bg[2] + VIB_W * 0.4 * rng.normal(size=n) + GYRO_ARW * bw * rng.normal(size=n)

    imu = np.stack([ax, ay, az, gx, gy, gz], axis=1).astype(np.float32)
    return {
        "imu": imu,
        "speed": speed.astype(np.float32),
        "psi_dot": psi_dot.astype(np.float32),
        "roll_res": np.asarray(roll_res, dtype=np.float32),
        "pitch_res": pitch.astype(np.float32),
        "phi": np.asarray(phi, dtype=np.float32),
        "t": t.astype(np.float32),
    }


def _windows_from_trace(tr: dict[str, np.ndarray], kind: VehicleKind, rng: np.random.Generator) -> dict[str, np.ndarray]:
    n = int(tr["imu"].shape[0])
    if n < WINDOW_SAMPLES:
        raise ValueError("trace shorter than one window")
    start = int(rng.integers(0, n - WINDOW_SAMPLES + 1)) if n > WINDOW_SAMPLES else 0
    sl = slice(start, start + WINDOW_SAMPLES)
    # Labels: last sample of the 2.0 s window (odometry-at-now).
    last = start + WINDOW_SAMPLES - 1
    return {
        "imu": tr["imu"][sl],
        "speed": np.float32(tr["speed"][last]),
        "psi_dot": np.float32(tr["psi_dot"][last]),
        "roll_res": np.float32(tr["roll_res"][last]),
        "pitch_res": np.float32(tr["pitch_res"][last]),
        "phi": np.float32(tr["phi"][last]),
        "vehicle": np.int8(1 if kind == "tw" else 0),
    }


def generate_windows(
    n_windows: int = 4096,
    *,
    seed: int = 7,
    tw_frac: float = 0.6,
    hz: float = IMU_HZ_IO_VNBD,
    duration_s: float = 5.0,
) -> WindowBatch:
    """Seeded mix of leaning two-wheeler and car windows."""
    rng = np.random.default_rng(int(seed))
    n_tw = int(round(n_windows * tw_frac))
    n_car = n_windows - n_tw
    kinds: list[VehicleKind] = ["tw"] * n_tw + ["car"] * n_car
    rng.shuffle(kinds)

    imu = np.empty((n_windows, WINDOW_SAMPLES, 6), dtype=np.float32)
    speed = np.empty(n_windows, dtype=np.float32)
    psi_dot = np.empty(n_windows, dtype=np.float32)
    roll_res = np.empty(n_windows, dtype=np.float32)
    pitch_res = np.empty(n_windows, dtype=np.float32)
    phi = np.empty(n_windows, dtype=np.float32)
    vehicle = np.empty(n_windows, dtype=np.int8)

    for i, kind in enumerate(kinds):
        tr = generate_trace(kind, duration_s=duration_s, hz=hz, rng=rng)
        w = _windows_from_trace(tr, kind, rng)
        imu[i] = w["imu"]
        speed[i] = w["speed"]
        psi_dot[i] = w["psi_dot"]
        roll_res[i] = w["roll_res"]
        pitch_res[i] = w["pitch_res"]
        phi[i] = w["phi"]
        vehicle[i] = w["vehicle"]

    return WindowBatch(
        imu=imu,
        speed=speed,
        psi_dot=psi_dot,
        roll_res=roll_res,
        pitch_res=pitch_res,
        phi=phi,
        vehicle=vehicle,
        hz=hz,
        window_s=WINDOW_SECONDS,
    )


if __name__ == "__main__":
    batch = generate_windows(n_windows=8, seed=7)
    print(
        f"windows={len(batch)} shape={batch.imu.shape} "
        f"speed[{batch.speed.min():.2f},{batch.speed.max():.2f}] "
        f"tw={int(batch.vehicle.sum())} car={int((1 - batch.vehicle).sum())}"
    )
