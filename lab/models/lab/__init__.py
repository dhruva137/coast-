"""Honest experiment harness for Phase 4 model design (§4.3).

Core contract: declarative Experiment → leave-file-out / synthetic folds →
``lab/models/results/<name>/{config.json, metrics.json, summary.md}``.

A run cannot claim a product win from per-window RMSE alone; closed-loop must
be present in metrics (value or null + note).
"""

from .compare import collect_runs, format_table, write_leaderboard
from .experiment import Experiment
from .metrics import (
    FoldMetrics,
    HonestyError,
    RunMetrics,
    evaluate_win_claims,
    forbid_rmse_only_win,
)
from .runner import ExperimentRunner, run_experiment
from .smoke import build_smoke_experiment, run_smoke
from .specs import ARCH_IDS, ArchSpec, FEATURE_KINDS, FeatureSpec

__all__ = [
    "ARCH_IDS",
    "ArchSpec",
    "Experiment",
    "ExperimentRunner",
    "FEATURE_KINDS",
    "FeatureSpec",
    "FoldMetrics",
    "HonestyError",
    "RunMetrics",
    "build_smoke_experiment",
    "collect_runs",
    "evaluate_win_claims",
    "forbid_rmse_only_win",
    "format_table",
    "run_experiment",
    "run_smoke",
    "write_leaderboard",
]
