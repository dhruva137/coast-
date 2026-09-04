"""Vibration rejection for phone gyroscope channels before heading integration.

WHY THIS EXISTS
---------------
The pipeline previously integrated the raw gyro channel straight into heading.
Measured against the paired IO-VNBD CAN logs (true vehicle yaw rate at 10 Hz),
that only works on the quiet urban drives:

    file      mean v   gyro std   CAN yaw std   corr(raw)   corr(0.25 Hz LP)
    S-S1       9.4       0.132       0.125        +0.908        +0.976
    S-S3c     13.7       0.115       0.115        +0.947        +0.954
    S-Vta2    11.4       0.326       0.085        +0.206        +0.755
    S-Vw4     18.9       0.349       0.095        +0.244        +0.601
    S-Vtb1    14.8       0.320       0.073        +0.127        +0.276

Wherever the phone's gyro standard deviation runs several times the vehicle's
actual yaw rate, chassis vibration and engine harmonics dominate the channel
and the raw signal carries almost no heading information. Finding F7
(`lab/research/exp7_welch_psd.py`) already measured the separation that makes
this fixable: essentially all vehicle-motion power sits below 2 Hz, with
+29 dB SNR there. Low-passing recovers the yaw signal.

CAUSALITY MATTERS FOR THE CLAIM
-------------------------------
``filtfilt`` is zero-phase but non-causal: it reads future samples. It is
legitimate for offline replay and for establishing a ceiling, but a phone
cannot use it in real time. So this module provides both, and every caller
must record which one it used. The honest number to quote in the submission is
the causal one; the zero-phase number is the upper bound.

ALIASING CAVEAT
---------------
IO-VNBD samples at 10 Hz, so anything above 5 Hz is already folded into the
passband before we see it. No filter can remove that. On a phone we control we
should sample the IMU fast (``SENSOR_DELAY_FASTEST``) and decimate with an
anti-alias filter, rather than sampling at 10 Hz directly.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.signal import butter, filtfilt, lfilter, lfilter_zi

DEFAULT_CUTOFF_HZ = 0.5
DEFAULT_ORDER = 2


def _design(cutoff_hz: float, fs_hz: float, order: int) -> tuple[np.ndarray, np.ndarray]:
    nyquist = 0.5 * fs_hz
    wn = float(np.clip(cutoff_hz / nyquist, 1e-4, 0.99))
    b, a = butter(order, wn, btype="low")
    return b, a


def lowpass_causal(
    x: np.ndarray,
    *,
    cutoff_hz: float = DEFAULT_CUTOFF_HZ,
    fs_hz: float = 10.0,
    order: int = DEFAULT_ORDER,
) -> np.ndarray:
    """Real-time-legal low pass. Introduces group delay; see ``group_delay_s``."""
    x = np.nan_to_num(np.asarray(x, dtype=np.float64), nan=0.0)
    if x.size < 3 * (order + 1):
        return x.copy()
    b, a = _design(cutoff_hz, fs_hz, order)
    zi = lfilter_zi(b, a) * float(x[0])
    y, _ = lfilter(b, a, x, zi=zi)
    return np.asarray(y, dtype=np.float64)


def lowpass_zerophase(
    x: np.ndarray,
    *,
    cutoff_hz: float = DEFAULT_CUTOFF_HZ,
    fs_hz: float = 10.0,
    order: int = DEFAULT_ORDER,
) -> np.ndarray:
    """Offline zero-phase low pass. NOT causal - do not quote as an on-device result."""
    x = np.nan_to_num(np.asarray(x, dtype=np.float64), nan=0.0)
    if x.size < 3 * (order + 1) * 3:
        return x.copy()
    b, a = _design(cutoff_hz, fs_hz, order)
    return np.asarray(filtfilt(b, a, x), dtype=np.float64)


def group_delay_s(
    cutoff_hz: float = DEFAULT_CUTOFF_HZ, order: int = DEFAULT_ORDER
) -> float:
    """Approximate passband group delay of the causal filter, in seconds.

    For a Butterworth low pass the DC group delay is about
    ``order / (2 * pi * cutoff)``. At the defaults that is ~0.64 s, which is a
    real lag in the heading estimate and must be stated alongside any result.
    """
    return float(order / (2.0 * np.pi * max(cutoff_hz, 1e-6)))


def filter_gyro(
    gx: np.ndarray,
    gy: np.ndarray,
    gz: np.ndarray,
    *,
    cutoff_hz: float = DEFAULT_CUTOFF_HZ,
    fs_hz: float = 10.0,
    order: int = DEFAULT_ORDER,
    causal: bool = True,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    """Low-pass all three gyro channels. Returns the channels plus provenance."""
    fn = lowpass_causal if causal else lowpass_zerophase
    out = tuple(
        fn(c, cutoff_hz=cutoff_hz, fs_hz=fs_hz, order=order) for c in (gx, gy, gz)
    )
    meta = {
        "cutoff_hz": float(cutoff_hz),
        "fs_hz": float(fs_hz),
        "order": int(order),
        "causal": bool(causal),
        "group_delay_s": group_delay_s(cutoff_hz, order) if causal else 0.0,
        "note": (
            "causal lfilter, real-time legal"
            if causal
            else "zero-phase filtfilt, OFFLINE CEILING ONLY - not achievable on-device"
        ),
    }
    return out[0], out[1], out[2], meta


def vibration_ratio(gyro_channel: np.ndarray, reference_yaw_rate: np.ndarray) -> float:
    """std(gyro) / std(reference). Above ~2 the channel is vibration-dominated.

    Diagnostic only: it needs a reference the phone does not have at run time.
    Use it when auditing against CAN, not in the live estimator.
    """
    g = np.asarray(gyro_channel, dtype=np.float64)
    r = np.asarray(reference_yaw_rate, dtype=np.float64)
    m = np.isfinite(g) & np.isfinite(r)
    if m.sum() < 100:
        return float("nan")
    denom = float(np.std(r[m]))
    if denom < 1e-9:
        return float("inf")
    return float(np.std(g[m]) / denom)
