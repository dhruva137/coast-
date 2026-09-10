"""Small, inspectable learned GNSS trust policy.

The model is ridge regression in logit-gain space.  Its four inputs are all
available online: reported horizontal accuracy, innovation magnitude, predicted
position sigma, and seconds since the previous fix.  Targets use CAN truth only
on training drives.  Evaluation drives are held out by basename.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

FEATURE_NAMES = (
    "log1p_acc_h_m",
    "log1p_innovation_m",
    "log1p_predicted_sigma_m",
    "log1p_fix_age_s",
)


@dataclass(frozen=True)
class LearnedGainPolicy:
    coefficients: tuple[float, ...]
    intercept: float
    feature_mean: tuple[float, ...]
    feature_scale: tuple[float, ...]
    ridge: float
    n_training_examples: int

    def predict(self, features: np.ndarray) -> np.ndarray:
        x = np.atleast_2d(np.asarray(features, dtype=np.float64))
        mean = np.asarray(self.feature_mean)
        scale = np.asarray(self.feature_scale)
        z = (x - mean) / scale
        logits = self.intercept + z @ np.asarray(self.coefficients)
        logits = np.clip(logits, -12.0, 12.0)
        return 1.0 / (1.0 + np.exp(-logits))

    def to_dict(self) -> dict[str, object]:
        out = asdict(self)
        out["feature_names"] = list(FEATURE_NAMES)
        out["model_type"] = "ridge_logit_gain"
        return out


def gain_features(
    acc_h_m: float,
    innovation_m: float,
    predicted_sigma_m: float,
    fix_age_s: float,
) -> np.ndarray:
    values = np.asarray(
        [acc_h_m, innovation_m, predicted_sigma_m, fix_age_s], dtype=np.float64
    )
    values = np.where(np.isfinite(values), np.maximum(values, 0.0), 0.0)
    return np.log1p(values)


def optimal_scalar_gain(
    predicted_xy: np.ndarray,
    measured_xy: np.ndarray,
    truth_xy: np.ndarray,
) -> float:
    """Least-squares scalar gain along the observed GNSS innovation."""
    innovation = np.asarray(measured_xy) - np.asarray(predicted_xy)
    denom = float(innovation @ innovation)
    if not math.isfinite(denom) or denom < 1e-6:
        return 0.0
    target = float((np.asarray(truth_xy) - np.asarray(predicted_xy)) @ innovation / denom)
    return float(np.clip(target, 0.01, 0.99))


def fit_gain_policy(
    features: np.ndarray,
    gains: np.ndarray,
    *,
    ridge: float = 1.0,
) -> LearnedGainPolicy:
    x = np.asarray(features, dtype=np.float64)
    y = np.asarray(gains, dtype=np.float64).reshape(-1)
    if x.ndim != 2 or x.shape[1] != len(FEATURE_NAMES) or x.shape[0] != y.size:
        raise ValueError("features/gains shape mismatch")
    valid = np.isfinite(x).all(axis=1) & np.isfinite(y)
    x, y = x[valid], np.clip(y[valid], 0.01, 0.99)
    if x.shape[0] < len(FEATURE_NAMES) + 2:
        raise ValueError("not enough training examples for learned gain policy")
    mean = x.mean(axis=0)
    scale = x.std(axis=0)
    scale[scale < 1e-8] = 1.0
    z = (x - mean) / scale
    design = np.column_stack([np.ones(z.shape[0]), z])
    target = np.log(y / (1.0 - y))
    penalty = np.eye(design.shape[1]) * float(ridge)
    penalty[0, 0] = 0.0
    params = np.linalg.solve(design.T @ design + penalty, design.T @ target)
    return LearnedGainPolicy(
        coefficients=tuple(float(v) for v in params[1:]),
        intercept=float(params[0]),
        feature_mean=tuple(float(v) for v in mean),
        feature_scale=tuple(float(v) for v in scale),
        ridge=float(ridge),
        n_training_examples=int(x.shape[0]),
    )


def split_drive_paths(
    paths: Sequence[Path],
    *,
    eval_fraction: float = 0.3,
    seed: int = 26168,
) -> tuple[list[Path], list[Path]]:
    """Deterministic drive-level split; no drive contributes to both sides."""
    unique = sorted({Path(path) for path in paths}, key=lambda path: path.name)
    if len(unique) < 2:
        raise ValueError("learned evaluation requires at least two distinct drives")
    scored = []
    for path in unique:
        digest = hashlib.sha256(f"{seed}:{path.name}".encode()).digest()
        scored.append((int.from_bytes(digest[:8], "big") / 2**64, path))
    evaluation = [path for score, path in scored if score < eval_fraction]
    training = [path for score, path in scored if score >= eval_fraction]
    if not evaluation:
        evaluation = [min(scored, key=lambda item: item[0])[1]]
        training = [path for _, path in scored if path not in evaluation]
    if not training:
        training = [max(scored, key=lambda item: item[0])[1]]
        evaluation = [path for _, path in scored if path not in training]
    return training, evaluation
