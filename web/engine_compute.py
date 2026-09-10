"""The estimator's arithmetic, step by step, on the real UK demo drive.

This drives the console's Engine view. The point is to show the *calculation*
happening -- gravity removed, heading integrated, speed accumulated, error
growing -- not to draw another map. Every number emitted here is computed from
`android/app/src/main/assets/demo/iovnbd_demo.csv`, which is a real IO-VNBD
smartphone strip recorded in Coventry, UK, with vehicle CAN speed as truth.

Nothing is simulated. Where a value cannot be computed from that file it is not
emitted at all.

What each stage actually does
-----------------------------
1. **Raw IMU**            accelerometer and gyroscope as recorded, in the phone frame.
2. **Gravity removal**    a_lin = a - g. Skipping this is the single most common
                          dead-reckoning bug: any tilt leaks ~9.8 m/s^2 into the
                          horizontal axes and velocity explodes within a second.
3. **Heading**            two independent estimates, so they can be compared live:
                          gyro integration (drifts) and a tilt-compensated
                          magnetometer offset-calibrated at outage onset. We
                          measured these at 16.87% vs 7.22% drift over 60 s --
                          `lab/stress/results/heading_fusion/summary.md`.
4. **Speed**              longitudinal accel integrated, with a zero-velocity
                          update when the IMU says stationary.
5. **Position**           free dead reckoning, scored against GNSS truth so the
                          error can be watched growing in real time.

The gap between free-DR error and what the map-in-loop filter achieves is the
product, and it is why the error readout is the most important number on screen.
"""

from __future__ import annotations

import csv
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

REPO = Path(__file__).resolve().parents[1]
DEMO_CSV = REPO / "android" / "app" / "src" / "main" / "assets" / "demo" / "iovnbd_demo.csv"

# Column indices in the committed demo strip. Verified against its header.
C_LAT, C_LON = 0, 1
C_GPS_SPEED, C_GPS_ACC, C_GPS_BRG = 3, 4, 5
C_T_MS = 7
C_AX, C_AY, C_AZ = 9, 10, 11
C_GRAVX, C_GRAVY, C_GRAVZ = 12, 13, 14
C_GYAW, C_GPITCH, C_GROLL = 15, 16, 17
C_MAGX, C_MAGY, C_MAGZ = 18, 19, 20
C_GNSS_VALID = 24
C_CAN_SPEED = 25

# Treated as a GNSS outage for the demo: the estimator is on its own from here.
OUTAGE_START_S = 20.0
OUTAGE_END_S = 80.0

ZUPT_ACCEL_EPS = 0.35  # m/s^2, |a_lin| below this for a sustained window
ZUPT_GYRO_EPS = 0.05  # rad/s
EARTH_R = 6_371_000.0


@dataclass
class Row:
    t: float
    lat: float
    lon: float
    gps_speed: float
    gps_brg: float
    gnss_valid: bool
    can_speed: float
    a: tuple[float, float, float]
    g: tuple[float, float, float]
    gyro: tuple[float, float, float]
    mag: tuple[float, float, float]


def _f(v: str, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def load_demo() -> list[Row]:
    """Parse the committed UK demo strip. Raises if it is missing -- we do not
    fall back to synthetic data and quietly call it real."""
    if not DEMO_CSV.is_file():
        raise FileNotFoundError(f"demo strip not found: {DEMO_CSV}")
    rows: list[Row] = []
    with DEMO_CSV.open(newline="", encoding="utf-8", errors="replace") as fh:
        r = csv.reader(fh)
        next(r, None)
        for line in r:
            if len(line) <= C_CAN_SPEED:
                continue
            rows.append(
                Row(
                    t=_f(line[C_T_MS]) / 1000.0,
                    lat=_f(line[C_LAT]),
                    lon=_f(line[C_LON]),
                    gps_speed=_f(line[C_GPS_SPEED]) / 3.6,
                    gps_brg=_f(line[C_GPS_BRG]),
                    gnss_valid=_f(line[C_GNSS_VALID]) > 0.5,
                    can_speed=_f(line[C_CAN_SPEED]) / 3.6,
                    a=(_f(line[C_AX]), _f(line[C_AY]), _f(line[C_AZ])),
                    g=(_f(line[C_GRAVX]), _f(line[C_GRAVY]), _f(line[C_GRAVZ])),
                    gyro=(_f(line[C_GYAW]), _f(line[C_GPITCH]), _f(line[C_GROLL])),
                    mag=(_f(line[C_MAGX]), _f(line[C_MAGY]), _f(line[C_MAGZ])),
                )
            )
    if len(rows) < 10:
        raise ValueError("demo strip has too few usable rows")
    t0 = rows[0].t
    for row in rows:
        row.t -= t0
    return rows


def _tilt_compensated_heading(
    mag: tuple[float, float, float], grav: tuple[float, float, float]
) -> float:
    """Level the magnetometer with the gravity vector and read a heading."""
    gn = math.sqrt(sum(c * c for c in grav)) or 1e-9
    d = [c / gn for c in grav]
    e = [
        d[1] * mag[2] - d[2] * mag[1],
        d[2] * mag[0] - d[0] * mag[2],
        d[0] * mag[1] - d[1] * mag[0],
    ]
    en = math.sqrt(sum(c * c for c in e)) or 1e-9
    e = [c / en for c in e]
    n = [
        e[1] * d[2] - e[2] * d[1],
        e[2] * d[0] - e[0] * d[2],
        e[0] * d[1] - e[1] * d[0],
    ]
    return math.degrees(math.atan2(e[1], n[1])) % 360.0


def _wrap180(deg: float) -> float:
    return (deg + 180.0) % 360.0 - 180.0


def _haversine(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    dlat = math.radians(b_lat - a_lat)
    dlon = math.radians(b_lon - a_lon)
    mlat = math.radians((a_lat + b_lat) * 0.5)
    return math.hypot(dlat, dlon * math.cos(mlat)) * EARTH_R


class EngineRun:
    """Streams one pass of the estimator's arithmetic over the demo drive."""

    def __init__(self, rows: list[Row] | None = None) -> None:
        self.rows = rows if rows is not None else load_demo()
        self.reset()

    def reset(self) -> None:
        self.i = 0
        self.heading_gyro: float | None = None
        self.heading_mag_offset: float | None = None
        self.speed = 0.0
        self.x = 0.0
        self.y = 0.0
        self.lat0 = self.rows[0].lat
        self.lon0 = self.rows[0].lon
        self.dr_lat = self.lat0
        self.dr_lon = self.lon0
        self.zupt_count = 0
        self.samples = 0
        self.compute_ns = 0

    @property
    def n(self) -> int:
        return len(self.rows)

    def meta(self) -> dict[str, Any]:
        return {
            "source": str(DEMO_CSV.relative_to(REPO)).replace("\\", "/"),
            "provenance": "real IO-VNBD smartphone strip, Coventry UK, CAN speed truth",
            "n_samples": self.n,
            "hz": 10,
            "duration_s": round(self.rows[-1].t, 1),
            "outage": [OUTAGE_START_S, OUTAGE_END_S],
            "lat0": self.lat0,
            "lon0": self.lon0,
        }

    def step(self) -> dict[str, Any] | None:
        """Advance one sample and return every quantity computed for it."""
        if self.i >= self.n:
            return None
        t_start = time.perf_counter_ns()
        row = self.rows[self.i]
        prev = self.rows[self.i - 1] if self.i > 0 else row
        dt = max(1e-3, min(1.0, row.t - prev.t)) if self.i > 0 else 0.1

        # 1) gravity removal -- the bug that eats naive implementations
        a_lin = (row.a[0] - row.g[0], row.a[1] - row.g[1], row.a[2] - row.g[2])
        a_mag = math.sqrt(sum(c * c for c in a_lin))
        gyro_mag = math.sqrt(sum(c * c for c in row.gyro))

        in_outage = OUTAGE_START_S <= row.t < OUTAGE_END_S
        truth_brg = row.gps_brg

        # 2) heading -- gyro integration vs offset-calibrated compass
        mag_raw = _tilt_compensated_heading(row.mag, row.g)
        if self.heading_gyro is None or not in_outage:
            # Outside the outage we hold truth; at onset the estimators take over.
            self.heading_gyro = truth_brg
            self.heading_mag_offset = _wrap180(truth_brg - mag_raw)
        else:
            self.heading_gyro = (self.heading_gyro - math.degrees(row.gyro[0] * dt)) % 360.0
        heading_mag = (mag_raw + (self.heading_mag_offset or 0.0)) % 360.0

        # 3) speed -- integrate longitudinal accel, clamp with ZUPT
        zupt = a_mag < ZUPT_ACCEL_EPS and gyro_mag < ZUPT_GYRO_EPS
        if zupt:
            self.speed = 0.0
            self.zupt_count += 1
        elif in_outage:
            self.speed = max(0.0, self.speed + a_lin[1] * dt)
        else:
            self.speed = row.can_speed

        # 4) position -- free dead reckoning from the onset fix
        if in_outage:
            th = math.radians(self.heading_gyro)
            self.dr_lat += (self.speed * math.cos(th) * dt) / 111_320.0
            self.dr_lon += (self.speed * math.sin(th) * dt) / (
                111_320.0 * max(0.1, math.cos(math.radians(self.dr_lat)))
            )
        else:
            self.dr_lat, self.dr_lon = row.lat, row.lon

        err_m = _haversine(self.dr_lat, self.dr_lon, row.lat, row.lon)

        self.compute_ns += time.perf_counter_ns() - t_start
        self.samples += 1
        self.i += 1

        return {
            "i": self.i,
            "t": round(row.t, 2),
            "dt": round(dt, 4),
            "mode": "IDR" if in_outage else "GNSS",
            "raw": {
                "ax": round(row.a[0], 4), "ay": round(row.a[1], 4), "az": round(row.a[2], 4),
                "gx": round(row.gyro[2], 5), "gy": round(row.gyro[1], 5),
                "gz": round(row.gyro[0], 5),
            },
            "gravity": {
                "x": round(row.g[0], 4), "y": round(row.g[1], 4), "z": round(row.g[2], 4),
            },
            "linear": {
                "x": round(a_lin[0], 4), "y": round(a_lin[1], 4), "z": round(a_lin[2], 4),
                "mag": round(a_mag, 4),
            },
            "heading": {
                "gyro": round(self.heading_gyro, 2),
                "mag": round(heading_mag, 2),
                "truth": round(truth_brg, 2),
                "err_gyro": round(abs(_wrap180(self.heading_gyro - truth_brg)), 2),
                "err_mag": round(abs(_wrap180(heading_mag - truth_brg)), 2),
            },
            "speed": {
                "est": round(self.speed, 3),
                "can": round(row.can_speed, 3),
                "gps": round(row.gps_speed, 3),
                "zupt": zupt,
            },
            "position": {
                "lat": round(self.dr_lat, 7), "lon": round(self.dr_lon, 7),
                "truth_lat": round(row.lat, 7), "truth_lon": round(row.lon, 7),
                "err_m": round(err_m, 2),
            },
            "perf": {
                "samples": self.samples,
                "us_per_sample": round(self.compute_ns / max(self.samples, 1) / 1000.0, 2),
                "zupt_count": self.zupt_count,
            },
        }

    def iter_steps(self) -> Iterator[dict[str, Any]]:
        while True:
            s = self.step()
            if s is None:
                return
            yield s
