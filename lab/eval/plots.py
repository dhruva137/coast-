"""
SIH26168 evaluation figures.

Three plots, matplotlib only, written under ``lab/eval/figures/``:

1. trajectory overlay  — ground truth vs estimate (equal aspect)
2. error vs time       — |p_est − p_gt| 
3. error CDF           — percentile tails, not means
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

_EVAL = Path(__file__).resolve().parent
if str(_EVAL) not in sys.path:
    sys.path.insert(0, str(_EVAL))

from metrics import error_cdf, position_errors  # noqa: E402

FIGURES = _EVAL / "figures"


def _use_agg() -> None:
    import matplotlib

    matplotlib.use("Agg")


def _xy(points: np.ndarray) -> np.ndarray:
    p = np.asarray(points, dtype=np.float64)
    if p.ndim != 2 or p.shape[1] < 2:
        raise ValueError(f"expected (N, 2), got {p.shape}")
    return p[:, :2]


def plot_trajectory(
    gt: np.ndarray,
    est: np.ndarray,
    path: Path,
    *,
    est_label: str = "estimate",
    title: str = "Trajectory overlay",
) -> Path:
    _use_agg()
    import matplotlib.pyplot as plt

    g = _xy(gt)
    e = _xy(est)
    fig, ax = plt.subplots(figsize=(7.2, 6.4))
    ax.plot(g[:, 0], g[:, 1], color="#1d4ed8", lw=2.0, label="ground truth")
    ax.plot(e[:, 0], e[:, 1], color="#dc2626", lw=1.6, ls="--", label=est_label)
    if len(g):
        ax.scatter(g[0, 0], g[0, 1], c="#16a34a", s=42, zorder=3, label="start")
        ax.scatter(g[-1, 0], g[-1, 1], c="#111827", s=36, marker="x", zorder=3, label="gt end")
    if len(e):
        ax.scatter(e[-1, 0], e[-1, 1], c="#dc2626", s=36, marker="x", zorder=3, label="est end")
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_xlabel("east (m)")
    ax.set_ylabel("north (m)")
    ax.set_title(title)
    ax.legend(loc="best", frameon=True, fontsize=8)
    ax.grid(True, alpha=0.35)
    fig.tight_layout()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def plot_error_vs_time(
    t: np.ndarray,
    est: np.ndarray,
    gt: np.ndarray,
    path: Path,
    *,
    title: str = "Position error vs time",
) -> Path:
    _use_agg()
    import matplotlib.pyplot as plt

    err = position_errors(est, gt)
    n = len(err)
    t = np.asarray(t, dtype=np.float64).ravel()
    if t.size >= n:
        tt = t[:n]
    else:
        tt = np.arange(n, dtype=np.float64)
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    ax.plot(tt, err, color="#7c3aed", lw=1.5)
    ax.set_xlabel("time (s)")
    ax.set_ylabel("|p_est − p_gt| (m)")
    ax.set_title(title)
    ax.grid(True, alpha=0.35)
    fig.tight_layout()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def plot_error_cdf(
    errors: np.ndarray,
    path: Path,
    *,
    title: str = "Position-error CDF",
) -> Path:
    _use_agg()
    import matplotlib.pyplot as plt

    e = np.asarray(errors, dtype=np.float64).ravel()
    e = e[np.isfinite(e)]
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    if e.size == 0:
        ax.text(0.5, 0.5, "no finite errors", ha="center", va="center")
    else:
        s = np.sort(e)
        p = np.linspace(0.0, 1.0, s.size, endpoint=True)
        ax.plot(s, p, color="#0f766e", lw=2.0)
        marks = error_cdf(s)
        for key, val in marks.items():
            if not np.isfinite(val):
                continue
            pct = float(key[1:]) / 100.0
            ax.axvline(val, color="#94a3b8", lw=0.8, ls=":")
            ax.scatter([val], [pct], c="#0f766e", s=18, zorder=3)
        ax.set_ylim(0.0, 1.02)
    ax.set_xlabel("position error (m)")
    ax.set_ylabel("F(error)")
    ax.set_title(title)
    ax.grid(True, alpha=0.35)
    fig.tight_layout()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def write_figures(
    gt: np.ndarray,
    est: np.ndarray,
    t: np.ndarray,
    *,
    dest: Path | None = None,
    est_label: str = "estimate",
) -> dict[str, str]:
    """Save the three canonical figures. Returns {name: path}."""
    dest = Path(dest) if dest is not None else FIGURES
    dest.mkdir(parents=True, exist_ok=True)
    err = position_errors(est, gt)
    paths = {
        "trajectory": str(
            plot_trajectory(
                gt,
                est,
                dest / "trajectory.png",
                est_label=est_label,
                title="SIH26168 trajectory overlay",
            )
        ),
        "error_vs_time": str(
            plot_error_vs_time(t, est, gt, dest / "error_vs_time.png")
        ),
        "error_cdf": str(plot_error_cdf(err, dest / "error_cdf.png")),
    }
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render §5.9 figures from a synthetic run")
    parser.add_argument("--seed", type=int, default=26168)
    args = parser.parse_args(argv)
    # Local import to avoid a plots↔harness cycle at module load.
    from harness import generate_synthetic_run  # noqa: WPS433

    run = generate_synthetic_run(seed=args.seed)
    paths = write_figures(
        run["gt_xy"],
        run["est_xy"],
        run["t"],
        est_label=run.get("method", "estimate"),
    )
    for name, p in paths.items():
        print(f"{name:16s} {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
