"""Closed-loop AVNet prior for GNSS-denied outage (real IO-VNBD).

Uses ``lab/models/infer.py`` on 20-sample @ 10 Hz windows. Gyro channels fed
to the network match *training* layout (raw Roll, Pitch, Yaw). Vehicle yaw
integration uses the stress-validated ``gz = -Pitch`` unless ``use_net_yaw``.

This is the missing wire between maximize training and ISRO scoring.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np

_STRESS = Path(__file__).resolve().parent
_LAB = _STRESS.parent
_MODELS = _LAB / "models"
for _p in (_STRESS, _LAB, _MODELS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from outage_replay import (  # noqa: E402
    SEED,
)

try:
    from car_style import integrate_heading_speed, wrap_pi
except ImportError:
    from baselines.car_style import integrate_heading_speed, wrap_pi  # type: ignore
_ = wrap_pi  # available for callers

WINDOW = 20


def _load_infer():
    try:
        from models.infer import infer_window, load_model
    except ImportError:
        from infer import infer_window, load_model  # type: ignore
    return infer_window, load_model


def build_train_layout_imu(
    ax: np.ndarray,
    ay: np.ndarray,
    az: np.ndarray,
    gyro_roll_raw: np.ndarray,
    gyro_pitch_raw: np.ndarray,
    gyro_yaw_raw: np.ndarray,
) -> np.ndarray:
    """(N, 6) in the order AVNet-tiny was trained: axyz + roll,pitch,yaw raw."""
    return np.column_stack(
        [
            np.asarray(ax, dtype=np.float64),
            np.asarray(ay, dtype=np.float64),
            np.asarray(az, dtype=np.float64),
            np.asarray(gyro_roll_raw, dtype=np.float64),
            np.asarray(gyro_pitch_raw, dtype=np.float64),
            np.asarray(gyro_yaw_raw, dtype=np.float64),
        ]
    )


def dead_reckon_avnet(
    t: np.ndarray,
    imu_train_layout: np.ndarray,
    vehicle_gz: np.ndarray,
    *,
    x0: float,
    y0: float,
    yaw0: float,
    speed0: float,
    use_net_yaw: bool = False,
    model: Any = None,
    weights: str | Path | None = None,
) -> dict[str, Any]:
    """Integrate AVNet speed (± yaw) through an outage window.

    ``imu_train_layout`` is (N, 6). ``vehicle_gz`` is stress-validated yaw rate
    (already bias-corrected by caller if desired).
    """
    infer_window, load_model = _load_infer()
    net = model
    if net is None:
        net = load_model(weights)

    t = np.asarray(t, dtype=np.float64).ravel()
    imu = np.asarray(imu_train_layout, dtype=np.float64)
    gz = np.asarray(vehicle_gz, dtype=np.float64).ravel()
    n = t.size
    if imu.shape[0] != n or gz.size != n:
        raise ValueError("length mismatch")

    speed = np.full(n, float(speed0), dtype=np.float64)
    psi = gz.copy()
    backends: list[str] = []
    v_prev = float(speed0)

    for i in range(n):
        i0 = max(0, i - WINDOW + 1)
        win = imu[i0 : i + 1]
        if win.shape[0] < 4:
            backends.append("seed")
            speed[i] = v_prev
            continue
        res = infer_window(win, model=net, weights=weights)
        backends.append(res.backend)
        if np.isfinite(res.speed) and res.speed >= 0.0:
            # Causal EMA: trust net, keep continuity, soft-cap vs seed.
            v_hat = float(res.speed)
            v_hat = float(np.clip(v_hat, 0.0, max(2.5 * abs(speed0) + 5.0, 35.0)))
            v_prev = 0.65 * v_hat + 0.35 * v_prev
            speed[i] = v_prev
        else:
            speed[i] = v_prev
        if use_net_yaw and np.isfinite(res.psi_dot):
            # Blend net yaw-rate with bias-corrected phone gz (heading dominates error).
            psi[i] = 0.55 * float(res.psi_dot) + 0.45 * float(gz[i])

    dt = np.zeros(n, dtype=np.float64)
    if n > 1:
        dt[1:] = np.diff(t)
    x, y, yaw = integrate_heading_speed(dt, speed, psi, x0=x0, y0=y0, yaw0=yaw0)
    torch_frac = float(sum(1 for b in backends if b == "torch")) / max(len(backends), 1)
    return {
        "x": x,
        "y": y,
        "yaw": yaw,
        "speed": speed,
        "psi": psi,
        "backend_torch_frac": torch_frac,
        "use_net_yaw": use_net_yaw,
    }
