"""GNSS-supervised vehicle-yaw calibration with calibrated abstention.

The loader owns the audited phone-to-vehicle axis mapping.  This model learns
only scale ``s`` and bias ``b`` for its mapped vehicle-yaw channel from a
GNSS-visible prefix:

    yaw_rate_vehicle = s * gz + b

It must not perform a second axis permutation after the alignment audit.
Weak excitation and temporal validation failures are detected and rejected.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math

import numpy as np
from scipy.signal import butter, sosfiltfilt


@dataclass
class Calibration:
    weights: list[float]
    bias_rps: float
    gps_gyro_lag_s: float
    n_fit: int
    validation_correlation: float
    validation_mae_rps: float
    conformal_q90_rps: float
    axis_norm: float
    excitation_rps: float
    trusted_prefix: bool
    reason: str
    feature_mean: list[float]
    feature_precision: list[list[float]]
    ood_d2_threshold: float

    def to_dict(self) -> dict:
        def finite_or_none(value):
            if isinstance(value, float):
                return value if math.isfinite(value) else None
            if isinstance(value, list):
                return [finite_or_none(item) for item in value]
            if isinstance(value, dict):
                return {key: finite_or_none(item) for key, item in value.items()}
            return value

        return finite_or_none(asdict(self))


def _lowpass(x: np.ndarray, fs: float, cutoff_hz: float = 1.2) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    if x.size < 25 or fs <= 2.5 * cutoff_hz:
        return x.copy()
    sos = butter(3, cutoff_hz, btype="lowpass", fs=fs, output="sos")
    return sosfiltfilt(sos, x, axis=0)


def _robust_ridge(X: np.ndarray, y: np.ndarray, ridge: float = 0.08) -> np.ndarray:
    """Huber IRLS with ridge on axis weights, not on the intercept."""
    A = np.column_stack([X, np.ones(len(X))])
    reg = np.diag([ridge] * X.shape[1] + [1e-8])
    beta = np.linalg.solve(A.T @ A + reg, A.T @ y)
    weights = np.ones(len(y))
    for _ in range(8):
        residual = y - A @ beta
        scale = 1.4826 * np.median(np.abs(residual - np.median(residual))) + 1e-5
        u = np.abs(residual) / (1.5 * scale)
        weights = np.where(u <= 1.0, 1.0, 1.0 / np.maximum(u, 1e-9))
        beta = np.linalg.solve(A.T @ (weights[:, None] * A) + reg, A.T @ (weights * y))
    return beta


def _angle_delta(values: np.ndarray) -> np.ndarray:
    return (np.diff(values) + np.pi) % (2.0 * np.pi) - np.pi


def _integral(t_s: np.ndarray, values: np.ndarray) -> np.ndarray:
    out = np.zeros(len(t_s), dtype=np.float64)
    if len(t_s) > 1:
        dt = np.diff(t_s)
        increments = np.where(
            (dt > 0.0) & (dt < 2.0),
            0.5 * (values[1:] + values[:-1]) * dt,
            0.0,
        )
        out[1:] = np.cumsum(increments)
    return out


def _window_features(
    t_s: np.ndarray,
    integrals: np.ndarray,
    starts: np.ndarray,
    ends: np.ndarray,
    lag_s: float,
) -> np.ndarray:
    shifted_starts = starts + lag_s
    shifted_ends = ends + lag_s
    valid = (
        (shifted_starts >= t_s[0])
        & (shifted_ends <= t_s[-1])
        & (shifted_ends > shifted_starts)
    )
    features = np.full((len(starts), integrals.shape[1]), np.nan)
    for axis in range(integrals.shape[1]):
        start_values = np.interp(shifted_starts[valid], t_s, integrals[:, axis])
        end_values = np.interp(shifted_ends[valid], t_s, integrals[:, axis])
        features[valid, axis] = (
            (end_values - start_values)
            / (shifted_ends[valid] - shifted_starts[valid])
        )
    return features


def _prefix_course_intervals(
    t_s: np.ndarray,
    bearing: np.ndarray,
    speed_mps: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return genuine GPS-orientation update intervals, not held IMU-rate rows."""
    finite = np.isfinite(t_s) & np.isfinite(bearing)
    source_indices = np.flatnonzero(finite)
    if source_indices.size < 3:
        return (np.array([]), np.array([]), np.array([]))
    # The IO-VNBD loader contract is explicit: ``bearing_deg`` is degrees.
    angles = np.unwrap(np.deg2rad(bearing[source_indices]))
    changed = np.ones(len(source_indices), dtype=bool)
    changed[1:] = np.abs(_angle_delta(angles)) > math.radians(1e-4)
    update_indices = source_indices[changed]
    if update_indices.size < 3:
        return (np.array([]), np.array([]), np.array([]))

    update_t = t_s[update_indices]
    update_angles = np.unwrap(np.deg2rad(bearing[update_indices]))
    starts, ends = update_t[:-1], update_t[1:]
    dt = ends - starts
    rates = _angle_delta(update_angles) / dt
    midpoint = 0.5 * (starts + ends)
    finite_speed = np.isfinite(t_s) & np.isfinite(speed_mps)
    if finite_speed.sum() < 2:
        return (np.array([]), np.array([]), np.array([]))
    speeds = np.interp(midpoint, t_s[finite_speed], speed_mps[finite_speed])
    valid = (
        (dt >= 0.05)
        & (dt <= 15.0)
        & np.isfinite(rates)
        & (np.abs(rates) < 1.5)
        & (speeds >= 3.0)
    )
    if not np.any(valid):
        return (np.array([]), np.array([]), np.array([]))
    rates_valid = rates[valid]
    turn_threshold = max(
        math.radians(0.5),
        float(np.quantile(np.abs(rates_valid), 0.35)),
    )
    turns = np.abs(rates_valid) >= turn_threshold
    return starts[valid][turns], ends[valid][turns], rates_valid[turns]


def fit_calibration(
    t_s: np.ndarray,
    gyro_xyz: np.ndarray,
    bearing: np.ndarray,
    speed_mps: np.ndarray,
    *,
    end_idx: int,
    alpha: float = 0.10,
) -> Calibration:
    """Fit only on ``[0, end_idx)`` and calibrate on later GPS updates.

    IO-VNBD repeats each GPS orientation across many 10 Hz IMU rows.  Rates are
    therefore formed only between genuine orientation changes, and gyro
    features are averaged over those same intervals.  Lag is selected on the
    training portion only; all trust metrics come from the later held-out
    prefix portion.
    """
    end = max(0, min(int(end_idx), len(t_s)))
    t = np.asarray(t_s[:end], dtype=np.float64)
    gyro = np.asarray(gyro_xyz[:end], dtype=np.float64)
    speed = np.asarray(speed_mps[:end], dtype=np.float64)
    if end < 80:
        return _rejected("fewer than 80 prefix samples")

    starts, ends, target_all = _prefix_course_intervals(
        t, np.asarray(bearing[:end], dtype=np.float64), speed
    )
    if len(target_all) < 48:
        return _rejected("fewer than 48 prefix turning updates")
    split = int(len(target_all) * 0.75)
    if split < 36 or len(target_all) - split < 12:
        return _rejected("insufficient temporal calibration updates")

    gyro_f = _lowpass(gyro, 1.0 / np.median(np.diff(t)[np.diff(t) > 1e-3]))
    integrals = np.column_stack([_integral(t, gyro_f[:, axis]) for axis in range(3)])
    best: tuple[float, float, np.ndarray] | None = None
    for lag_s in np.arange(-1.0, 1.01, 0.1):
        features = _window_features(t, integrals, starts, ends, float(lag_s))
        train_ok = np.isfinite(features[:split]).all(axis=1)
        if train_ok.sum() < 36:
            continue
        beta_scale = _robust_ridge(
            features[:split][train_ok, 2:3],
            target_all[:split][train_ok],
            ridge=0.005,
        )
        beta_lag = np.array([0.0, 0.0, beta_scale[0], beta_scale[1]])
        fitted = features[:split][train_ok] @ beta_lag[:3] + beta_lag[3]
        corr_lag = (
            abs(float(np.corrcoef(fitted, target_all[:split][train_ok])[0, 1]))
            if np.std(fitted) > 1e-8
            else 0.0
        )
        if best is None or corr_lag > best[0]:
            best = (corr_lag, float(lag_s), beta_lag)
    if best is None:
        return _rejected("insufficient lag-aligned prefix updates")

    _, lag_s, beta = best
    features = _window_features(t, integrals, starts, ends, lag_s)
    cal_ok = np.isfinite(features[split:]).all(axis=1)
    if cal_ok.sum() < 12:
        return _rejected("insufficient held-out prefix updates")
    cal_features = features[split:][cal_ok]
    target = target_all[split:][cal_ok]
    pred = cal_features @ beta[:3] + beta[3]
    corr = float(np.corrcoef(pred, target)[0, 1]) if np.std(pred) > 1e-8 and np.std(target) > 1e-8 else 0.0
    residual = np.abs(target - pred)
    q_level = min(1.0, np.ceil((len(residual) + 1) * (1.0 - alpha)) / len(residual))
    q90 = float(np.quantile(residual, q_level, method="higher"))
    excitation = float(np.std(target))
    axis_norm = float(np.linalg.norm(beta[:3]))

    # OOD operates on per-tick gyro values, so calibrate its feature distribution
    # on per-tick prefix values as well (not on interval-averaged fit features).
    tick_split = max(1, int(len(gyro_f) * 0.75))
    training_ticks = gyro_f[:tick_split]
    mean = np.mean(training_ticks, axis=0)
    cov = np.cov(training_ticks.T) + np.eye(3) * 1e-5
    precision = np.linalg.pinv(cov)
    heldout_ticks = gyro_f[tick_split:]
    heldout_delta = heldout_ticks - mean
    heldout_d2 = np.einsum(
        "ni,ij,nj->n", heldout_delta, precision, heldout_delta
    )
    # Empirical prefix-held-out 99.5% radius: this adapts the Gaussian reference
    # to real phone tails without looking at the forced outage.
    ood_d2_threshold = float(np.quantile(heldout_d2, 0.995, method="higher"))
    reasons = []
    if corr < 0.70:
        reasons.append("held-out prefix correlation < 0.70")
    if excitation < 0.015:
        reasons.append("weak turning excitation")
    # The loader already supplies a rad/s vehicle-yaw channel.  A large
    # rescaling would contradict that audited sensor contract and is a common
    # symptom of a non-transferable prefix fit.
    if not 0.85 <= axis_norm <= 1.15:
        reasons.append("mapped-yaw scale outside [0.85, 1.15]")
    trusted = not reasons
    return Calibration(
        weights=beta[:3].tolist(),
        bias_rps=float(beta[3]),
        gps_gyro_lag_s=lag_s,
        n_fit=int(len(target_all)),
        validation_correlation=corr,
        validation_mae_rps=float(np.mean(residual)),
        conformal_q90_rps=q90,
        axis_norm=axis_norm,
        excitation_rps=excitation,
        trusted_prefix=trusted,
        reason="ok" if trusted else "; ".join(reasons),
        feature_mean=mean.tolist(),
        feature_precision=precision.tolist(),
        ood_d2_threshold=ood_d2_threshold,
    )


def predict_yaw_rate(gyro_xyz: np.ndarray, calibration: Calibration, fs: float = 10.0) -> np.ndarray:
    gyro = _lowpass(np.asarray(gyro_xyz, dtype=np.float64), fs)
    return gyro @ np.asarray(calibration.weights) + calibration.bias_rps


def ood_fraction(gyro_xyz: np.ndarray, calibration: Calibration, fs: float = 10.0) -> float:
    """Fraction beyond the prefix-held-out 99.5% Mahalanobis radius."""
    x = _lowpass(np.asarray(gyro_xyz, dtype=np.float64), fs)
    d = x - np.asarray(calibration.feature_mean)
    p = np.asarray(calibration.feature_precision)
    d2 = np.einsum("ni,ij,nj->n", d, p, d)
    return float(np.mean(d2 > calibration.ood_d2_threshold))


def _rejected(reason: str) -> Calibration:
    return Calibration(
        weights=[0.0, 0.0, 1.0],
        bias_rps=0.0,
        gps_gyro_lag_s=0.0,
        n_fit=0,
        validation_correlation=0.0,
        validation_mae_rps=float("inf"),
        conformal_q90_rps=float("inf"),
        axis_norm=1.0,
        excitation_rps=0.0,
        trusted_prefix=False,
        reason=reason,
        feature_mean=[0.0, 0.0, 0.0],
        feature_precision=np.eye(3).tolist(),
        ood_d2_threshold=12.84,
    )
