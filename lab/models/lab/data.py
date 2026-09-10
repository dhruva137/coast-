"""Data presence checks and synthetic tiny corpora for smoke runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

_REPO = Path(__file__).resolve().parents[3]
IO_VNBD_ROOT = _REPO / "data" / "raw" / "IO-VNBD"
WINDOW = 20
CHANNELS = 6


@dataclass(frozen=True)
class TinyDrive:
    """Minimal drive-shaped blob for dry-run folds (not real IO-VNBD)."""

    name: str
    imu: np.ndarray  # (N, WINDOW, 6)
    speed: np.ndarray  # (N,)
    t_end: np.ndarray  # (N,)

    def __len__(self) -> int:
        return int(self.speed.shape[0])


def io_vnbd_present() -> bool:
    """True if at least one smartphone CSV is reachable under data/raw/IO-VNBD."""
    if not IO_VNBD_ROOT.is_dir():
        return False
    try:
        next(IO_VNBD_ROOT.rglob("S-*.csv"))
        return True
    except StopIteration:
        return False


def io_vnbd_status() -> dict[str, Any]:
    present = io_vnbd_present()
    n = 0
    if present:
        n = sum(1 for _ in IO_VNBD_ROOT.rglob("S-*.csv"))
    return {
        "path": str(IO_VNBD_ROOT),
        "present": present,
        "n_smartphone_csv": n,
        "note": (
            "IO-VNBD found locally"
            if present
            else "IO-VNBD missing under data/raw/IO-VNBD - real folds skipped"
        ),
    }


def make_synthetic_drives(
    *,
    n_drives: int = 3,
    n_windows: int = 64,
    seed: int = 26168,
) -> list[TinyDrive]:
    """Tiny kinematics-ish windows: speed ≈ integrated |accel| + noise.

    Used only to exercise the harness. Numbers are not product claims.
    """
    rng = np.random.default_rng(seed)
    drives: list[TinyDrive] = []
    for i in range(n_drives):
        # Slow-varying body speed with mild accel correlation.
        t = np.arange(n_windows, dtype=np.float32) * 0.2
        base = 8.0 + 3.0 * np.sin(0.05 * t + i) + rng.normal(0, 0.3, size=n_windows)
        base = np.clip(base, 0.0, None).astype(np.float32)
        imu = rng.normal(0, 0.5, size=(n_windows, WINDOW, CHANNELS)).astype(np.float32)
        # Channel 0 carries a weak speed cue so a trivial linear fit has signal.
        imu[:, -1, 0] = (base / 10.0) + rng.normal(0, 0.05, size=n_windows).astype(
            np.float32
        )
        drives.append(
            TinyDrive(
                name=f"synth-{i}",
                imu=imu,
                speed=base,
                t_end=t.astype(np.float32) + float(WINDOW) / 10.0,
            )
        )
    return drives
