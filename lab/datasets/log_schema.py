"""Frozen log schema — SIH26168_PROJECT_BIBLE.md §5.8.

Do not rename fields. Units are SI. Timestamps are monotonic
``SystemClock.elapsedRealtimeNanos()`` (``t_ns``).
Any log missing ``meta.json`` is worthless.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any, Iterable, Mapping

# IO-VNBD native rate. AVNet's 200-sample @ 200 Hz windows are wrong here.
IMU_HZ_IO_VNBD: float = 10.0
WINDOW_SECONDS: float = 2.0
WINDOW_SAMPLES: int = 20  # 2.0 s × 10 Hz
G: float = 9.80665

# Motion lives below this (bible [F7]); above it is vibration / noise adapter.
MOTION_BAND_HZ: float = 2.0

IMU_COLUMNS: tuple[str, ...] = (
    "t_ns",
    "ax",
    "ay",
    "az",
    "gx",
    "gy",
    "gz",
    "mx",
    "my",
    "mz",
    "pressure_hpa",
    "lux",
)

GNSS_COLUMNS: tuple[str, ...] = (
    "t_ns",
    "lat",
    "lon",
    "alt",
    "speed",
    "bearing",
    "acc_h",
    "acc_v",
    "n_sats",
)

# Network consumes the 6-DoF IMU slice of imu.csv (SI).
IMU6_COLUMNS: tuple[str, ...] = ("ax", "ay", "az", "gx", "gy", "gz")

MOUNT_TYPES: tuple[str, ...] = ("handlebar", "pocket", "tankbag", "frame", "dash")
VEHICLE_TYPES: tuple[str, ...] = ("car", "scooter", "motorcycle", "bicycle")

# Bible §5.8 + the TypeScript ILogMeta extras (imu_hz, leans) already frozen
# in core/ts. Both sets are required on disk.
META_FIELDS: tuple[str, ...] = (
    "phone_model",
    "mount_type",
    "vehicle",
    "rider",
    "route_id",
    "loop_closure",
    "notes",
    "imu_hz",
    "leans",
)


@dataclass
class LoopClosure:
    lat: float
    lon: float


@dataclass
class LogMeta:
    phone_model: str
    mount_type: str
    vehicle: str
    rider: str
    route_id: str
    loop_closure: LoopClosure
    notes: str
    imu_hz: float = IMU_HZ_IO_VNBD
    leans: bool = True

    def __post_init__(self) -> None:
        if isinstance(self.loop_closure, Mapping):
            self.loop_closure = LoopClosure(
                lat=float(self.loop_closure["lat"]),
                lon=float(self.loop_closure["lon"]),
            )
        if self.mount_type not in MOUNT_TYPES:
            raise ValueError(f"mount_type must be one of {MOUNT_TYPES}")
        if self.vehicle not in VEHICLE_TYPES:
            raise ValueError(f"vehicle must be one of {VEHICLE_TYPES}")


def imu_header() -> str:
    return ",".join(IMU_COLUMNS)


def gnss_header() -> str:
    return ",".join(GNSS_COLUMNS)


def validate_columns(got: Iterable[str], expected: tuple[str, ...], name: str) -> None:
    got_t = tuple(got)
    if got_t != expected:
        raise ValueError(f"{name} columns must be {expected}, got {got_t}")


def validate_meta(meta: Mapping[str, Any]) -> LogMeta:
    missing = [k for k in META_FIELDS if k not in meta]
    if missing:
        raise ValueError(f"meta.json missing {missing}; log is worthless without it")
    lc = meta["loop_closure"]
    if not isinstance(lc, Mapping) or "lat" not in lc or "lon" not in lc:
        raise ValueError("meta.json.loop_closure must be {lat, lon}")
    return LogMeta(
        phone_model=str(meta["phone_model"]),
        mount_type=str(meta["mount_type"]),
        vehicle=str(meta["vehicle"]),
        rider=str(meta["rider"]),
        route_id=str(meta["route_id"]),
        loop_closure=LoopClosure(lat=float(lc["lat"]), lon=float(lc["lon"])),
        notes=str(meta["notes"]),
        imu_hz=float(meta["imu_hz"]),
        leans=bool(meta["leans"]),
    )


def meta_to_dict(meta: LogMeta) -> dict[str, Any]:
    d = asdict(meta)
    return d


def empty_meta(**overrides: Any) -> LogMeta:
    base = LogMeta(
        phone_model="",
        mount_type="handlebar",
        vehicle="scooter",
        rider="",
        route_id="",
        loop_closure=LoopClosure(lat=0.0, lon=0.0),
        notes="",
    )
    for f in fields(base):
        if f.name in overrides:
            setattr(base, f.name, overrides[f.name])
    base.__post_init__()
    return base
