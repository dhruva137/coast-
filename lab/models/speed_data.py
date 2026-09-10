"""Leave-file-out window builder for the speed bake-off, labelled from CAN.

Why this module exists
----------------------
Older versions of ``lab/datasets/io_vnbd.py`` built windows against the
*smartphone* GNSS speed column. Two problems with that label:

1. It used to be divided by 3.6 on the strength of the ``(Kmh)`` header. The
   column is metres per second; ``lab/stress/load_iovnbd.resolve_speed_unit``
   now settles the unit geometrically against the GNSS polyline length. Every
   speed label produced before that fix was 3.6x too small.
2. Even corrected, the phone holds each GNSS fix for ~9 s (S-S1: 498 unique
   positions across 51 746 rows), so the label is a staircase, not a speed.

IO-VNBD's synchronised release ships a row-aligned ``V-<id>.csv`` per drive
carrying CAN *indicated vehicle speed* at the full 10 Hz. Where that pair
exists we train against it; otherwise we fall back to the corrected phone GNSS
speed and record which was used, per drive, in the checkpoint metadata.

Windows are 2.0 s = 20 samples at IO-VNBD's native 10 Hz. Windows are cached
as ``.npz`` because parsing ~220 MB of CSV per fold would dominate runtime.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

_REPO = Path(__file__).resolve().parents[2]
_STRESS = _REPO / "lab" / "stress"
if str(_STRESS) not in sys.path:
    sys.path.insert(0, str(_STRESS))

from load_iovnbd import (  # noqa: E402
    attach_vehicle_truth,
    find_smartphone_csvs,
    load_smartphone_csv,
)

WINDOW_SAMPLES = 20
IMU_HZ = 10.0
WINDOW_SECONDS = WINDOW_SAMPLES / IMU_HZ
DEFAULT_STRIDE = 2  # 0.2 s hop
IMU_AXES = ("ax", "ay", "az", "gx", "gy", "gz")
IMU_UNITS = ("m/s^2", "m/s^2", "m/s^2", "rad/s", "rad/s", "rad/s")
CAN_LABELS = ("indicated_vehicle_speed_mps", "yaw_rate_rad_s")
CACHE_DIR = Path(__file__).resolve().parent / "results" / "speed_bakeoff" / "cache"
CACHE_VERSION = 4  # v4 adds CAN yaw-rate labels


@dataclass(frozen=True)
class DriveWindows:
    """Every 2.0 s window of one drive, plus the label and its provenance."""

    name: str
    imu: np.ndarray  # (N, 20, 6) float32 - ax, ay, az, gx, gy, gz (SI)
    speed: np.ndarray  # (N,) float32 - label at the window's last sample
    t_end: np.ndarray  # (N,) float32 - seconds since drive start
    label_source: str  # "can_10hz" | "phone_gnss"
    n_rows: int
    hz_est: float
    speed_unit_decision: str
    speed_unit_ratio: float
    csv_path: str
    yaw_rate: np.ndarray | None = None  # (N,) CAN yaw rate, rad/s

    def __len__(self) -> int:
        return int(self.imu.shape[0])

    def summary(self) -> dict[str, Any]:
        return {
            "drive": self.name,
            "label_source": self.label_source,
            "n_windows": len(self),
            "n_rows": int(self.n_rows),
            "hz_est": round(float(self.hz_est), 3),
            "speed_unit_decision": self.speed_unit_decision,
            "speed_unit_ratio": round(float(self.speed_unit_ratio), 4),
            "mean_speed_mps": round(float(np.mean(self.speed)), 3),
            "max_speed_mps": round(float(np.max(self.speed)), 3),
            "frac_stopped": round(float(np.mean(self.speed < 0.5)), 4),
            "duration_s": round(float(self.t_end[-1] - self.t_end[0]), 1),
            "has_can_yaw_rate": self.yaw_rate is not None,
        }


def _windows_from_arrays(
    imu_rows: np.ndarray,
    speed_rows: np.ndarray,
    t_rows: np.ndarray,
    *,
    stride: int,
    yaw_rate_rows: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray | None]:
    """Stride a sliding view over the drive; label is the window's last sample.

    The last sample is the causal choice: on the phone the network sees the
    trailing 2.0 s and must report the speed *now*, not the window centre.
    """
    n = int(imu_rows.shape[0])
    if n < WINDOW_SAMPLES:
        return (
            np.empty((0, WINDOW_SAMPLES, 6), np.float32),
            np.empty(0, np.float32),
            np.empty(0, np.float32),
            None if yaw_rate_rows is None else np.empty(0, np.float32),
        )
    starts = np.arange(0, n - WINDOW_SAMPLES + 1, stride, dtype=np.int64)
    idx = starts[:, None] + np.arange(WINDOW_SAMPLES, dtype=np.int64)[None, :]
    imu = imu_rows[idx]  # (N, 20, 6)
    last = starts + WINDOW_SAMPLES - 1
    speed = speed_rows[last]
    t_end = t_rows[last]
    yaw_rate = None if yaw_rate_rows is None else yaw_rate_rows[last]
    # Drop windows with any non-finite IMU sample or a non-finite label.
    ok = np.isfinite(imu).all(axis=(1, 2)) & np.isfinite(speed)
    if yaw_rate is not None:
        ok &= np.isfinite(yaw_rate)
    filtered_yaw_rate = None
    if yaw_rate is not None:
        filtered_yaw_rate = np.ascontiguousarray(yaw_rate[ok], dtype=np.float32)
    return (
        np.ascontiguousarray(imu[ok], dtype=np.float32),
        np.ascontiguousarray(speed[ok], dtype=np.float32),
        np.ascontiguousarray(t_end[ok], dtype=np.float32),
        filtered_yaw_rate,
    )


def build_drive_windows(path: Path | str, *, stride: int = DEFAULT_STRIDE) -> DriveWindows:
    """Parse one S-*.csv (plus its V-*.csv if present) into labelled windows."""
    path = Path(path)
    data = attach_vehicle_truth(load_smartphone_csv(path))
    imu_rows = np.column_stack(
        [data["ax"], data["ay"], data["az"], data["gx"], data["gy"], data["gz"]]
    ).astype(np.float32)
    if data.get("truth_source") == "can_10hz":
        n = int(data["can_n"])
        label = np.asarray(data["can_speed_mps"], dtype=np.float32)[:n]
        yaw_rate_rows = np.asarray(data["can_yaw_rate_rad_s"], dtype=np.float32)[:n]
        imu_rows = imu_rows[:n]
        t_rows = np.asarray(data["t_s"], dtype=np.float32)[:n]
        label_source = "can_10hz"
    else:
        label = np.asarray(data["speed_mps"], dtype=np.float32)
        yaw_rate_rows = None
        t_rows = np.asarray(data["t_s"], dtype=np.float32)
        label_source = "phone_gnss"
    imu, speed, t_end, yaw_rate = _windows_from_arrays(
        imu_rows,
        label,
        t_rows,
        stride=stride,
        yaw_rate_rows=yaw_rate_rows,
    )
    unit = data.get("speed_unit", {}) or {}
    return DriveWindows(
        name=path.stem,
        imu=imu,
        speed=speed,
        t_end=t_end,
        label_source=label_source,
        n_rows=int(data["n"]),
        hz_est=float(data["hz_est"]),
        speed_unit_decision=str(unit.get("decision", "unknown")),
        speed_unit_ratio=float(unit.get("ratio", float("nan"))),
        csv_path=str(path),
        yaw_rate=yaw_rate,
    )


def _cache_path(name: str, stride: int) -> Path:
    return CACHE_DIR / f"{name}_s{stride}_v{CACHE_VERSION}.npz"


def load_drive_windows(
    path: Path | str,
    *,
    stride: int = DEFAULT_STRIDE,
    use_cache: bool = True,
) -> DriveWindows:
    """Cached ``build_drive_windows``. Cache is keyed on name+stride+version."""
    path = Path(path)
    cache = _cache_path(path.stem, stride)
    if use_cache and cache.is_file():
        with np.load(cache, allow_pickle=False) as z:
            cached_yaw = None
            if "yaw_rate" in z.files:
                yaw_rate = z["yaw_rate"]
                if yaw_rate.size:
                    cached_yaw = yaw_rate
            return DriveWindows(
                name=str(z["name"]),
                imu=z["imu"],
                speed=z["speed"],
                t_end=z["t_end"],
                label_source=str(z["label_source"]),
                n_rows=int(z["n_rows"]),
                hz_est=float(z["hz_est"]),
                speed_unit_decision=str(z["speed_unit_decision"]),
                speed_unit_ratio=float(z["speed_unit_ratio"]),
                csv_path=str(z["csv_path"]),
                yaw_rate=cached_yaw,
            )
    dw = build_drive_windows(path, stride=stride)
    if use_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            cache,
            name=dw.name,
            imu=dw.imu,
            speed=dw.speed,
            t_end=dw.t_end,
            label_source=dw.label_source,
            n_rows=dw.n_rows,
            hz_est=dw.hz_est,
            speed_unit_decision=dw.speed_unit_decision,
            speed_unit_ratio=dw.speed_unit_ratio,
            csv_path=dw.csv_path,
            yaw_rate=dw.yaw_rate if dw.yaw_rate is not None else np.empty(0, np.float32),
        )
    return dw


def load_corpus(
    *,
    stride: int = DEFAULT_STRIDE,
    can_only: bool = True,
    min_windows: int = 500,
    names: Sequence[str] | None = None,
    verbose: bool = True,
) -> list[DriveWindows]:
    """Load every usable drive. ``can_only`` keeps drives with a CAN pair.

    ``can_only=True`` is the honest default for a speed bake-off: mixing a
    10 Hz CAN label with a 0.1 Hz staircase label in the same training set
    would make the fold-to-fold numbers incomparable.
    """
    drives: list[DriveWindows] = []
    paths = find_smartphone_csvs()
    if names is not None:
        wanted = {n.lower() for n in names}
        paths = [p for p in paths if p.stem.lower() in wanted or p.name.lower() in wanted]
    for p in paths:
        try:
            dw = load_drive_windows(p, stride=stride)
        except Exception as exc:  # noqa: BLE001 - a broken drive must not kill the sweep
            if verbose:
                print(f"  skip {p.name}: {exc}")
            continue
        if can_only and dw.label_source != "can_10hz":
            continue
        if len(dw) < min_windows:
            if verbose:
                print(f"  skip {p.name}: only {len(dw)} windows")
            continue
        drives.append(dw)
        if verbose:
            s = dw.summary()
            print(
                f"  {s['drive']:<10} {s['label_source']:<10} "
                f"n={s['n_windows']:>7}  mean={s['mean_speed_mps']:>5.2f} m/s  "
                f"max={s['max_speed_mps']:>5.2f}  stop={s['frac_stopped']:.2f}  "
                f"unit={s['speed_unit_decision']}({s['speed_unit_ratio']:.2f})"
            )
    return drives


def stack(drives: Iterable[DriveWindows]) -> tuple[np.ndarray, np.ndarray]:
    """Concatenate drives into ``(imu, speed)`` for a training split."""
    ds = list(drives)
    if not ds:
        raise ValueError("no drives to stack")
    return (
        np.concatenate([d.imu for d in ds], axis=0),
        np.concatenate([d.speed for d in ds], axis=0),
    )


def is_clean_drive(drive: DriveWindows) -> bool:
    """Whether a drive is suitable for final CAN-supervised training."""
    return (
        drive.label_source == "can_10hz"
        and drive.yaw_rate is not None
        and 0.8 <= drive.speed_unit_ratio <= 1.25
        and float(np.mean(drive.speed)) >= 2.0
    )


def clean_drives(drives: Iterable[DriveWindows]) -> list[DriveWindows]:
    """Keep moving drives with trustworthy 10 Hz CAN speed and yaw labels."""
    return [drive for drive in drives if is_clean_drive(drive)]


if __name__ == "__main__":
    corpus = load_corpus()
    total = sum(len(d) for d in corpus)
    print(f"\n{len(corpus)} drives, {total} windows @ {WINDOW_SECONDS:.1f} s")
