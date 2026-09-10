"""Compatibility adapter for authoritative IO-VNBD training windows.

Official dataset
    https://github.com/onyekpeu/IO-VNBD

Git LFS (required — without it every CSV is a ~130-byte pointer stub)::

    git lfs install && git lfs pull

Expected local path: ``<repo>/data/raw/IO-VNBD/``. This module never downloads.
If that directory is missing or empty, we fall back to ``synthetic_tw``.
If a CSV is present but ≤ 1 MB (or is a Git LFS pointer), we raise
``IoVnbdLfsError`` instead of silently training on stubs.

Axes, units, CAN labels and windowing are owned by
``lab/stress/load_iovnbd.py`` and ``lab/models/speed_data.py``. This module
keeps the historical ``WindowBatch`` API for callers such as ``train_avnet``;
it must not independently interpret phone CSV headers.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

try:
    from .log_schema import IMU_HZ_IO_VNBD, WINDOW_SAMPLES, WINDOW_SECONDS
    from .synthetic_tw import WindowBatch, generate_windows
except ImportError:
    from log_schema import IMU_HZ_IO_VNBD, WINDOW_SAMPLES, WINDOW_SECONDS  # type: ignore
    from synthetic_tw import WindowBatch, generate_windows  # type: ignore

_REPO = Path(__file__).resolve().parents[2]
_STRESS = _REPO / "lab" / "stress"
_MODELS = _REPO / "lab" / "models"
for _path in (_STRESS, _MODELS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from load_iovnbd import (  # noqa: E402
    IoVnbdLfsError as _AuthoritativeLfsError,
    attach_vehicle_truth,
    find_smartphone_csvs,
    load_smartphone_csv,
    verify_csv_not_lfs_stub as _verify_authoritative_csv,
)
from speed_data import (  # noqa: E402
    DEFAULT_STRIDE,
    DriveWindows,
    load_drive_windows,
)

LFS_MIN_BYTES = 1_000_000
DEFAULT_REL = Path("data") / "raw" / "IO-VNBD"
LFS_HINT = (
    "IO-VNBD CSV looks like a Git LFS pointer stub (or is otherwise ≤ 1 MB). "
    "Install LFS and pull the real blobs before training on this path:\n"
    "    git lfs install && git lfs pull\n"
    "Verify any CSV is > 1 MB before trusting it. "
    "See https://github.com/onyekpeu/IO-VNBD"
)

IoVnbdLfsError = _AuthoritativeLfsError


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_raw_dir() -> Path:
    return repo_root() / DEFAULT_REL


def verify_csv_not_lfs_stub(path: Path, min_bytes: int = LFS_MIN_BYTES) -> None:
    """Delegate LFS validation to the authoritative raw loader."""
    _verify_authoritative_csv(Path(path), min_bytes=min_bytes)


def parse_generic_csv(path: Path) -> dict[str, np.ndarray]:
    """Read a smartphone CSV through the authoritative SI/CAN parser."""
    data = attach_vehicle_truth(load_smartphone_csv(path))
    n = int(data.get("can_n", data["n"]))
    imu = np.column_stack(
        [data["ax"], data["ay"], data["az"], data["gx"], data["gy"], data["gz"]]
    )[:n]
    has_can = data.get("truth_source") == "can_10hz"
    return {
        "imu": np.ascontiguousarray(imu, dtype=np.float32),
        "speed": np.ascontiguousarray(
            data["can_speed_mps"][:n] if has_can else data["speed_mps"][:n],
            dtype=np.float32,
        ),
        "bearing": np.ascontiguousarray(data["bearing_deg"][:n], dtype=np.float32),
        "t": np.ascontiguousarray(data["t_s"][:n], dtype=np.float32),
        "psi_dot": np.ascontiguousarray(
            data["can_yaw_rate_rad_s"][:n] if has_can else data["gz"][:n],
            dtype=np.float32,
        ),
    }


def discover_csvs(raw_dir: Path, *, smartphone_only: bool = True) -> list[Path]:
    if not raw_dir.is_dir():
        return []
    files = sorted(p for p in raw_dir.rglob("*.csv") if p.is_file())
    if smartphone_only:
        smartphone = [p for p in files if p.name.upper().startswith("S-")]
        if smartphone:
            return smartphone
    return files


def _batch_from_drives(drives: list[DriveWindows]) -> WindowBatch:
    """Adapt authoritative drive windows to the legacy AVNet batch API."""
    if not drives:
        raise ValueError("no authoritative IO-VNBD drives produced windows")
    imu = np.concatenate([drive.imu for drive in drives], axis=0)
    speed = np.concatenate([drive.speed for drive in drives], axis=0)
    psi_dot = np.concatenate(
        [
            drive.yaw_rate
            if drive.yaw_rate is not None
            else drive.imu[:, -1, 5]
            for drive in drives
        ],
        axis=0,
    ).astype(np.float32)
    zeros = np.zeros(speed.shape[0], dtype=np.float32)
    return WindowBatch(
        imu=np.ascontiguousarray(imu, dtype=np.float32),
        speed=np.ascontiguousarray(speed, dtype=np.float32),
        psi_dot=psi_dot,
        roll_res=zeros.copy(),
        pitch_res=zeros.copy(),
        phi=zeros.copy(),
        vehicle=np.zeros(speed.shape[0], dtype=np.int8),
        hz=IMU_HZ_IO_VNBD,
        window_s=WINDOW_SECONDS,
    )


def load_io_vnbd(
    raw_dir: Path | None = None,
    *,
    exclude_names: set[str] | frozenset[str] | None = None,
    can_only: bool = True,
) -> WindowBatch:
    """Parse every real CSV under the raw dir into 20-sample windows.

    ``exclude_names``: basename set (e.g. ``{"S-S1.csv"}``) for leave-file-out.
    """
    raw_dir = Path(raw_dir) if raw_dir is not None else default_raw_dir()
    exclude = {n.lower() for n in (exclude_names or ())}
    csvs = discover_csvs(raw_dir)
    if not csvs:
        raise FileNotFoundError(f"no CSV files under {raw_dir}")
    usable = []
    tiny = []
    for p in csvs:
        if p.name.lower() in exclude:
            continue
        try:
            verify_csv_not_lfs_stub(p)
            usable.append(p)
        except IoVnbdLfsError:
            tiny.append(p)
    # Preserve LFS-stub detection above, then use the authoritative discovery
    # policy to deduplicate synchronised/unsynchronised copies.
    preferred = set(find_smartphone_csvs(raw_dir))
    if preferred:
        usable = [path for path in usable if path in preferred]
    if not usable:
        sample = tiny[0] if tiny else csvs[0]
        raise IoVnbdLfsError(f"{sample} {LFS_HINT}")
    if tiny:
        print(f"io_vnbd: skipping {len(tiny)} LFS stub/tiny CSV(s); using {len(usable)}")
    if exclude:
        print(f"io_vnbd: leave-file-out exclude={sorted(exclude)} train_files={len(usable)}")
    drives: list[DriveWindows] = []
    errors: list[str] = []
    for p in usable:
        try:
            drive = load_drive_windows(p, stride=DEFAULT_STRIDE)
            if can_only and drive.label_source != "can_10hz":
                continue
            drives.append(drive)
        except Exception as exc:  # noqa: BLE001 — skip unmappable tables
            errors.append(f"{p.name}: {exc}")
    if not drives:
        raise ValueError("no IO-VNBD tables produced windows:\n" + "\n".join(errors[:8]))
    if errors:
        print(f"io_vnbd: skipped {len(errors)} CSV(s); used {len(drives)}")
    return _batch_from_drives(drives)


def load_windows(
    raw_dir: Path | None = None,
    *,
    fallback_synthetic: bool = True,
    n_windows: int = 4096,
    seed: int = 7,
    exclude_names: set[str] | frozenset[str] | None = None,
) -> tuple[WindowBatch, str]:
    """Load IO-VNBD windows, or synthetic if the dataset directory is absent.

    Returns ``(batch, source)`` where source is ``'io-vnbd'`` or ``'synthetic'``.
    LFS stubs raise — they are not treated as 'missing'.
    """
    raw_dir = Path(raw_dir) if raw_dir is not None else default_raw_dir()
    csvs = discover_csvs(raw_dir)
    if not raw_dir.is_dir() or not csvs:
        if not fallback_synthetic:
            raise FileNotFoundError(
                f"IO-VNBD not found at {raw_dir}. Clone it yourself "
                f"(do not download from this loader) and run:\n"
                f"    git lfs install && git lfs pull"
            )
        return generate_windows(n_windows=n_windows, seed=seed), "synthetic"
    return load_io_vnbd(raw_dir, exclude_names=exclude_names), "io-vnbd"


if __name__ == "__main__":
    batch, src = load_windows()
    print(f"source={src} windows={len(batch)} imu={batch.imu.shape} hz={batch.hz}")
