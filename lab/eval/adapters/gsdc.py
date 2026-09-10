"""Google Smartphone Decimeter Challenge (GSDC) style CSVs → session schema.

Optional adapter for Kaggle GSDC exports. GNSS tables use
``utcTimeMillis`` / ``LatitudeDegrees`` / ``LongitudeDegrees``; IMU tables use
``UncalAccel`` / ``UncalGyro`` MeasurementX/Y/Z. A single combined CSV (as in
the tiny fixture) is also accepted.
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

_COMBINED: dict[str, tuple[str, ...]] = {
    "t": ("utcTimeMillis", "utc_time_millis", "t", "t_s", "time", "timestamp"),
    "ax": ("ax", "MeasurementX", "uncalaccel_x", "accel_x", "acc_x"),
    "ay": ("ay", "MeasurementY", "uncalaccel_y", "accel_y", "acc_y"),
    "az": ("az", "MeasurementZ", "uncalaccel_z", "accel_z", "acc_z"),
    "gx": ("gx", "gyro_x", "uncalgyro_x", "MeasurementX_gyro"),
    "gy": ("gy", "gyro_y", "uncalgyro_y", "MeasurementY_gyro"),
    "gz": ("gz", "gyro_z", "uncalgyro_z", "MeasurementZ_gyro"),
    "lat": ("lat", "LatitudeDegrees", "latitude", "latitude_degrees"),
    "lon": ("lon", "LongitudeDegrees", "longitude", "longitude_degrees"),
    "speed": ("speed", "SpeedMps", "speed_mps"),
    "bearing": ("bearing", "BearingDegrees", "bearing_deg", "course"),
}


class GsdcAdapter(ColumnAdapter):
    name = "gsdc"

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
            mapped = map_columns(header, _COMBINED)
            if "lat" in mapped and "lon" in mapped and "ax" in mapped and "t" in mapped:
                usable.append(p)
        return usable

    def load(self, path: Path) -> SessionArrays:
        path = Path(path)
        header, body = read_csv_table(path)
        mapped = map_columns(header, _COMBINED)
        require_keys(mapped, ("t", "ax", "ay", "az", "lat", "lon"), where=str(path))
        n = len(body)
        t_raw = float_col(body, mapped["t"], n)
        finite = t_raw[np.isfinite(t_raw)]
        if finite.size and float(np.nanmedian(np.abs(finite))) > 1e11:
            t_s = t_raw / 1000.0
        else:
            t_s = t_raw.copy()
        t0 = float(t_s[np.isfinite(t_s)][0])
        t_s = t_s - t0
        for i in range(1, n):
            if not np.isfinite(t_s[i]):
                t_s[i] = t_s[i - 1] + 0.01

        gx = float_col(body, mapped.get("gx"), n)
        gy = float_col(body, mapped.get("gy"), n)
        gz = float_col(body, mapped.get("gz"), n)
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
            speed=float_col(body, mapped.get("speed"), n),
            bearing_deg=float_col(body, mapped.get("bearing"), n),
            source_path=str(path.resolve()),
            meta={"adapter": self.name},
        )
