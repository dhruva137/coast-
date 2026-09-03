"""
AI-IMU / AVNet stub — NHC-constrained integrator for CARS.

This is **not** a bit-faithful reproduction of either paper. It exists so
the lab has a same-input, comparable-output car baseline while IO-VNBD
is still a Git-LFS pointer. Do not quote the 1.10 % / 0.64 % numbers
from a run of this file.

---------------------------------------------------------------------------
What Brossard, Barrau, Bonnabel 2020 actually do  (IEEE T-IV 5(4):585–595)
---------------------------------------------------------------------------
"AI-IMU Dead-Reckoning", code: github.com/mbrossar/ai-imu-dr

* Right-invariant EKF on SE₂(3) (Barrau & Bonnabel): attitude, velocity,
  position, plus IMU biases.
* They do **not** learn the motion. They learn the *noise* of a
  physics constraint. A CNN looks at a window of IMU and outputs the
  covariance of the non-holonomic (NHC) pseudo-measurements
      v_lat ≈ 0 ,  v_up ≈ 0
  (a car cannot slide sideways or fly). The IEKF then treats those as
  observations with the predicted R.
* 1.10 % translational error on KITTI — competitive with stereo/LiDAR
  *on cars*, with an automotive-grade IMU rigidly mounted.

---------------------------------------------------------------------------
What Qian, Lin, Niu, Huang, Li, Guo, Wang, Chen 2025 actually do  (AVNet)
---------------------------------------------------------------------------
"AVNet: learning attitude and velocity … adapting an invariant EKF",
Satell. Navig. 6:15. Code: QDeepOdo + QAIIMUDeadReckoning.

* CNN-GRU regresses data-driven attitude (DDATT) and velocity (DDODO).
* Those, plus a data-driven NHC (DDNHC), are pseudo-measurements in an
  IEKF. A second CNN adapts the measurement covariance.
* 0.4 % relative horizontal error in car parks; 0.64 % over a 578 m
  tunnel (55 s GNSS outage). Phone: Huawei Mate 30 / LSM6DSM.
* Trained at 200 Hz windows of 200 samples. IO-VNBD is **10 Hz**.
  Copying their window math onto IO-VNBD silently destroys the result
  (bible §2 / trap 1). Rigid-mount assumption (trap 2). Cars only (trap 3).

---------------------------------------------------------------------------
What this stub implements
---------------------------------------------------------------------------
A simplified NHC-constrained dead-reckon for a *car*:

1. Integrate body-frame specific force into a body velocity.
2. Pull lateral and vertical body velocity toward 0 (the NHC).
3. Rotate remaining forward speed into ENU and integrate position.
4. A stand-in "CNN covariance adapter": high-band accel energy inflates
   the NHC stiffness. This is a *heuristic*, not a trained network.

It is correct-in-spirit for φ ≈ 0. It is **wrong on two-wheelers**:
NHC in the untilted body frame fights the lean (the specific force is
``[0, 0, g/cos φ]``, which is observationally identical to "upright but
heavier" — F4). The two-wheeler fix is the lean-tilted NHC in the InEKF,
not this file.

Reproduction fidelity is claimed only after:

* ``git lfs pull`` of IO-VNBD, files actually > 1 MB
* 10 Hz window redesign
* trained CNN (Brossard) / CNN-GRU (AVNet) weights
* full IEKF on SE₂(3), not this Euler integrator
"""

from __future__ import annotations

import numpy as np

try:
    from car_style import G, SEED, dt_from_t, integrate_heading_speed, wrap_pi
except ImportError:  # script: python lab/baselines/ai_imu_stub.py
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from car_style import G, SEED, dt_from_t, integrate_heading_speed, wrap_pi


def highband_energy(accel: np.ndarray) -> np.ndarray:
    """
    Cheap stand-in for Brossard's CNN covariance adapter.

    Consecutive differences ≈ high-frequency content. Large values mean
    the NHC is less trustworthy (potholes, a kerb, a gear shift) so we
    *loosen* the lateral-velocity pull. A real CNN would be trained on
    KITTI / IO-VNBD residuals. This is not that.
    """
    a = np.asarray(accel, dtype=np.float64)
    if a.ndim == 1:
        a = a[:, None]
    if len(a) == 0:
        return np.zeros(0, dtype=np.float64)
    d = np.diff(a, axis=0, prepend=a[:1])
    return np.sqrt(np.sum(d * d, axis=1))


def nhc_stiffness(energy: np.ndarray, *, base: float = 0.35, scale: float = 2.5) -> np.ndarray:
    """
    Map high-band energy → NHC blend in (0, 1).

    ``alpha = 1`` would hard-zero v_lat every step (overconfident NHC).
    ``alpha → 0`` leaves the integrated lateral velocity alone.
    Brossard's CNN outputs a *covariance*; we squash to a gain because
    this stub has no Kalman filter.
    """
    e = np.asarray(energy, dtype=np.float64).ravel()
    return base / (1.0 + scale * e)


def integrate_nhc_car(
    t: np.ndarray,
    ax: np.ndarray,
    ay: np.ndarray,
    az: np.ndarray,
    gx: np.ndarray,
    gy: np.ndarray,
    gz: np.ndarray,
    *,
    speed: np.ndarray | None = None,
    x0: float = 0.0,
    y0: float = 0.0,
    yaw0: float = 0.0,
    v_fwd0: float = 0.0,
) -> dict[str, np.ndarray]:
    """
    NHC-constrained integrator for a car (lateral velocity ~ 0).

    Body axes: x forward, y right, z down-ish (phone / ISO-ish). We only
    need a consistent triad: ``ay`` is treated as the lateral channel.

    If ``speed`` is provided (wheel-odometry / DDODO stub / GNSS), it
    replaces the integrated forward speed each step — that is closer to
    AVNet's DDODO pseudo-measurement than to pure IMU integration.

    Returns dict of arrays: x, y, yaw, v_fwd, v_lat, alpha.
    """
    t = np.asarray(t, dtype=np.float64).ravel()
    ax = np.asarray(ax, dtype=np.float64).ravel()
    ay = np.asarray(ay, dtype=np.float64).ravel()
    az = np.asarray(az, dtype=np.float64).ravel()
    gz = np.asarray(gz, dtype=np.float64).ravel()
    n = t.size
    for name, arr in (("ax", ax), ("ay", ay), ("az", az), ("gz", gz)):
        if arr.size != n:
            raise ValueError(f"{name} length {arr.size} != t length {n}")
    # gx, gy unused in this stub (no full attitude). Kept in the signature
    # so the call site can pass the same IMU the other methods see.
    _ = np.asarray(gx, dtype=np.float64)
    _ = np.asarray(gy, dtype=np.float64)

    dt = dt_from_t(t)
    energy = highband_energy(np.column_stack([ax, ay, az]))
    alpha = nhc_stiffness(energy)

    use_speed = None if speed is None else np.asarray(speed, dtype=np.float64).ravel()
    if use_speed is not None and use_speed.size != n:
        raise ValueError("speed must match t")

    x = np.empty(n, dtype=np.float64)
    y = np.empty(n, dtype=np.float64)
    yaw = np.empty(n, dtype=np.float64)
    v_fwd = np.empty(n, dtype=np.float64)
    v_lat = np.empty(n, dtype=np.float64)
    x[0], y[0], yaw[0] = float(x0), float(y0), float(yaw0)
    v_fwd[0] = float(use_speed[0] if use_speed is not None else v_fwd0)
    v_lat[0] = 0.0

    for i in range(1, n):
        dti = float(dt[i])
        yaw[i] = float(wrap_pi(yaw[i - 1] + gz[i - 1] * dti))
        # Specific force along the road: subtract a crude gravity prior
        # on z so a parked car does not "accelerate upward". Not an AHRS.
        a_fwd = float(ax[i - 1])
        a_lat = float(ay[i - 1])
        vf = v_fwd[i - 1] + a_fwd * dti
        vl = v_lat[i - 1] + a_lat * dti
        a = float(alpha[i - 1])
        vl = (1.0 - a) * vl  # NHC: lateral velocity ~ 0
        if use_speed is not None:
            vf = float(use_speed[i - 1])
        vf = max(0.0, vf)
        v_fwd[i] = vf
        v_lat[i] = vl
        # Body (fwd, right) → ENU (east, north), nav yaw.
        east = vf * np.sin(yaw[i - 1]) + vl * np.cos(yaw[i - 1])
        north = vf * np.cos(yaw[i - 1]) - vl * np.sin(yaw[i - 1])
        x[i] = x[i - 1] + east * dti
        y[i] = y[i - 1] + north * dti

    return {
        "x": x,
        "y": y,
        "yaw": yaw,
        "v_fwd": v_fwd,
        "v_lat": v_lat,
        "alpha": alpha,
        "energy": energy,
    }


def integrate_nhc_from_speed(
    t: np.ndarray,
    speed: np.ndarray,
    gz: np.ndarray,
    *,
    x0: float = 0.0,
    y0: float = 0.0,
    yaw0: float = 0.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Degenerate NHC: hard v_lat = 0, yaw from gz, speed from odometry.

    Algebraically identical to ``integrate_heading_speed`` with
    ``yaw_rate = gz``. That is the point — on a car, AI-IMU's motion
    model *is* car-style plus a covariance adapter. The adapter does
    not change the mean if NHC is hard. Kept as a named entry so call
    sites stay explicit about which paper-shaped box they opened.
    """
    return integrate_heading_speed(
        dt_from_t(t), speed, gz, x0=x0, y0=y0, yaw0=yaw0
    )


if __name__ == "__main__":
    rng = np.random.default_rng(SEED)
    n = 200
    hz = 20.0
    t = np.arange(n, dtype=np.float64) / hz
    speed = np.full(n, 10.0)
    gz = np.zeros(n)
    gz[40:80] = 0.4
    ax = np.zeros(n)
    ay = 0.02 * rng.normal(size=n)
    az = np.full(n, G)
    gx = np.zeros(n)
    gy = np.zeros(n)
    out = integrate_nhc_car(t, ax, ay, az, gx, gy, gz, speed=speed)
    print(
        "ai_imu_stub.py  STUB - not a paper reproduction  "
        f"end=({out['x'][-1]:.2f}, {out['y'][-1]:.2f})  "
        f"|v_lat|rms={np.sqrt(np.mean(out['v_lat']**2)):.4f}"
    )
