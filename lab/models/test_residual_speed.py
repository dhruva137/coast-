"""Numpy-only checks for residual scheduled-sampling / rollout helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

MODELS = Path(__file__).resolve().parent
if str(MODELS) not in sys.path:
    sys.path.insert(0, str(MODELS))

from run_residual_speed import (  # noqa: E402
    COPIER_ABS_DELTA,
    WINDOW_S,
    _has_history,
    _mix_vprev,
    _predecessor_idx,
    _ss_prob,
    _with_vprev,
)


def test_predecessor_is_two_seconds_earlier() -> None:
    t = np.arange(20, dtype=np.float64) * 0.2  # stride 0.2 s, 4 s of windows
    pred = _predecessor_idx(t)
    assert pred[0] == 0
    # t=2.0 is index 10; 2.0 s earlier is t=0.0, index 0.
    assert t[10] == pytest.approx(2.0)
    assert pred[10] == 0
    assert t[11] == pytest.approx(2.2)
    assert pred[11] == 1


def test_has_history_rejects_clip_to_start() -> None:
    t = np.arange(20, dtype=np.float64) * 0.2
    pred = _predecessor_idx(t)
    hist = _has_history(t, pred)
    assert not hist[0]
    assert not hist[5]  # 1.0 s of lag, below 1.5 s
    assert hist[10]
    assert hist[11]


def test_ss_prob_warmup_then_rises_to_half() -> None:
    probs = [_ss_prob(i, 12, p_max=0.5) for i in range(12)]
    assert probs[:4] == [0.0, 0.0, 0.0, 0.0]
    assert probs[-1] == pytest.approx(0.5)
    assert probs[4] < probs[7] < probs[11]


def test_mix_vprev_teacher_forced_when_p_zero() -> None:
    n = 16
    vpr = np.linspace(5.0, 8.0, n).astype(np.float32)
    delta = np.full(n, 0.25, dtype=np.float32)
    t = np.arange(n, dtype=np.float64) * 0.2
    pred = _predecessor_idx(t)
    hist = _has_history(t, pred)
    rng = np.random.default_rng(0)
    used = _mix_vprev(vpr, delta, pred, hist, p=0.0, rng=rng)
    np.testing.assert_array_equal(used, vpr)


def test_mix_vprev_chains_own_estimate_when_p_one() -> None:
    n = 16
    vpr = np.full(n, 10.0, dtype=np.float32)
    delta = np.ones(n, dtype=np.float32)
    t = np.arange(n, dtype=np.float64) * 0.2
    pred = _predecessor_idx(t)
    hist = _has_history(t, pred)
    rng = np.random.default_rng(0)
    used = _mix_vprev(vpr, delta, pred, hist, p=1.0, rng=rng)
    # First windows have no history: true v_prev. Once history exists, v_prev
    # is the chained estimate from ~2 s earlier, which itself grew by 1 each hop.
    assert used[0] == pytest.approx(10.0)
    assert used[10] == pytest.approx(11.0)  # pred=0 → 10 + 1
    assert used[11] == pytest.approx(11.0)  # pred=1 → 10 + 1


def test_with_vprev_appends_constant_channel() -> None:
    imu = np.zeros((3, 20, 6), dtype=np.float32)
    v = np.array([1.5, 2.5, 3.5], dtype=np.float32)
    out = _with_vprev(imu, v)
    assert out.shape == (3, 20, 7)
    np.testing.assert_allclose(out[:, :, 6], np.repeat(v[:, None], 20, axis=1))


def test_copier_threshold_is_five_cm_per_s() -> None:
    assert COPIER_ABS_DELTA == pytest.approx(0.05)
    assert WINDOW_S == pytest.approx(2.0)
