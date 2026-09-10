"""Honest metrics schema for the training lab.

A run is not allowed to report a win on per-window RMSE alone. Closed-loop is
the product metric; the two disagree in our bake-off data. Metrics always carry
a closed-loop field (value or null + note).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


REQUIRED_METRIC_KEYS = (
    "per_window_rmse_mps",
    "hold_baseline_rmse_mps",
    "rmse_vs_hold_mps",
    "closed_loop_60s_distance_error_m",
    "outage_drift_pct",
    "mount_swap_delta_rmse_mps",
    "params",
    "onnx_size_bytes",
    "on_device_latency_ms",
)


@dataclass
class FoldMetrics:
    """One fold's scored numbers. Nulls are honest absences, not zeros."""

    fold_id: str
    per_window_rmse_mps: float | None = None
    hold_baseline_rmse_mps: float | None = None
    rmse_vs_hold_mps: float | None = None  # model - hold; negative = better
    closed_loop_60s_distance_error_m: float | None = None
    outage_drift_pct: float | None = None
    mount_swap_delta_rmse_mps: float | None = None
    params: int | None = None
    onnx_size_bytes: int | None = None
    on_device_latency_ms: float | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RunMetrics:
    """Aggregate metrics for one experiment directory."""

    experiment: str
    status: str  # "ok" | "skipped" | "dry_run" | "error"
    folds: list[FoldMetrics] = field(default_factory=list)
    # Aggregate (median over folds when present)
    per_window_rmse_mps: float | None = None
    hold_baseline_rmse_mps: float | None = None
    rmse_vs_hold_mps: float | None = None
    closed_loop_60s_distance_error_m: float | None = None
    outage_drift_pct: float | None = None
    mount_swap_delta_rmse_mps: float | None = None
    params: int | None = None
    onnx_size_bytes: int | None = None
    on_device_latency_ms: float | None = None
    # Honesty bookkeeping
    closed_loop_note: str = ""
    win_claims: list[str] = field(default_factory=list)
    disagreement_flags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Closed-loop field must always exist in the contract; fill the note if null.
        if self.closed_loop_60s_distance_error_m is None and not self.closed_loop_note:
            self.closed_loop_note = (
                "closed_loop_60s_distance_error_m is null - not measured this run; "
                "cannot claim a product win from per-window RMSE alone."
            )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Explicit presence of required keys even when null.
        for k in REQUIRED_METRIC_KEYS:
            d.setdefault(k, None)
        return d


class HonestyError(ValueError):
    """Raised when a caller tries to claim a forbidden win."""


def assert_closed_loop_present(metrics: dict[str, Any]) -> None:
    """Every metrics.json must include the closed-loop key (value may be null)."""
    if "closed_loop_60s_distance_error_m" not in metrics:
        raise HonestyError(
            "metrics missing closed_loop_60s_distance_error_m - "
            "required even when null, with a note"
        )
    if (
        metrics.get("closed_loop_60s_distance_error_m") is None
        and not metrics.get("closed_loop_note")
    ):
        raise HonestyError(
            "closed_loop is null without closed_loop_note - "
            "record why it was not measured"
        )


def evaluate_win_claims(
    *,
    per_window_rmse: float | None,
    hold_rmse: float | None,
    closed_loop_err: float | None,
    closed_loop_baseline_err: float | None = None,
) -> tuple[list[str], list[str]]:
    """Return (allowed_claims, disagreement_flags).

    Per-window RMSE beating hold is never enough for a product win claim.
    """
    claims: list[str] = []
    flags: list[str] = []

    beats_hold_pw = (
        per_window_rmse is not None
        and hold_rmse is not None
        and per_window_rmse < hold_rmse
    )
    loses_hold_pw = (
        per_window_rmse is not None
        and hold_rmse is not None
        and per_window_rmse >= hold_rmse
    )

    beats_cl = (
        closed_loop_err is not None
        and closed_loop_baseline_err is not None
        and closed_loop_err < closed_loop_baseline_err
    )
    loses_cl = (
        closed_loop_err is not None
        and closed_loop_baseline_err is not None
        and closed_loop_err >= closed_loop_baseline_err
    )

    if beats_hold_pw and closed_loop_err is None:
        flags.append(
            "per-window RMSE beats hold, but closed-loop was not measured - "
            "NO WIN CLAIM allowed"
        )
    elif beats_hold_pw and beats_cl:
        claims.append("beats hold on per-window RMSE and closed-loop")
    elif beats_hold_pw and loses_cl:
        flags.append(
            "disagreement: per-window beats hold, closed-loop loses - report both"
        )
    elif loses_hold_pw and beats_cl:
        flags.append(
            "disagreement: per-window loses to hold, closed-loop wins - report both "
            "(this pattern appears in the AVNet bake-off)"
        )
        claims.append("closed-loop only (per-window loses to hold)")
    elif loses_hold_pw and loses_cl:
        flags.append("model loses to hold on both per-window and closed-loop")
    elif loses_hold_pw and closed_loop_err is None:
        flags.append(
            "per-window loses to hold; closed-loop not measured - no win claim"
        )

    return claims, flags


def forbid_rmse_only_win(metrics: dict[str, Any]) -> None:
    """Hard gate: refuse to stamp a win that cites only per-window RMSE."""
    assert_closed_loop_present(metrics)
    for claim in metrics.get("win_claims") or []:
        text = str(claim).lower()
        cites_pw = "per-window" in text or "per window" in text
        cites_cl = "closed-loop" in text or "closed loop" in text
        if cites_pw and not cites_cl:
            raise HonestyError(
                f"refusing win claim without closed-loop evidence: {claim!r}"
            )
        if cites_pw and metrics.get("closed_loop_60s_distance_error_m") is None:
            raise HonestyError(
                f"refusing win claim while closed-loop is null: {claim!r}"
            )
