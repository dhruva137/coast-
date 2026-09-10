"""Architecture and feature specs for the experiment harness.

Real model bodies live in ``lab/models/arch/`` (Phase 4.4). This package only
declares the swap interface so runs stay declarative and reproducible.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

# Known architecture ids from PHASE_4_TRAINING §4.4. Measured later; listed here
# so configs cannot silently invent names.
ARCH_IDS = (
    "avnet_tiny",
    "tcn",
    "freq_decoupled",
    "eq_canon",
    "resid_hold",
    "seq2one_attn",
    "hold_baseline",  # trivial persistence; smoke / reference only
)

FEATURE_KINDS = (
    "raw",
    "gravity_canonical",
    "freq_decoupled",
)

Objective = Literal["mse", "nll", "huber", "quantile"]


@dataclass(frozen=True)
class ArchSpec:
    """Declarative architecture handle. The harness swaps on ``id`` only."""

    id: str
    params: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.id not in ARCH_IDS:
            raise ValueError(
                f"unknown arch id {self.id!r}; known: {', '.join(ARCH_IDS)}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "params": dict(self.params)}


@dataclass(frozen=True)
class FeatureSpec:
    """Input featurisation. Keep this orthogonal to ``ArchSpec``."""

    kind: str
    params: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in FEATURE_KINDS:
            raise ValueError(
                f"unknown feature kind {self.kind!r}; known: {', '.join(FEATURE_KINDS)}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "params": dict(self.params)}


def specs_to_jsonable(obj: ArchSpec | FeatureSpec) -> dict[str, Any]:
    return obj.to_dict()


def experiment_config_dict(exp: Any) -> dict[str, Any]:
    """Serialize an Experiment-like object without importing circularly."""
    d = asdict(exp) if hasattr(exp, "__dataclass_fields__") else dict(exp)
    # asdict flattens nested dataclasses; keep nested shape explicit.
    if hasattr(exp, "arch"):
        d["arch"] = exp.arch.to_dict()
    if hasattr(exp, "features"):
        d["features"] = exp.features.to_dict()
    return d
