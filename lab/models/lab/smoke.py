"""Dry-run / smoke experiment - synthetic tiny data, honest nulls."""

from __future__ import annotations

import argparse
from pathlib import Path

from .data import io_vnbd_status
from .experiment import Experiment
from .runner import ExperimentRunner, DEFAULT_RESULTS_ROOT
from .specs import ArchSpec, FeatureSpec
from .compare import write_leaderboard


SMOKE_NAME = "smoke_synthetic_hold"


def build_smoke_experiment(
    *,
    name: str = SMOKE_NAME,
    folds: int = 3,
    epochs: int = 1,
    seed: int = 26168,
) -> Experiment:
    return Experiment(
        name=name,
        arch=ArchSpec(id="hold_baseline", params={"blend": 0.15}),
        objective="mse",
        features=FeatureSpec(kind="raw"),
        folds=folds,
        epochs=epochs,
        seed=seed,
    )


def run_smoke(
    *,
    results_root: Path | None = None,
    parallel: int = 2,
    folds: int = 3,
    seed: int = 26168,
    mode: str = "synthetic",
) -> Path:
    """Run the smoke experiment and return its results directory."""
    exp = build_smoke_experiment(folds=folds, seed=seed)
    runner = ExperimentRunner(results_root=results_root)
    metrics = runner.run(exp, parallel=parallel, mode=mode)
    out = runner.out_dir(exp.name)
    write_leaderboard(runner.results_root)
    iov = io_vnbd_status()
    print(f"smoke status={metrics.status}  out={out}")
    print(f"IO-VNBD: {iov['note']}")
    if metrics.disagreement_flags:
        print("honesty flags:")
        for f in metrics.disagreement_flags:
            print(f"  - {f}")
    if not metrics.win_claims:
        print("win claims: (none) - as expected for smoke")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Phase-4 lab smoke: synthetic folds → results/<name>/"
    )
    ap.add_argument("--folds", type=int, default=3)
    ap.add_argument("--parallel", type=int, default=2, help="parallel fold workers")
    ap.add_argument("--seed", type=int, default=26168)
    ap.add_argument(
        "--results-root",
        type=Path,
        default=DEFAULT_RESULTS_ROOT,
        help="defaults to lab/models/results",
    )
    ap.add_argument(
        "--mode",
        choices=("synthetic", "auto", "require_iovnbd"),
        default="synthetic",
        help="synthetic=always tiny data; require_iovnbd=skip with note if missing",
    )
    args = ap.parse_args(argv)
    run_smoke(
        results_root=args.results_root,
        parallel=args.parallel,
        folds=args.folds,
        seed=args.seed,
        mode=args.mode,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
