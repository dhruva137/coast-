"""comma2k19-style flattened CSV → session schema.

The full comma2k19 release is huge (~97 GB of raw rlogs). This adapter is for
**manager-exported flat CSVs** (or the committed tiny fixture), not for
auto-downloading the corpus.

Expected columns (fuzzy): time, accel xyz, gyro xyz, lat/lon, optional speed
and bearing — the same shape community ``rlog → CSV`` dumps use.
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

_ALIASES: dict[str, tuple[str, ...]] = {
    "t": (
        "t",
        "t_s",
        "time",
        "timestamp",
        "time_s",
        "seconds",
        "t_ns",
        "logMonoTime",
        "log_mono_time",
    ),
    "ax": ("ax", "accel_x", "acc_x", "acceleration_x", "accelerometer_x"),
    "ay": ("ay", "accel_y", "acc_y", "acceleration_y", "accelerometer_y"),
    "az": ("az", "accel_z", "acc_z", "acceleration_z", "accelerometer_z"),
    "gx": ("gx", "gyro_x", "gyroscope_x", "angular_velocity_x"),
    "gy": ("gy", "gyro_y", "gyroscope_y", "angular_velocity_y"),
    "gz": ("gz", "gyro_z", "gyroscope_z", "angular_velocity_z"),
    "lat": ("lat", "latitude", "gps_lat", "latitude_deg"),
    "lon": ("lon", "longitude", "lng", "gps_lon", "longitude_deg"),
    "speed": ("speed", "speed_mps", "velocity", "vf", "gps_speed"),
    "bearing": ("bearing", "bearing_deg", "heading", "course", "yaw_deg"),
}


class Comma2k19Adapter(ColumnAdapter):
    name = "comma2k19"

    def discover(self, dataset_dir: Path) -> list[Path]:
        root = Path(dataset_dir)
        if not root.is_dir():
            raise FileNotFoundError(root)
        usable: list[Path] = []
        for p in sorted(root.rglob("*.csv")):
            if p.stat().st_size < 80:
                continue
            try:
                header, _ = read_csv_table(p)
            except (OSError, ValueError):
                continue
            mapped = map_columns(header, _ALIASES)
            if all(k in mapped for k in ("t", "ax", "ay", "az", "gx", "gy", "gz", "lat", "lon")):
                usable.append(p)
        return usable

    def load(self, path: Path) -> SessionArrays:
        path = Path(path)
        header, body = read_csv_table(path)
        mapped = map_columns(header, _ALIASES)
        require_keys(
            mapped,
            ("t", "ax", "ay", "az", "gx", "gy", "gz", "lat", "lon"),
            where=str(path),
        )
        n = len(body)
        t_raw = float_col(body, mapped["t"], n)
        # nanoseconds → seconds when magnitudes look like ns.
        finite = t_raw[np.isfinite(t_raw)]
        if finite.size and float(np.nanmedian(np.abs(finite))) > 1e12:
            t_s = t_raw / 1e9
        elif finite.size and float(np.nanmedian(np.abs(finite))) > 1e6:
            t_s = t_raw / 1e3
        else:
            t_s = t_raw.copy()
        t0 = float(t_s[np.isfinite(t_s)][0])
        t_s = t_s - t0
        for i in range(1, n):
            if not np.isfinite(t_s[i]):
                t_s[i] = t_s[i - 1] + 0.01

        speed = float_col(body, mapped.get("speed"), n)
        bearing = float_col(body, mapped.get("bearing"), n)
        return SessionArrays(
            name=path.stem,
            t_s=t_s,
            ax=float_col(body, mapped["ax"], n),
            ay=float_col(body, mapped["ay"], n),
            az=float_col(body, mapped["az"], n),
            gx=float_col(body, mapped["gx"], n),
            gy=float_col(body, mapped["gy"], n),
            gz=float_col(body, mapped["gz"], n),
            lat=float_col(body, mapped["lat"], n),
            lon=float_col(body, mapped["lon"], n),
            speed=speed,
            bearing_deg=bearing,
            source_path=str(path.resolve()),
            meta={"adapter": self.name, "fixture": "tiny" in path.as_posix().lower()},
        )
