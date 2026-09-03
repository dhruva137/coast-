"""Headless plotting + JSON helpers for the research lab."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from kinematics import PLOT_DIR, ensure_plot_dir

plt.rcParams.update(
    {
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.grid": True,
        "grid.alpha": 0.35,
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.labelsize": 11,
        "legend.fontsize": 9,
        "figure.dpi": 120,
        "savefig.dpi": 140,
        "savefig.bbox": "tight",
    }
)


def save_plot(fig: plt.Figure, name: str) -> Path:
    ensure_plot_dir()
    path = PLOT_DIR / f"{name}.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def save_json(name: str, payload: dict[str, Any]) -> Path:
    ensure_plot_dir()
    path = PLOT_DIR / f"{name}.json"

    def _conv(o):
        if isinstance(o, np.generic):
            return o.item()
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, Path):
            return str(o)
        raise TypeError(type(o))

    path.write_text(json.dumps(payload, indent=2, default=_conv), encoding="utf-8")
    return path


def rel_err(actual: float, expected: float) -> float:
    if abs(expected) < 1e-18:
        return abs(actual)
    return abs(actual - expected) / abs(expected)
