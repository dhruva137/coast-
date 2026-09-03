"""IO-VNBD loader for 10 Hz AVNet-tiny windows.

Official dataset
    https://github.com/onyekpeu/IO-VNBD

Git LFS (required — without it every CSV is a ~130-byte pointer stub)::

    git lfs install && git lfs pull

Expected local path: ``<repo>/data/raw/IO-VNBD/``. This module never downloads.
If that directory is missing or empty, we fall back to ``synthetic_tw``.
If a CSV is present but ≤ 1 MB (or is a Git LFS pointer), we raise
``IoVnbdLfsError`` instead of silently training on stubs.

IO-VNBD is 10 Hz. Windows are 2.0 s → 20 samples (not AVNet's 200 @ 200 Hz).
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

try:
    from .log_schema import IMU_HZ_IO_VNBD, WINDOW_SAMPLES
    from .synthetic_tw import WindowBatch, generate_windows
except ImportError:
    from log_schema import IMU_HZ_IO_VNBD, WINDOW_SAMPLES  # type: ignore
    from synthetic_tw import WindowBatch, generate_windows  # type: ignore

LFS_MIN_BYTES = 1_000_000
DEFAULT_REL = Path("data") / "raw" / "IO-VNBD"
LFS_HINT = (
    "IO-VNBD CSV looks like a Git LFS pointer stub (or is otherwise ≤ 1 MB). "
    "Install LFS and pull the real blobs before training on this path:\n"
    "    git lfs install && git lfs pull\n"
    "Verify any CSV is > 1 MB before trusting it. "
    "See https://github.com/onyekpeu/IO-VNBD"
)

# Fuzzy header tokens → our 6-axis + labels. IO-VNBD smartphone tables use
# "Gyroscope (Yaw|Pitch|Roll)" and "GPS speed" in km/h.
_ALIASES: dict[str, tuple[str, ...]] = {
    "ax": ("accelerometer x", "accel_x", "acc_x", "accx", "ax", "accx[m/s2]", "longitudinal acceleration"),
    "ay": ("accelerometer y", "accel_y", "acc_y", "accy", "ay", "accy[m/s2]", "lateral acceleration"),
    "az": ("accelerometer z", "accel_z", "acc_z", "accz", "az", "accz[m/s2]"),
    "gx": ("gyroscope (roll)", "gyro_x", "gyrox", "gx", "roll rate", "rollrate", "wx"),
    "gy": ("gyroscope (pitch)", "gyro_y", "gyroy", "gy", "pitch rate", "pitchrate", "wy"),
    "gz": ("gyroscope (yaw)", "gyro_z", "gyroz", "gz", "yaw rate", "yawrate", "yaw_rate", "wz"),
    "speed": ("gps speed", "speed", "velocity", "vf", "gps_speed", "veh_speed"),
    "bearing": ("gps orientation", "bearing", "heading", "course", "gps heading", "orientation (yaw)"),
    "lat": ("gps latitude", "latitude", "lat"),
    "lon": ("gps longitude", "longitude", "lon", "lng"),
    "t": ("time since start", "timestamp", "time", "t", "t_ns", "gps time", "millis"),
}


class IoVnbdLfsError(RuntimeError):
    """CSV on disk is an LFS pointer stub or otherwise unusably small."""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_raw_dir() -> Path:
    return repo_root() / DEFAULT_REL


def _norm(name: str) -> str:
    s = name.strip().lower()
    for ch in "[](){}":
        s = s.replace(ch, " ")
    s = s.replace("_", " ").replace("-", " ")
    return " ".join(s.split())


def _is_lfs_pointer(path: Path) -> bool:
    try:
        size = path.stat().st_size
    except OSError:
        return False
    if size > 1024:
        return False
    try:
        head = path.read_text(encoding="utf-8", errors="ignore")[:240]
    except OSError:
        return False
    h = head.lower()
    return "git-lfs" in h or head.startswith("version https://git-lfs")


def verify_csv_not_lfs_stub(path: Path, min_bytes: int = LFS_MIN_BYTES) -> None:
    """Raise IoVnbdLfsError unless ``path`` is a real CSV larger than 1 MB."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    size = path.stat().st_size
    if _is_lfs_pointer(path) or size <= min_bytes:
        raise IoVnbdLfsError(
            f"{path} is {size} bytes (need > {min_bytes}). {LFS_HINT}"
        )


def _map_header(header: list[str]) -> dict[str, int]:
    norms = [_norm(h) for h in header]
    found: dict[str, int] = {}
    for key, aliases in _ALIASES.items():
        for i, n in enumerate(norms):
            if n in aliases or n.replace(" ", "") in {a.replace(" ", "") for a in aliases}:
                found[key] = i
                break
            # substring fallback for "Accelerometer X (m/s^2)"
            if any(a in n for a in aliases if len(a) > 3):
                found[key] = i
                break
    return found


def _col_unit_is_kmh(header_cell: str) -> bool:
    n = _norm(header_cell)
    return "km" in n and "h" in n.replace(" ", "")


def parse_generic_csv(path: Path) -> dict[str, np.ndarray]:
    """Read a smartphone / ECU CSV into SI arrays. Requires size > 1 MB."""
    verify_csv_not_lfs_stub(path)
    with path.open("r", newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        header = next(reader)
        idx = _map_header(header)
        need = ("ax", "ay", "az", "gx", "gy", "gz")
        missing = [k for k in need if k not in idx]
        if missing:
            raise ValueError(f"{path.name}: cannot map IMU columns {missing} from {header[:24]}")
        rows: list[list[float]] = []
        for raw in reader:
            if len(raw) < len(header):
                continue
            try:
                rec = [float(raw[idx[k]]) for k in need]
            except (ValueError, IndexError):
                continue
            speed = float(raw[idx["speed"]]) if "speed" in idx else float("nan")
            bearing = float(raw[idx["bearing"]]) if "bearing" in idx else float("nan")
            t = float(raw[idx["t"]]) if "t" in idx else float(len(rows))
            rows.append(rec + [speed, bearing, t])
    if len(rows) < WINDOW_SAMPLES:
        raise ValueError(f"{path.name}: only {len(rows)} usable rows")
    arr = np.asarray(rows, dtype=np.float64)
    imu = arr[:, :6].astype(np.float32)
    speed = arr[:, 6].astype(np.float32)
    bearing = arr[:, 7].astype(np.float32)
    t = arr[:, 8]
    # GPS speed in the smartphone tables is km/h.
    hdr_speed = header[idx["speed"]] if "speed" in idx else ""
    finite = speed[np.isfinite(speed)]
    if _col_unit_is_kmh(hdr_speed) or (finite.size > 10 and float(np.nanmax(np.abs(finite))) > 80.0):
        speed = speed / 3.6
    return {"imu": imu, "speed": speed, "bearing": bearing, "t": t.astype(np.float32)}


def _window_stream(
    imu: np.ndarray,
    speed: np.ndarray,
    bearing: np.ndarray,
    t: np.ndarray,
    *,
    stride: int = 5,
) -> WindowBatch:
    n = int(imu.shape[0])
    starts = list(range(0, n - WINDOW_SAMPLES + 1, stride))
    if not starts:
        raise ValueError("not enough samples to form a 2.0 s window")
    n_w = len(starts)
    out_imu = np.empty((n_w, WINDOW_SAMPLES, 6), dtype=np.float32)
    out_speed = np.empty(n_w, dtype=np.float32)
    out_psi = np.empty(n_w, dtype=np.float32)
    for i, s in enumerate(starts):
        e = s + WINDOW_SAMPLES
        out_imu[i] = imu[s:e]
        last = e - 1
        sp = speed[last]
        out_speed[i] = sp if np.isfinite(sp) else 0.0
        # Yaw-rate label: GNSS heading finite-diff, else body gz.
        if last > 0 and np.isfinite(bearing[last]) and np.isfinite(bearing[last - 1]):
            dt = float(t[last] - t[last - 1])
            if dt <= 0:
                dt = 1.0 / IMU_HZ_IO_VNBD
            # bearing may be degrees
            b1, b0 = float(bearing[last]), float(bearing[last - 1])
            if abs(b1) > 2 * np.pi + 0.2 or abs(b0) > 2 * np.pi + 0.2:
                b1, b0 = np.deg2rad(b1), np.deg2rad(b0)
            d = (b1 - b0 + np.pi) % (2 * np.pi) - np.pi
            out_psi[i] = np.float32(d / dt)
        else:
            out_psi[i] = imu[last, 5]
    zeros = np.zeros(n_w, dtype=np.float32)
    return WindowBatch(
        imu=out_imu,
        speed=out_speed,
        psi_dot=out_psi,
        roll_res=zeros.copy(),
        pitch_res=zeros.copy(),
        phi=zeros.copy(),
        vehicle=np.zeros(n_w, dtype=np.int8),
        hz=IMU_HZ_IO_VNBD,
        window_s=WINDOW_SECONDS,
    )


def discover_csvs(raw_dir: Path) -> list[Path]:
    if not raw_dir.is_dir():
        return []
    files = sorted(p for p in raw_dir.rglob("*.csv") if p.is_file())
    return files


def load_io_vnbd(raw_dir: Path | None = None) -> WindowBatch:
    """Parse every real CSV under the raw dir into 20-sample windows."""
    raw_dir = Path(raw_dir) if raw_dir is not None else default_raw_dir()
    csvs = discover_csvs(raw_dir)
    if not csvs:
        raise FileNotFoundError(f"no CSV files under {raw_dir}")
    pointers = [p for p in csvs if _is_lfs_pointer(p)]
    if pointers:
        raise IoVnbdLfsError(f"{pointers[0]} {LFS_HINT}")
    usable = []
    tiny = []
    for p in csvs:
        try:
            verify_csv_not_lfs_stub(p)
            usable.append(p)
        except IoVnbdLfsError:
            tiny.append(p)
    if not usable:
        sample = tiny[0] if tiny else csvs[0]
        raise IoVnbdLfsError(f"{sample} {LFS_HINT}")
    batches: list[WindowBatch] = []
    for p in usable:
        parsed = parse_generic_csv(p)
        batches.append(
            _window_stream(parsed["imu"], parsed["speed"], parsed["bearing"], parsed["t"])
        )
    imu = np.concatenate([b.imu for b in batches], axis=0)
    return WindowBatch(
        imu=imu,
        speed=np.concatenate([b.speed for b in batches]),
        psi_dot=np.concatenate([b.psi_dot for b in batches]),
        roll_res=np.concatenate([b.roll_res for b in batches]),
        pitch_res=np.concatenate([b.pitch_res for b in batches]),
        phi=np.concatenate([b.phi for b in batches]),
        vehicle=np.concatenate([b.vehicle for b in batches]),
    )


def load_windows(
    raw_dir: Path | None = None,
    *,
    fallback_synthetic: bool = True,
    n_windows: int = 4096,
    seed: int = 7,
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
    return load_io_vnbd(raw_dir), "io-vnbd"


if __name__ == "__main__":
    batch, src = load_windows()
    print(f"source={src} windows={len(batch)} imu={batch.imu.shape} hz={batch.hz}")
