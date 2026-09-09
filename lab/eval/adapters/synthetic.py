"""Synthetic fixture adapter for the dataset stress harness.

Loads the committed tiny session under
``lab/eval/fixtures/dataset_stress_synthetic/`` so
``run_dataset_stress.py`` is green without a manager download.

This is **not** field proof. Real scores need a download dropped in
``data/field/`` (see adapters/README.md). Avoid Kaggle notebooks — keep
scoring local in this repo.
"""

from __future__ import annotations

import json
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

_FIXTURE_REL = Path("lab") / "eval" / "fixtures" / "dataset_stress_synthetic"

# Session-schema columns (bible §5.8) plus a single combined CSV option.
_SESSION_IMU = {
    "t": ("t_ns", "t", "time", "timestamp"),
    "ax": ("ax",),
    "ay": ("ay",),
    "az": ("az",),
    "gx": ("gx",),
    "gy": ("gy",),
    "gz": ("gz",),
}
_SESSION_GNSS = {
    "t": ("t_ns", "t", "time", "timestamp"),
    "lat": ("lat", "latitude"),
    "lon": ("lon", "longitude", "lng"),
    "speed": ("speed",),
    "bearing": ("bearing", "course", "heading"),
}
_COMBINED = {
    "t": ("t_s", "t", "time", "time_s", "timestamp"),
    "ax": ("ax", "accel_x"),
    "ay": ("ay", "accel_y"),
    "az": ("az", "accel_z"),
    "gx": ("gx", "gyro_x"),
    "gy": ("gy", "gyro_y"),
    "gz": ("gz", "gyro_z"),
    "lat": ("lat", "latitude"),
    "lon": ("lon", "longitude", "lng"),
    "speed": ("speed", "speed_mps"),
    "bearing": ("bearing", "bearing_deg", "heading"),
}


def fixture_dir(repo_root: Path | None = None) -> Path:
    if repo_root is None:
        # adapters/ → eval/ → lab/ → repo
        repo_root = Path(__file__).resolve().parents[3]
    return repo_root / _FIXTURE_REL


class SyntheticAdapter(ColumnAdapter):
    """Adapter for the committed synthetic stress fixture (and clones)."""

    name = "synthetic"

    def discover(self, dataset_dir: Path) -> list[Path]:
        root = Path(dataset_dir)
        if not root.is_dir():
            raise FileNotFoundError(root)
        # Prefer session dirs (imu.csv + gnss.csv); else combined track.csv.
        sessions: list[Path] = []
        if (root / "imu.csv").is_file() and (root / "gnss.csv").is_file():
            sessions.append(root)
        for child in sorted(root.iterdir()):
            if child.is_dir() and (child / "imu.csv").is_file() and (child / "gnss.csv").is_file():
                sessions.append(child)
        if sessions:
            return sessions
        combined = list(root.glob("track.csv")) + list(root.glob("*.csv"))
        return [p for p in combined if p.is_file() and p.stat().st_size > 50]

    def load(self, path: Path) -> SessionArrays:
        path = Path(path)
        if path.is_dir():
            return self._load_session_dir(path)
        return self._load_combined_csv(path)

    def _load_session_dir(self, session: Path) -> SessionArrays:
        imu_h, imu_b = read_csv_table(session / "imu.csv")
        gnss_h, gnss_b = read_csv_table(session / "gnss.csv")
        imu_m = map_columns(imu_h, _SESSION_IMU)
        gnss_m = map_columns(gnss_h, _SESSION_GNSS)
        require_keys(imu_m, ("t", "ax", "ay", "az", "gx", "gy", "gz"), where=str(session / "imu.csv"))
        require_keys(gnss_m, ("t", "lat", "lon"), where=str(session / "gnss.csv"))

        n_imu = len(imu_b)
        t_ns = float_col(imu_b, imu_m["t"], n_imu)
        t_s = t_ns / 1e9 if np.nanmedian(np.abs(t_ns[np.isfinite(t_ns)])) > 1e6 else t_ns.copy()
        t_s = t_s - float(t_s[np.isfinite(t_s)][0])

        # Interpolate GNSS onto IMU timeline (nearest).
        n_g = len(gnss_b)
        g_t_ns = float_col(gnss_b, gnss_m["t"], n_g)
        g_t = g_t_ns / 1e9 if np.nanmedian(np.abs(g_t_ns[np.isfinite(g_t_ns)])) > 1e6 else g_t_ns
        g_t = g_t - float(g_t[np.isfinite(g_t)][0])
        g_lat = float_col(gnss_b, gnss_m["lat"], n_g)
        g_lon = float_col(gnss_b, gnss_m["lon"], n_g)
        g_speed = float_col(gnss_b, gnss_m.get("speed"), n_g)
        g_brg = float_col(gnss_b, gnss_m.get("bearing"), n_g)

        lat = np.interp(t_s, g_t, g_lat, left=g_lat[0], right=g_lat[-1])
        lon = np.interp(t_s, g_t, g_lon, left=g_lon[0], right=g_lon[-1])
        speed = np.interp(t_s, g_t, g_speed, left=g_speed[0], right=g_speed[-1])
        bearing = np.interp(t_s, g_t, g_brg, left=g_brg[0], right=g_brg[-1])

        meta: dict = {"adapter": self.name, "fixture": True}
        meta_path = session / "meta.json"
        if meta_path.is_file():
            meta.update(json.loads(meta_path.read_text(encoding="utf-8")))

        return SessionArrays(
            name=session.name,
            t_s=t_s,
            ax=float_col(imu_b, imu_m["ax"], n_imu),
            ay=float_col(imu_b, imu_m["ay"], n_imu),
            az=float_col(imu_b, imu_m["az"], n_imu),
            gx=float_col(imu_b, imu_m["gx"], n_imu),
            gy=float_col(imu_b, imu_m["gy"], n_imu),
            gz=float_col(imu_b, imu_m["gz"], n_imu),
            lat=lat,
            lon=lon,
            speed=speed,
            bearing_deg=bearing,
            source_path=str(session.resolve()),
            meta=meta,
        )

    def _load_combined_csv(self, path: Path) -> SessionArrays:
        header, body = read_csv_table(path)
        mapped = map_columns(header, _COMBINED)
        require_keys(
            mapped,
            ("t", "ax", "ay", "az", "gx", "gy", "gz", "lat", "lon", "speed"),
            where=str(path),
        )
        n = len(body)
        t_s = float_col(body, mapped["t"], n)
        t_s = t_s - float(t_s[np.isfinite(t_s)][0])
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
            speed=float_col(body, mapped["speed"], n),
            bearing_deg=float_col(body, mapped.get("bearing"), n),
            source_path=str(path.resolve()),
            meta={"adapter": self.name, "fixture": True},
        )
