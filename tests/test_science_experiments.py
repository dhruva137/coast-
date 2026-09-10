from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from lab.nav.mapfilter import RoadParticleFilter
from lab.stress.learned_gnss_policy import (
    fit_gain_policy,
    gain_features,
    split_drive_paths,
)
from lab.stress.run_mapfilter_compass_eval import onset_calibrated_compass
from lab.stress.run_transition_latency import (
    _drop_latency_ms,
    _rejoin,
    summarise as summarise_transitions,
)


class _TwoBearingGraph:
    """Two long, disconnected edges for deterministic heading-weight tests."""

    def __init__(self) -> None:
        self.seg_ptr = np.array([0, 1, 2])
        self.seg_len_m = np.array([1000.0, 1000.0])
        self.seg_bearing_deg = np.array([0.0, 90.0])
        self.edge_u = np.array([0, 2])
        self.edge_v = np.array([1, 3])
        self.adj_ptr = np.zeros(5, dtype=int)
        self.adj_edge = np.array([], dtype=int)
        self.n_edges = 2


def test_mapfilter_absolute_heading_reweights_road_hypotheses() -> None:
    pf = RoadParticleFilter(_TwoBearingGraph(), n_particles=4)
    pf.alive = True
    pf.edge[:] = [0, 0, 1, 1]
    pf.s[:] = 10.0
    pf.forward[:] = True
    pf.speed_scale[:] = 1.0
    pf.w[:] = 0.25

    state = pf.step(
        0.0,
        0.0,
        0.1,
        heading_deg=90.0,
        heading_sigma_deg=10.0,
        want_position=False,
    )

    assert state.on_graph
    assert float(pf.w[pf.edge == 1].sum()) > 0.99


def test_compass_calibration_uses_onset_bearing_only() -> None:
    raw = np.array([15.0, 20.0, 25.0, 30.0])
    bearing = np.array([105.0, 110.0, np.nan, 999.0])
    calibrated = onset_calibrated_compass(raw, bearing, onset=2)
    assert calibrated is not None
    np.testing.assert_allclose(calibrated, [100.0, 105.0, 110.0, 115.0])


def test_learned_gain_fits_parameters_and_drive_split_has_no_overlap() -> None:
    rows = []
    targets = []
    for acc in np.linspace(1.0, 30.0, 40):
        rows.append(gain_features(acc, 8.0, 10.0, 1.0))
        targets.append(1.0 / (1.0 + acc / 5.0))
    policy = fit_gain_policy(np.vstack(rows), np.asarray(targets), ridge=0.01)
    low = float(policy.predict(gain_features(2.0, 8.0, 10.0, 1.0))[0])
    high = float(policy.predict(gain_features(25.0, 8.0, 10.0, 1.0))[0])
    assert policy.n_training_examples == 40
    assert any(abs(value) > 1e-3 for value in policy.coefficients)
    assert low > high

    paths = [Path(f"S-{i}.csv") for i in range(8)]
    train, evaluation = split_drive_paths(paths)
    assert train and evaluation
    assert set(train).isdisjoint(evaluation)
    assert set(train) | set(evaluation) == set(paths)


def test_drop_latency_skips_invalid_timestamp_and_never_returns_nan() -> None:
    t = np.array([0.0, 0.1, 0.1, np.nan, 0.3])
    assert math.isclose(_drop_latency_ms(t, 1) or -1.0, 200.0)
    assert _drop_latency_ms(np.array([0.0, np.nan]), 0) is None


def test_adaptive_rejoin_reduces_visible_jump_against_hard_snap() -> None:
    dt = np.full(300, 0.1)
    gnss = np.column_stack([np.linspace(100.0, 130.0, 300), np.zeros(300)])
    start = np.array([0.0, 0.0])
    hard = _rejoin(start, gnss, dt, "hard_snap", 2.0, initial_cov_m2=2500.0)
    adaptive = _rejoin(start, gnss, dt, "adaptive", 2.0, initial_cov_m2=2500.0)
    hard_jump = np.linalg.norm(np.diff(np.vstack([start, hard]), axis=0), axis=1).max()
    adaptive_jump = np.linalg.norm(
        np.diff(np.vstack([start, adaptive]), axis=0), axis=1
    ).max()
    assert adaptive_jump < hard_jump
    assert np.linalg.norm(adaptive[-1] - gnss[-1]) < 5.0


def test_transition_summary_uses_valid_drop_latency_key() -> None:
    event = {
        "drop_latency_ms": 100.0,
        "dr_offset_at_reacquire_m": 20.0,
        **{
            name: {"reacquire_latency_ms": 500.0, "reacquire_jump_m": 3.0}
            for name in ("hard_snap", "blended", "adaptive")
        },
    }
    summary = summarise_transitions([event])
    assert summary["drop_latency_ms_median"] == 100.0
    assert summary["drop_latency_valid_events"] == 1
