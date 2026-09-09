"""IO-VNBD smartphone CSV → session schema.

Matches the Data-in-Brief / GitHub IO-VNBD headers
(``GPS latitude``, ``Accelerometer X``, ``Gyroscope (Yaw|Pitch|Roll)``, …)
the same way the demo strip and ``lab/stress/load_iovnbd.py`` do.

Mount note: IO-VNBD vehicle yaw ≈ −GYROSCOPE Pitch (see alignment audit).
This adapter exposes that as ``gz`` so free-DR uses the validated axis.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .base import (
    ColumnAdapter,
    SessionArrays,
    float_col,
    map_columns,
    read_csv_table,
    require_keys,
)

# Fuzzy aliases — same spirit as lab/stress/load_iovnbd.py / datasets/io_vnbd.py
_ALIASES: dict[str, tuple[str, ...]] = {
    "lat": ("gps latitude", "latitude", "lat"),
    "lon": ("gps longitude", "longitude", "lon", "lng"),
    "speed": ("gps speed", "speed", "velocity", "vf", "gps_speed"),
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
    # Raw IO-VNBD semantic labels (not yet remapped).
    "gyro_yaw": ("gyroscope yaw", "gyroscope (yaw)", "gyro_z", "gyroz", "gz"),
    "gyro_pitch": ("gyroscope pitch", "gyroscope (pitch)", "gyro_y", "gyroy", "gy"),
    "gyro_roll": ("gyroscope roll", "gyroscope (roll)", "gyro_x", "gyrox", "gx"),
}


def _col_unit_is_kmh(header_cell: str) -> bool:
    n = header_cell.strip().lower().replace(" ", "")
    return "km" in n and "h" in n


class IoVnbdAdapter(ColumnAdapter):
    name = "iovnbd"

    def discover(self, dataset_dir: Path) -> list[Path]:
        root = Path(dataset_dir)
        if not root.is_dir():
            raise FileNotFoundError(root)
        files = sorted(root.rglob("*.csv"))
        # Prefer smartphone-style names; keep everything with GPS-like headers.
        usable: list[Path] = []
        for p in files:
            if p.stat().st_size < 200:
                continue  # likely LFS pointer / empty
            try:
                header, _ = read_csv_table(p)
            except (OSError, ValueError):
                continue
            mapped = map_columns(header, _ALIASES)
            if "lat" in mapped and "lon" in mapped and "ax" in mapped:
                usable.append(p)
        return usable

    def load(self, path: Path) -> SessionArrays:
        path = Path(path)
        header, body = read_csv_table(path)
        mapped = map_columns(header, _ALIASES)
        require_keys(
            mapped,
            ("lat", "lon", "ax", "ay", "az", "t"),
            where=str(path),
        )
        n = len(body)
        t_raw = float_col(body, mapped["t"], n)
        # Time since start is often milliseconds in IO-VNBD.
        if np.nanmedian(np.diff(t_raw[np.isfinite(t_raw)])) > 5.0:
            t_s = t_raw / 1000.0
        else:
            t_s = t_raw.copy()
        if not np.isfinite(t_s[0]):
            t_s[0] = 0.0
        # Fill leading NaNs; enforce monotonic seconds from first finite.
        t0 = float(t_s[np.isfinite(t_s)][0])
        t_s = t_s - t0
        for i in range(1, n):
            if not np.isfinite(t_s[i]):
                t_s[i] = t_s[i - 1] + 0.1

        speed = float_col(body, mapped.get("speed"), n)
        if "speed" in mapped and _col_unit_is_kmh(header[mapped["speed"]]):
            speed = speed / 3.6

        # Validated mount: vehicle yaw rate ≈ −GYROSCOPE Pitch.
        gyro_pitch = float_col(body, mapped.get("gyro_pitch"), n)
        gyro_yaw = float_col(body, mapped.get("gyro_yaw"), n)
        gyro_roll = float_col(body, mapped.get("gyro_roll"), n)
        if np.any(np.isfinite(gyro_pitch)):
            gz = -gyro_pitch
            gy = gyro_yaw
            gx = gyro_roll
            yaw_src = "-gyroscope_pitch"
        else:
            gz = gyro_yaw
            gy = gyro_pitch
            gx = gyro_roll
            yaw_src = "gyroscope_yaw_fallback"

        return SessionArrays(
            name=path.stem,
            t_s=t_s,
            ax=float_col(body, mapped["ax"], n),
            ay=float_col(body, mapped["ay"], n),
            az=float_col(body, mapped["az"], n),
            gx=gx,
            gy=gy,
            gz=gz,
            lat=float_col(body, mapped["lat"], n),
            lon=float_col(body, mapped["lon"], n),
            speed=speed,
            bearing_deg=float_col(body, mapped.get("bearing"), n),
            source_path=str(path.resolve()),
            meta={
                "adapter": self.name,
                "yaw_source": yaw_src,
                "n_rows": n,
            },
        )
