"""CLI: ``python -m lab.models.lab smoke|compare``."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="python -m lab.models.lab")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_smoke = sub.add_parser("smoke", help="synthetic dry-run experiment")
    p_smoke.add_argument("--folds", type=int, default=3)
    p_smoke.add_argument("--parallel", type=int, default=2)
    p_smoke.add_argument("--seed", type=int, default=26168)
    p_smoke.add_argument("--results-root", type=str, default=None)
    p_smoke.add_argument(
        "--mode",
        choices=("synthetic", "auto", "require_iovnbd"),
        default="synthetic",
    )

    p_cmp = sub.add_parser("compare", help="build leaderboard from results/")
    p_cmp.add_argument("--results-root", type=str, default=None)
    p_cmp.add_argument("--out", type=str, default=None)

    args = ap.parse_args(argv)

    if args.cmd == "smoke":
        from pathlib import Path

        from .smoke import run_smoke
        from .runner import DEFAULT_RESULTS_ROOT

        root = Path(args.results_root) if args.results_root else DEFAULT_RESULTS_ROOT
        run_smoke(
            results_root=root,
            parallel=args.parallel,
            folds=args.folds,
            seed=args.seed,
            mode=args.mode,
        )
        return 0

    if args.cmd == "compare":
        from pathlib import Path

        from .compare import write_leaderboard
        from .runner import DEFAULT_RESULTS_ROOT

        root = Path(args.results_root) if args.results_root else DEFAULT_RESULTS_ROOT
        out = Path(args.out) if args.out else None
        print(write_leaderboard(root, out_path=out))
        return 0

    ap.error(f"unknown command {args.cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
