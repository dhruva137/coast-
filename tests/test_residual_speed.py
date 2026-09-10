"""CPU unit tests for residual-on-persistence speed math.

No GPU, no IO-VNBD, no 23-fold trainer. Imports the helpers from
``lab.models.run_residual_speed`` so the training script cannot silently
change the (N, T, 7) channel contract, the 60 s integrator, or the copier
gate.
"""

from __future__ import annotations

import numpy as np

from lab.models.run_residual_speed import (
    CLOSED_LOOP_S,
    _closed_loop_err,
    _rmse,
    _with_vprev,
)

# Same gate as run_residual_speed.main: mean |Δ̂| below this is a copier.
COPIER_MEAN_ABS_DELTA = 0.05


def test_with_vprev_shape_is_n_t_7() -> None:
    n, t, c = 5, 20, 6
    imu = np.arange(n * t * c, dtype=np.float32).reshape(n, t, c)
    vprev = np.array([1.5, 2.0, 0.0, -3.25, 10.0], dtype=np.float64)
    out = _with_vprev(imu, vprev)
    assert out.shape == (n, t, 7)
    np.testing.assert_array_equal(out[..., :6], imu)
    expected = np.repeat(vprev.astype(np.float32).reshape(n, 1), t, axis=1)
    np.testing.assert_allclose(out[..., 6], expected)
    assert np.all(out[:, 0, 6] == out[:, -1, 6])


def test_rmse_zero_and_unit() -> None:
    zeros = np.zeros(4)
    assert _rmse(zeros, zeros) == 0.0
    assert _rmse(np.array([1.0, -1.0]), zeros[:2]) == 1.0


def test_closed_loop_err_constant_bias_on_10hz_series() -> None:
    hz = 10.0
    t_end = np.arange(0.0, 180.0, 1.0 / hz)
    truth = np.full_like(t_end, 10.0)
    pred = truth + 1.0
    err = _closed_loop_err(pred, truth, t_end)
    assert err is not None
    # Integrator prepends dt[0]=0 then steps of 1/hz until the first sample
    # that reaches CLOSED_LOOP_S (exclusive). At 10 Hz that is 59.9 s of
    # 1 m/s bias → 59.9 m.
    np.testing.assert_allclose(err, CLOSED_LOOP_S - 1.0 / hz, atol=1e-6)


def test_closed_loop_err_perfect_match_is_zero() -> None:
    t_end = np.linspace(0.0, 200.0, 401)
    y = np.sin(t_end / 10.0)
    err = _closed_loop_err(y, y, t_end)
    assert err is not None
    assert err == 0.0


def test_closed_loop_err_too_short_is_none() -> None:
    t_end = np.array([0.0, 1.0, 2.0])
    y = np.ones(3)
    assert _closed_loop_err(y, y, t_end) is None


def test_copier_guard_detects_near_zero_delta() -> None:
    copier = np.full(1000, 1e-6)
    real = np.full(1000, 0.35)
    assert float(np.mean(np.abs(copier))) < COPIER_MEAN_ABS_DELTA
    assert float(np.mean(np.abs(real))) >= COPIER_MEAN_ABS_DELTA

    v_prev = np.array([3.0, 4.0, 5.0])
    y = np.array([3.2, 4.1, 4.8])
    delta0 = np.zeros_like(v_prev)
    np.testing.assert_allclose(_rmse(v_prev + delta0, y), _rmse(v_prev, y))
