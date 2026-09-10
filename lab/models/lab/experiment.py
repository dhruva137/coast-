"""Declarative experiment config (PHASE_4_TRAINING §4.3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .specs import ArchSpec, FeatureSpec, Objective, experiment_config_dict


@dataclass(frozen=True)
class Experiment:
    """One reproducible leave-file-out (or synthetic) training claim.

    ``folds=None`` means all clean drives when real IO-VNBD is used.
    """

    name: str
    arch: ArchSpec
    objective: Objective
    features: FeatureSpec
    folds: int | None
    epochs: int
    seed: int

    def __post_init__(self) -> None:
        if not self.name or "/" in self.name or "\\" in self.name:
            raise ValueError(f"invalid experiment name: {self.name!r}")
        if self.epochs < 1:
            raise ValueError("epochs must be >= 1")
        if self.folds is not None and self.folds < 1:
            raise ValueError("folds must be >= 1 or None")
        allowed = {"mse", "nll", "huber", "quantile"}
        if self.objective not in allowed:
            raise ValueError(f"objective must be one of {sorted(allowed)}")

    def to_config(self) -> dict[str, Any]:
        return experiment_config_dict(self)
