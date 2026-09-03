"""Load real IO-VNBD smartphone (S-*.csv) logs into a uniform dict.

Fails loudly on Git LFS pointer stubs (≤ 1 MB). Column names are matched
case-insensitively against the Data-in-Brief / GitHub IO-VNBD headers.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

import numpy as np

LFS_MIN_BYTES = 1_000_000
SESSION_MAX_GAP_S = 5.0
SESSION_MAX_COORD_SPEED_MPS = 80.0
SESSION_ABSOLUTE_JUMP_M = 1_000.0
SESSION_MIN_DURATION_S = 55.0
SESSION_MIN_DISTANCE_M = 100.0
LFS_HINT = (
    "CSV looks like a Git LFS pointer stub (or is ≤ 1 MB). "
    "Run: git lfs install && git lfs pull  inside data/raw/IO-VNBD"
)
SEED = 26168

# Fuzzy header tokens → canonical keys. Matched after normalisation.
_ALIASES: dict[str, tuple[str, ...]] = {
    "lat": ("gps latitude", "latitude", "lat"),
    "lon": ("gps longitude", "longitude", "lon", "lng"),
    "speed": ("gps speed", "speed", "velocity", "vf", "gps_speed"),
    "acc_h": ("gps accuracy", "accuracy", "hdop", "horizontal accuracy", "acc_h"),
    "bearing": (
        "gps orientation",
        "gps heading",
        "bearing",
        "course",
        "orientation yaw",
        "orientation (yaw)",
    ),
    "t": ("time since start", "timestamp", "time", "t", "millis", "gps time"),
    "ax": ("accelerometer x", "accel_x", "acc_x", "accx", "ax"),
    "ay": ("accelerometer y", "accel_y", "acc_y", "accy", "ay"),
    "az": ("accelerometer z", "accel_z", "acc_z", "accz", "az"),
    # Preserve the dataset's semantic labels. They are not vehicle-frame axes:
    # the alignment audit found vehicle yaw = -GYROSCOPE Pitch.
    "gyro_yaw_raw": ("gyroscope yaw", "gyro_z", "gyroz", "gz", "yaw rate", "yawrate", "wz"),
    "gyro_pitch_raw": ("gyroscope pitch", "gyro_y", "gyroy", "gy", "pitch rate", "pitchrate", "wy"),
    "gyro_roll_raw": ("gyroscope roll", "gyro_x", "gyrox", "gx", "roll rate", "rollrate", "wx"),
}


class IoVnbdLfsError(RuntimeError):
    """CSV on disk is an LFS pointer stub or otherwise unusably small."""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_raw_dir() -> Path:
    return repo_root() / "data" / "raw" / "IO-VNBD"


def _norm(name: str) -> str:
    s = name.strip().lower()
    # Strip non-ascii unit glyphs (° µ ² etc.) that break matching.
    s = re.sub(r"[^\x00-\x7f]", " ", s)
    for ch in "[](){}^/":
        s = s.replace(ch, " ")
    s = s.replace("_", " ").replace("-", " ").replace(",", " ")
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
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    size = path.stat().st_size
    if _is_lfs_pointer(path) or size <= min_bytes:
        raise IoVnbdLfsError(f"{path} is {size} bytes (need > {min_bytes}). {LFS_HINT}")


def _map_header(header: list[str]) -> dict[str, int]:
    norms = [_norm(h) for h in header]
    found: dict[str, int] = {}
    for key, aliases in _ALIASES.items():
        alias_compact = {a.replace(" ", "") for a in aliases}
        for i, n in enumerate(norms):
            if key in found:
                break
            compact = n.replace(" ", "")
            if n in aliases or compact in alias_compact:
                found[key] = i
                break
            for a in aliases:
                if len(a) > 3 and a in n:
                    found[key] = i
                    break
    return found


def _col_unit_is_kmh(header_cell: str) -> bool:
    n = _norm(header_cell)
    return "km" in n and "h" in n.replace(" ", "")


def _col_unit_is_ms(header_cell: str) -> bool:
    n = _norm(header_cell)
    return "ms" in n.split() or n.endswith("ms") or "millis" in n


def find_smartphone_csvs(
    raw_dir: Path | None = None,
    *,
    min_bytes: int = LFS_MIN_BYTES,
) -> list[Path]:
    """Return S-*.csv files larger than ``min_bytes`` under IO-VNBD."""
    raw_dir = Path(raw_dir) if raw_dir is not None else default_raw_dir()
    if not raw_dir.is_dir():
        return []
    out: list[Path] = []
    for p in sorted(raw_dir.rglob("S-*.csv")):
        if not p.is_file():
            continue
        try:
            if p.stat().st_size > min_bytes and not _is_lfs_pointer(p):
                out.append(p)
        except OSError:
            continue
    return out


def detect_gnss_outage(
    lat: np.ndarray,
    lon: np.ndarray,
    speed_mps: np.ndarray,
    *,
    acc_h: np.ndarray | None = None,
    acc_h_bad_m: float = 25.0,
    freeze_eps_deg: float = 1e-7,
    freeze_min_samples: int = 300,
) -> np.ndarray:
    """Boolean outage mask (True = GNSS denied / unusable).

    IO-VNBD smartphone logs stream IMU at ~10 Hz but GPS *position* often
    updates much slower (observed ~0.1 Hz on some S-*.csv). Short lat/lon
    holds are therefore normal. Only flag a freeze if stuck for
    ``freeze_min_samples`` (≥ ~30 s at 10 Hz) while speed says moving.
    Primary outage signals are bad accuracy / NaNs.
    """
    n = lat.size
    bad = np.zeros(n, dtype=bool)
    bad |= ~np.isfinite(lat) | ~np.isfinite(lon)
    bad |= ~np.isfinite(speed_mps)
    if acc_h is not None:
        a = np.asarray(acc_h, dtype=np.float64)
        bad |= ~np.isfinite(a) | (a > acc_h_bad_m)
    # Pathological freeze only (tens of seconds), not normal GPS holds.
    if n >= 2:
        dlat = np.abs(np.diff(lat, prepend=lat[0]))
        dlon = np.abs(np.diff(lon, prepend=lon[0]))
        frozen = (dlat < freeze_eps_deg) & (dlon < freeze_eps_deg)
        run = 0
        for i in range(n):
            moving = (not np.isfinite(speed_mps[i])) or speed_mps[i] > 1.0
            if frozen[i] and moving:
                run += 1
            else:
                if run >= freeze_min_samples:
                    bad[i - run : i] = True
                run = 0
        if run >= freeze_min_samples:
            bad[n - run : n] = True
    return bad


def _coordinate_breaks(
    t_s: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    *,
    max_coord_speed_mps: float,
    absolute_jump_m: float,
) -> np.ndarray:
    """Mark impossible jumps while respecting sparse held GNSS fixes."""
    n = len(t_s)
    breaks = np.zeros(n, dtype=bool)
    finite = np.isfinite(lat) & np.isfinite(lon)
    changed = np.zeros(n, dtype=bool)
    changed[0] = finite[0]
    changed[1:] = finite[1:] & (
        ~finite[:-1]
        | (np.abs(np.diff(lat)) > 1e-10)
        | (np.abs(np.diff(lon)) > 1e-10)
    )
    fixes = np.flatnonzero(changed)
    if fixes.size < 2:
        return breaks
    previous = fixes[:-1]
    current = fixes[1:]
    mean_lat = np.deg2rad((lat[previous] + lat[current]) * 0.5)
    north_m = np.deg2rad(lat[current] - lat[previous]) * 6_371_008.8
    east_m = (
        np.deg2rad(lon[current] - lon[previous])
        * 6_371_008.8
        * np.cos(mean_lat)
    )
    distance_m = np.hypot(east_m, north_m)
    elapsed_s = t_s[current] - t_s[previous]
    impossible = (distance_m > absolute_jump_m) | (
        (elapsed_s > 0)
        & (distance_m / np.maximum(elapsed_s, 1e-6) > max_coord_speed_mps)
    )
    breaks[current[impossible]] = True
    return breaks


def segment_iovnbd_sessions(
    data: dict[str, Any],
    *,
    max_gap_s: float = SESSION_MAX_GAP_S,
    max_coord_speed_mps: float = SESSION_MAX_COORD_SPEED_MPS,
    absolute_jump_m: float = SESSION_ABSOLUTE_JUMP_M,
    min_duration_s: float = SESSION_MIN_DURATION_S,
    min_distance_m: float = SESSION_MIN_DISTANCE_M,
) -> list[dict[str, Any]]:
    """Split reset/concatenated logs into monotonic, viable drive sessions.

    Coordinate continuity is evaluated between actual changed GNSS fixes, not
    adjacent 10 Hz rows, because IO-VNBD commonly holds each fix for ~9 seconds.
    """
    t_s = np.asarray(data["t_s"], dtype=np.float64)
    if t_s.size < 2:
        return []
    dt = np.diff(t_s)
    breaks = np.zeros(t_s.size, dtype=bool)
    breaks[1:] = ~np.isfinite(dt) | (dt <= 0) | (dt > max_gap_s)
    breaks |= _coordinate_breaks(
        t_s,
        np.asarray(data["lat"], dtype=np.float64),
        np.asarray(data["lon"], dtype=np.float64),
        max_coord_speed_mps=max_coord_speed_mps,
        absolute_jump_m=absolute_jump_m,
    )
    bounds = np.r_[0, np.flatnonzero(breaks), t_s.size]
    bounds = np.unique(bounds)
    array_keys = [
        key
        for key, value in data.items()
        if isinstance(value, np.ndarray) and len(value) == t_s.size
    ]
    sessions: list[dict[str, Any]] = []
    for source_session_index, (start, end) in enumerate(zip(bounds[:-1], bounds[1:])):
        start, end = int(start), int(end)
        if end - start < 2:
            continue
        duration_s = float(t_s[end - 1] - t_s[start])
        local_dt = np.diff(t_s[start:end])
        speed = np.asarray(data["speed_mps"][start:end], dtype=np.float64)
        speed = np.where(np.isfinite(speed), np.maximum(speed, 0.0), 0.0)
        distance_m = float(np.sum(speed[:-1] * np.clip(local_dt, 0.0, 0.5)))
        if duration_s < min_duration_s or distance_m < min_distance_m:
            continue
        session = dict(data)
        for key in array_keys:
            session[key] = np.asarray(data[key][start:end]).copy()
        session["t_s"] -= session["t_s"][0]
        valid_dt = local_dt[
            np.isfinite(local_dt) & (local_dt > 1e-4) & (local_dt < 2.0)
        ]
        session["n"] = end - start
        session["hz_est"] = (
            float(1.0 / np.median(valid_dt)) if valid_dt.size else data["hz_est"]
        )
        session["source_name"] = data["name"]
        session["name"] = f"{data['name']}#session-{source_session_index + 1}"
        session["session_index"] = source_session_index
        session["source_sample_range"] = [start, end]
        session["session_duration_s"] = duration_s
        session["session_distance_m"] = distance_m
        session["segmentation"] = {
            "dt_nonpositive": True,
            "max_gap_s": max_gap_s,
            "max_coord_speed_mps": max_coord_speed_mps,
            "absolute_jump_m": absolute_jump_m,
            "min_duration_s": min_duration_s,
            "min_distance_m": min_distance_m,
        }
        sessions.append(session)
    return sessions


def load_smartphone_csv(path: Path | str) -> dict[str, Any]:
    """Parse one real S-*.csv into SI arrays + outage mask.

    Returns dict keys:
        t_s, lat, lon, ax, ay, az, gx, gy, gz, gyro_yaw_raw,
        gyro_pitch_raw, gyro_roll_raw, speed_mps, bearing_deg,
        acc_h_m, outage, path, n, hz_est, header_map, file_bytes

    ``gx, gy, gz`` use a right-handed gyro-channel remap:
    ``[gx, gy, gz] = [raw_roll, raw_yaw, -raw_pitch]``. This was validated
    independently for **yaw** against GPS orientation and lat/lon course rates
    by ``alignment_audit.py`` on S-S1 and S-S2 (correlations 0.93--0.99).
    Course alone cannot identify the horizontal-axis completion.
    """
    path = Path(path)
    verify_csv_not_lfs_stub(path)
    file_bytes = path.stat().st_size

    with path.open("r", newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        header = next(reader)
        idx = _map_header(header)
        need = (
            "lat", "lon", "ax", "ay", "az",
            "gyro_yaw_raw", "gyro_pitch_raw", "gyro_roll_raw", "t",
        )
        missing = [k for k in need if k not in idx]
        if missing:
            raise ValueError(
                f"{path.name}: cannot map columns {missing} from {[ _norm(h) for h in header[:12] ]}"
            )

        rows: list[list[float]] = []
        for raw in reader:
            if len(raw) < len(header):
                continue
            try:
                lat = float(raw[idx["lat"]])
                lon = float(raw[idx["lon"]])
                ax = float(raw[idx["ax"]])
                ay = float(raw[idx["ay"]])
                az = float(raw[idx["az"]])
                gyro_yaw_raw = float(raw[idx["gyro_yaw_raw"]])
                gyro_pitch_raw = float(raw[idx["gyro_pitch_raw"]])
                gyro_roll_raw = float(raw[idx["gyro_roll_raw"]])
                t = float(raw[idx["t"]])
            except (ValueError, IndexError):
                continue
            speed = float(raw[idx["speed"]]) if "speed" in idx else float("nan")
            bearing = float(raw[idx["bearing"]]) if "bearing" in idx else float("nan")
            acc_h = float(raw[idx["acc_h"]]) if "acc_h" in idx else float("nan")
            rows.append(
                [
                    t, lat, lon, ax, ay, az,
                    gyro_yaw_raw, gyro_pitch_raw, gyro_roll_raw,
                    speed, bearing, acc_h,
                ]
            )

    if len(rows) < 50:
        raise ValueError(f"{path.name}: only {len(rows)} usable rows")

    arr = np.asarray(rows, dtype=np.float64)
    t_raw = arr[:, 0]
    # TIME SINCE START is milliseconds in the smartphone tables.
    hdr_t = header[idx["t"]]
    if _col_unit_is_ms(hdr_t) or (np.nanmedian(np.diff(t_raw)) > 5.0):
        t_s = (t_raw - t_raw[0]) * 1e-3
    else:
        t_s = t_raw - t_raw[0]

    lat = arr[:, 1]
    lon = arr[:, 2]
    ax = arr[:, 3]
    ay = arr[:, 4]
    az = arr[:, 5]
    gyro_yaw_raw = arr[:, 6]
    gyro_pitch_raw = arr[:, 7]
    gyro_roll_raw = arr[:, 8]
    # Right-handed gyro-channel completion. Only yaw = -raw Pitch is directly
    # observable in this corpus; do not interpret this as an accelerometer
    # mount rotation (raw accelerometer Z carries gravity).
    gx = gyro_roll_raw
    gy = gyro_yaw_raw
    gz = -gyro_pitch_raw
    speed = arr[:, 9]
    bearing = arr[:, 10]
    acc_h = arr[:, 11]

    hdr_speed = header[idx["speed"]] if "speed" in idx else ""
    finite = speed[np.isfinite(speed)]
    if _col_unit_is_kmh(hdr_speed) or (finite.size > 10 and float(np.nanmax(np.abs(finite))) > 80.0):
        speed_mps = speed / 3.6
    else:
        speed_mps = speed.copy()

    # Bearing is degrees in IO-VNBD (GPS ORIENTATION / ORIENTATION Yaw).
    bearing_deg = bearing.copy()

    dt = np.diff(t_s)
    dt = dt[np.isfinite(dt) & (dt > 1e-4) & (dt < 2.0)]
    hz_est = float(1.0 / np.median(dt)) if dt.size else 10.0

    outage = detect_gnss_outage(lat, lon, speed_mps, acc_h=acc_h)

    return {
        "t_s": t_s.astype(np.float64),
        "lat": lat.astype(np.float64),
        "lon": lon.astype(np.float64),
        "ax": ax.astype(np.float64),
        "ay": ay.astype(np.float64),
        "az": az.astype(np.float64),
        "gx": gx.astype(np.float64),
        "gy": gy.astype(np.float64),
        "gz": gz.astype(np.float64),
        "gyro_yaw_raw": gyro_yaw_raw.astype(np.float64),
        "gyro_pitch_raw": gyro_pitch_raw.astype(np.float64),
        "gyro_roll_raw": gyro_roll_raw.astype(np.float64),
        "speed_mps": speed_mps.astype(np.float64),
        "bearing_deg": bearing_deg.astype(np.float64),
        "acc_h_m": acc_h.astype(np.float64),
        "outage": outage,
        "path": str(path),
        "name": path.name,
        "n": int(t_s.size),
        "hz_est": hz_est,
        "header_map": {k: header[i] for k, i in idx.items()},
        "file_bytes": int(file_bytes),
        "axis_mapping": {
            "vehicle_gx": "gyro_roll_raw",
            "vehicle_gy": "gyro_yaw_raw",
            "vehicle_gz_yaw": "-gyro_pitch_raw",
            "yaw_validation": "ALIGNMENT_REPORT.md PASS_ALIGNMENT",
            "horizontal_completion_observable": False,
        },
    }


if __name__ == "__main__":
    csvs = find_smartphone_csvs()
    print(f"found {len(csvs)} real S-*.csv (>1 MB)")
    for p in csvs:
        d = load_smartphone_csv(p)
        print(
            f"  {d['name']}: n={d['n']} hz~{d['hz_est']:.1f} "
            f"outage={100.0 * d['outage'].mean():.1f}% "
            f"map={list(d['header_map'].keys())}"
        )
