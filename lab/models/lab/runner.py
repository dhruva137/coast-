"""Experiment runner: leave-file-out / synthetic folds → results/<name>/."""

from __future__ import annotations

import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np

from .data import TinyDrive, io_vnbd_status, make_synthetic_drives
from .experiment import Experiment
from .metrics import (
    FoldMetrics,
    RunMetrics,
    evaluate_win_claims,
    forbid_rmse_only_win,
)

_HERE = Path(__file__).resolve().parent
_MODELS = _HERE.parent
DEFAULT_RESULTS_ROOT = _MODELS / "results"


def _median(xs: list[float | None]) -> float | None:
    vals = [float(x) for x in xs if x is not None and math.isfinite(float(x))]
    if not vals:
        return None
    return float(np.median(np.asarray(vals, dtype=np.float64)))


def _rmse(pred: np.ndarray, truth: np.ndarray) -> float:
    err = pred.astype(np.float64) - truth.astype(np.float64)
    return float(np.sqrt(np.mean(err * err)))


def _hold_baseline(speed: np.ndarray, t_end: np.ndarray) -> np.ndarray:
    """Persistence over ~2.0 s (same idea as run_speed_bakeoff._hold_label)."""
    order = np.argsort(t_end)
    t = t_end[order]
    s = speed[order]
    prev_t = t - 2.0
    idx = np.searchsorted(t, prev_t, side="right") - 1
    idx = np.clip(idx, 0, len(t) - 1)
    hold = s[idx]
    out = np.empty_like(hold)
    out[order] = hold
    return out.astype(np.float32)


def _closed_loop_distance_error(
    pred_speed: np.ndarray,
    truth_speed: np.ndarray,
    *,
    dt: float = 0.2,
    horizon_s: float = 60.0,
) -> tuple[float, float]:
    """Integrate speed error over a synthetic 60 s outage.

    Returns (model_endpoint_err_m, hold_endpoint_err_m) using persistence of the
    first sample as the frozen baseline. Synthetic only - not a field claim.
    """
    n = int(horizon_s / dt)
    n = min(n, len(pred_speed), len(truth_speed))
    if n < 2:
        return float("nan"), float("nan")
    p = pred_speed[:n].astype(np.float64)
    t = truth_speed[:n].astype(np.float64)
    hold = np.full(n, t[0], dtype=np.float64)
    model_pos = np.cumsum(p) * dt
    truth_pos = np.cumsum(t) * dt
    hold_pos = np.cumsum(hold) * dt
    return float(abs(model_pos[-1] - truth_pos[-1])), float(
        abs(hold_pos[-1] - truth_pos[-1])
    )


def score_hold_fold(drive: TinyDrive, *, seed: int) -> FoldMetrics:
    """Smoke scorer: train-fold mean speed vs hold persistence.

    Deliberately weak (mean usually loses to hold on smooth series). Exists only
    to exercise IO, metrics schema, and honesty flags - not to mint a win.
    """
    _ = seed  # reserved for future stochastic scorers
    hold = _hold_baseline(drive.speed, drive.t_end)
    # Leave one synthetic "model": constant = drive mean (floor baseline).
    pred = np.full_like(drive.speed, float(np.mean(drive.speed)))

    pw = _rmse(pred, drive.speed)
    hr = _rmse(hold, drive.speed)
    cl_m, cl_h = _closed_loop_distance_error(pred, drive.speed)
    path_len = float(np.sum(drive.speed[: min(300, len(drive.speed))]) * 0.2)
    drift = 100.0 * cl_m / max(path_len, 1.0)

    return FoldMetrics(
        fold_id=drive.name,
        per_window_rmse_mps=pw,
        hold_baseline_rmse_mps=hr,
        rmse_vs_hold_mps=pw - hr,
        closed_loop_60s_distance_error_m=cl_m if math.isfinite(cl_m) else None,
        outage_drift_pct=drift if math.isfinite(drift) else None,
        mount_swap_delta_rmse_mps=None,
        params=0,
        onnx_size_bytes=None,
        on_device_latency_ms=None,
        notes=[
            "synthetic fold - not IO-VNBD; numbers are harness smoke only",
            f"closed-loop hold baseline endpoint err={cl_h:.3f} m (synthetic)",
            "mount_swap_delta_rmse_mps null - probe not run in smoke",
            "onnx_size_bytes / on_device_latency_ms null - no export in smoke",
        ],
    )


FoldRunner = Callable[[TinyDrive, Experiment], FoldMetrics]


class ExperimentRunner:
    """Run one Experiment and write results/<name>/{config,metrics,summary}."""

    def __init__(
        self,
        results_root: Path | None = None,
        *,
        fold_fn: FoldRunner | None = None,
    ) -> None:
        self.results_root = Path(results_root) if results_root else DEFAULT_RESULTS_ROOT
        self.fold_fn = fold_fn or (
            lambda drive, exp: score_hold_fold(drive, seed=exp.seed)
        )

    def out_dir(self, name: str) -> Path:
        return self.results_root / name

    def run(
        self,
        exp: Experiment,
        *,
        drives: Sequence[TinyDrive] | None = None,
        parallel: int = 1,
        mode: str = "auto",
    ) -> RunMetrics:
        """Execute folds and persist artifacts.

        ``mode``:
          - ``synthetic`` - always use tiny synthetic drives
          - ``require_iovnbd`` - skip with honesty note if corpus missing
          - ``auto`` - synthetic smoke (default for this harness package until
            arch trainers are wired); still records IO-VNBD presence
        """
        out = self.out_dir(exp.name)
        out.mkdir(parents=True, exist_ok=True)

        config = exp.to_config()
        config["runner"] = {
            "mode": mode,
            "parallel": int(parallel),
            "io_vnbd": io_vnbd_status(),
        }
        (out / "config.json").write_text(
            json.dumps(config, indent=2) + "\n", encoding="utf-8"
        )

        iov = io_vnbd_status()
        if mode == "require_iovnbd" and not iov["present"]:
            metrics = RunMetrics(
                experiment=exp.name,
                status="skipped",
                closed_loop_60s_distance_error_m=None,
                closed_loop_note=(
                    "skipped: IO-VNBD missing under data/raw/IO-VNBD; "
                    "closed-loop not measured; no win claimed"
                ),
                notes=[
                    iov["note"],
                    "Re-run with local IO-VNBD or use --mode synthetic for smoke.",
                ],
            )
            self._write_metrics(out, metrics)
            self._write_summary(out, exp, metrics)
            return metrics

        if drives is None:
            n_folds = exp.folds if exp.folds is not None else 3
            drives = make_synthetic_drives(
                n_drives=n_folds, n_windows=64, seed=exp.seed
            )
        else:
            drives = list(drives)
            if exp.folds is not None:
                drives = drives[: exp.folds]

        if not drives:
            metrics = RunMetrics(
                experiment=exp.name,
                status="error",
                closed_loop_60s_distance_error_m=None,
                closed_loop_note="no folds available; closed-loop null",
                notes=["empty drive list"],
            )
            self._write_metrics(out, metrics)
            self._write_summary(out, exp, metrics)
            return metrics

        fold_rows = self._run_folds(exp, drives, parallel=max(1, int(parallel)))

        # Closed-loop baseline comparison for honesty flags (hold persistence).
        pw = _median([f.per_window_rmse_mps for f in fold_rows])
        hr = _median([f.hold_baseline_rmse_mps for f in fold_rows])
        cl = _median([f.closed_loop_60s_distance_error_m for f in fold_rows])
        drift = _median([f.outage_drift_pct for f in fold_rows])

        # Synthetic hold closed-loop: re-score persistence for disagreement flags.
        cl_hold_vals: list[float] = []
        for d in drives:
            hold = _hold_baseline(d.speed, d.t_end)
            _, cl_h = _closed_loop_distance_error(hold, d.speed)
            if math.isfinite(cl_h):
                cl_hold_vals.append(cl_h)
        cl_hold = float(np.median(cl_hold_vals)) if cl_hold_vals else None

        claims, flags = evaluate_win_claims(
            per_window_rmse=pw,
            hold_rmse=hr,
            closed_loop_err=cl,
            closed_loop_baseline_err=cl_hold,
        )

        status = "dry_run" if mode in ("auto", "synthetic") else "ok"
        # Synthetic / dry-run numbers are not product evidence - never mint wins.
        if status == "dry_run":
            if claims:
                flags = list(flags) + [
                    "suppressed synthetic win_claims - dry-run is not a product result"
                ]
            claims = []

        metrics = RunMetrics(
            experiment=exp.name,
            status=status,
            folds=fold_rows,
            per_window_rmse_mps=pw,
            hold_baseline_rmse_mps=hr,
            rmse_vs_hold_mps=(pw - hr) if pw is not None and hr is not None else None,
            closed_loop_60s_distance_error_m=cl,
            outage_drift_pct=drift,
            mount_swap_delta_rmse_mps=None,
            params=fold_rows[0].params if fold_rows else None,
            onnx_size_bytes=None,
            on_device_latency_ms=None,
            closed_loop_note=(
                "closed-loop measured on synthetic 60 s integrate; "
                "not a field / IO-VNBD product number"
                if cl is not None
                else "closed_loop null"
            ),
            win_claims=claims,
            disagreement_flags=flags,
            notes=[
                "Harness smoke / dry-run unless a real fold_fn and IO-VNBD trainer "
                "are plugged in.",
                iov["note"],
                "mount_swap / onnx / latency left null deliberately - not measured.",
            ],
        )

        self._write_metrics(out, metrics)
        self._write_summary(out, exp, metrics)
        return metrics

    def _run_folds(
        self,
        exp: Experiment,
        drives: Sequence[TinyDrive],
        *,
        parallel: int,
    ) -> list[FoldMetrics]:
        if parallel <= 1 or len(drives) == 1:
            return [self.fold_fn(d, exp) for d in drives]

        rows: list[FoldMetrics | None] = [None] * len(drives)

        def _one(i: int, d: TinyDrive) -> tuple[int, FoldMetrics]:
            return i, self.fold_fn(d, exp)

        with ThreadPoolExecutor(max_workers=parallel) as pool:
            futs = [pool.submit(_one, i, d) for i, d in enumerate(drives)]
            for fut in as_completed(futs):
                i, fm = fut.result()
                rows[i] = fm
        return [r for r in rows if r is not None]

    def _write_metrics(self, out: Path, metrics: RunMetrics) -> None:
        payload = metrics.to_dict()
        forbid_rmse_only_win(payload)
        (out / "metrics.json").write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )

    def _write_summary(
        self, out: Path, exp: Experiment, metrics: RunMetrics
    ) -> None:
        lines = [
            f"# Experiment: `{exp.name}`",
            "",
            f"- status: **{metrics.status}**",
            f"- arch: `{exp.arch.id}`",
            f"- objective: `{exp.objective}`",
            f"- features: `{exp.features.kind}`",
            f"- folds: {exp.folds}",
            f"- epochs: {exp.epochs}",
            f"- seed: {exp.seed}",
            "",
            "## Metrics",
            "",
            "| field | value |",
            "|---|---|",
            f"| per-window RMSE (m/s) | {_fmt(metrics.per_window_rmse_mps)} |",
            f"| hold baseline RMSE (m/s) | {_fmt(metrics.hold_baseline_rmse_mps)} |",
            f"| RMSE vs hold (m/s) | {_fmt(metrics.rmse_vs_hold_mps)} |",
            f"| closed-loop 60 s dist err (m) | {_fmt(metrics.closed_loop_60s_distance_error_m)} |",
            f"| outage drift % | {_fmt(metrics.outage_drift_pct)} |",
            f"| mount-swap ΔRMSE | {_fmt(metrics.mount_swap_delta_rmse_mps)} |",
            f"| params | {_fmt(metrics.params)} |",
            f"| ONNX size (bytes) | {_fmt(metrics.onnx_size_bytes)} |",
            f"| on-device latency (ms) | {_fmt(metrics.on_device_latency_ms)} |",
            "",
            f"**Closed-loop note:** {metrics.closed_loop_note}",
            "",
        ]
        if metrics.win_claims:
            lines.append("## Allowed claims")
            lines.append("")
            for c in metrics.win_claims:
                lines.append(f"- {c}")
            lines.append("")
        else:
            lines.extend(["## Allowed claims", "", "- *(none)*", ""])

        if metrics.disagreement_flags:
            lines.append("## Honesty / disagreement flags")
            lines.append("")
            for f in metrics.disagreement_flags:
                lines.append(f"- {f}")
            lines.append("")

        if metrics.notes:
            lines.append("## Notes")
            lines.append("")
            for n in metrics.notes:
                lines.append(f"- {n}")
            lines.append("")

        lines.extend(
            [
                "## Rule",
                "",
                "A run cannot claim a product win from per-window RMSE alone. "
                "Closed-loop must be present (value or null + note).",
                "",
            ]
        )
        (out / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def _fmt(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def run_experiment(
    exp: Experiment,
    *,
    results_root: Path | None = None,
    parallel: int = 1,
    mode: str = "auto",
) -> RunMetrics:
    return ExperimentRunner(results_root=results_root).run(
        exp, parallel=parallel, mode=mode
    )
