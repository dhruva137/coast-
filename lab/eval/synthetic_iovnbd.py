"""Deterministic Ford-Fiesta-like 10 Hz IO-VNBD fixture.

Column names follow the IO-VNBD smartphone log (Data in Brief 35 (2021) 106885,
Table A6) plus a GNSS-valid flag and a few Ford Fiesta ECU fields.

Git LFS for the real dataset is often a ~130-byte pointer. This fixture is the
fallback used by iovnbd_plots.py.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

SEED = 26168
HZ = 10
G = 9.80665
# Coventry-ish (IO-VNBD UK roads).
ORIGIN_LAT = 52.4068
ORIGIN_LON = -1.5197
ORIGIN_ALT_M = 82.0
# ~60 s × ~16.7 m/s ≈ 1 km GNSS outage (ISRO 60 km/h / 1 km case).
OUTAGE_S = 60.0
OUTAGE_SPEED_MPS = 1000.0 / OUTAGE_S

EVAL_DIR = Path(__file__).resolve().parent
FIXTURE_DIR = EVAL_DIR / "fixtures"
FIXTURE_PATH = FIXTURE_DIR / "iovnbd_like.csv"

# Table A6 order, then extras the plotter also understands.
HEADER = [
    "GPS latitude",
    "GPS longitude",
    "GPS altitude",
    "GPS speed",
    "GPS accuracy",
    "GPS orientation",
    "GPS satellites In range",
    "Time since start",
    "Date",
    "Accelerometer X",
    "Accelerometer Y",
    "Accelerometer Z",
    "Gravity X",
    "Gravity Y",
    "Gravity Z",
    "Gyroscope (Yaw)",
    "Gyroscope (Pitch)",
    "Gyroscope (Roll)",
    "Magnetic field X",
    "Magnetic field Y",
    "Magnetic field Z",
    "Orientation (Yaw)",
    "Orientation (Pitch)",
    "Orientation (Roll)",
    "GNSS valid",
    "Indicated vehicle speed",
    "Yaw rate",
    "Indicated longitudinal acceleration",
    "Indicated lateral acceleration",
]


def _meters_per_deg(lat_deg: float) -> tuple[float, float]:
    lat = np.deg2rad(lat_deg)
    m_lat = 111_132.92 - 559.82 * np.cos(2 * lat) + 1.175 * np.cos(4 * lat)
    m_lon = 111_412.84 * np.cos(lat) - 93.5 * np.cos(3 * lat)
    return float(m_lat), float(m_lon)


def _enu_to_lla(e: np.ndarray, n: np.ndarray, u: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    m_lat, m_lon = _meters_per_deg(ORIGIN_LAT)
    lat = ORIGIN_LAT + n / m_lat
    lon = ORIGIN_LON + e / m_lon
    alt = ORIGIN_ALT_M + u
    return lat, lon, alt


def _format_date(t_s: float) -> str:
    """IO-VNBD Date column: YYYY-MO-DD HH-MI-SS_SSS."""
    total_ms = int(round(t_s * 1000.0))
    hh = 9 + total_ms // 3_600_000
    rem = total_ms % 3_600_000
    mm = rem // 60_000
    rem %= 60_000
    ss = rem // 1000
    ms = rem % 1000
    return f"2019-03-15 {hh:02d}-{mm:02d}-{ss:02d}_{ms:03d}"


def generate(seed: int = SEED) -> dict:
    """Simulate a Fiesta-like 10 Hz drive with a 60 s / ~1 km GNSS outage."""
    rng = np.random.default_rng(int(seed))
    dt = 1.0 / HZ

    # (duration_s, accel_mps2, yaw_rate_rad_s). Heading = clockwise from north.
    # Accel segment reaches OUTAGE_SPEED_MPS; outage is a 60 s gentle curve.
    a_launch = OUTAGE_SPEED_MPS / 8.0
    segments = (
        (8.0, a_launch, 0.0),
        (12.0, 0.0, 0.0),
        (4.0, 0.0, 0.35),
        (15.0, 0.0, 0.0),
        (6.0, 0.0, -0.20),
        (10.0, 0.0, 0.0),
        (OUTAGE_S, 0.0, 0.008),
        (8.0, 0.0, 0.25),
        (20.0, 0.0, 0.0),
        (8.0, -1.5, 0.0),
    )
    outage_start_s = sum(seg[0] for seg in segments[:6])
    outage_end_s = outage_start_s + OUTAGE_S

    n = int(round(sum(seg[0] for seg in segments) * HZ))
    t = np.arange(n, dtype=np.float64) * dt

    v = 0.0
    psi = 0.12
    e = 0.0
    north = 0.0
    e_arr = np.zeros(n)
    n_arr = np.zeros(n)
    v_arr = np.zeros(n)
    psi_arr = np.zeros(n)
    ax_true = np.zeros(n)
    ay_true = np.zeros(n)
    gz_true = np.zeros(n)

    seg_i = 0
    seg_t = 0.0
    for i in range(n):
        dur, acc, yaw_rate = segments[seg_i]
        v = max(0.0, v + acc * dt)
        psi = psi + yaw_rate * dt
        e = e + v * np.sin(psi) * dt
        north = north + v * np.cos(psi) * dt
        e_arr[i] = e
        n_arr[i] = north
        v_arr[i] = v
        psi_arr[i] = psi
        ax_true[i] = acc
        ay_true[i] = v * yaw_rate
        gz_true[i] = yaw_rate
        seg_t += dt
        if seg_t >= dur - 0.5 * dt and seg_i + 1 < len(segments):
            seg_i += 1
            seg_t = 0.0

    gnss_ok = ~((t >= outage_start_s) & (t < outage_end_s))

    # IO-VNBD vibration: ~0.15 g accel, ~0.08 rad/s gyro (paper).
    # Small residual gyro bias so DR actually drifts during the outage.
    gyro_bias = np.deg2rad(0.04)
    ax = ax_true + rng.normal(0.0, 0.15 * G * 0.35, n)
    ay = ay_true + rng.normal(0.0, 0.15 * G * 0.35, n)
    az = G + rng.normal(0.0, 0.15 * G * 0.25, n)
    gx = rng.normal(0.0, 0.012, n)
    gy = rng.normal(0.0, 0.012, n)
    gz = gz_true + gyro_bias + rng.normal(0.0, 0.08 * 0.35, n)

    lat, lon, alt = _enu_to_lla(e_arr, n_arr, np.zeros(n))
    gps_noise_e = rng.normal(0.0, 1.6, n)
    gps_noise_n = rng.normal(0.0, 1.6, n)
    lat_obs, lon_obs, _ = _enu_to_lla(e_arr + gps_noise_e, n_arr + gps_noise_n, np.zeros(n))
    lat_out = np.where(gnss_ok, lat_obs, lat)
    lon_out = np.where(gnss_ok, lon_obs, lon)

    speed_kmh = v_arr * 3.6
    heading_deg = np.rad2deg(np.mod(psi_arr, 2.0 * np.pi))
    sats = np.where(gnss_ok, 11, 0).astype(np.int64)
    acc_h = np.where(gnss_ok, 2.4, 999.0)
    gps_speed = np.where(gnss_ok, speed_kmh, np.nan)
    gps_hdg = np.where(gnss_ok, heading_deg, np.nan)

    return {
        "t": t,
        "lat": lat_out,
        "lon": lon_out,
        "alt": alt,
        "speed_kmh": speed_kmh,
        "gps_speed_kmh": gps_speed,
        "heading_deg": heading_deg,
        "gps_heading_deg": gps_hdg,
        "sats": sats,
        "acc_h": acc_h,
        "ax": ax,
        "ay": ay,
        "az": az,
        "gx": gx,
        "gy": gy,
        "gz": gz,
        "gnss_ok": gnss_ok,
        "outage_start_s": outage_start_s,
        "outage_end_s": outage_end_s,
        "hz": HZ,
        "seed": int(seed),
    }


def write_csv(path: Path | None = None, seed: int = SEED) -> Path:
    data = generate(seed=seed)
    dest = Path(path) if path is not None else FIXTURE_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)

    n = int(data["t"].shape[0])
    t = data["t"]
    with dest.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(HEADER)
        for i in range(n):
            ok = bool(data["gnss_ok"][i])
            gps_speed = data["gps_speed_kmh"][i]
            gps_hdg = data["gps_heading_deg"][i]
            writer.writerow(
                [
                    f"{data['lat'][i]:.8f}",
                    f"{data['lon'][i]:.8f}",
                    f"{data['alt'][i]:.3f}",
                    "" if not ok or not np.isfinite(gps_speed) else f"{gps_speed:.4f}",
                    f"{data['acc_h'][i]:.2f}",
                    "" if not ok or not np.isfinite(gps_hdg) else f"{gps_hdg:.3f}",
                    int(data["sats"][i]),
                    f"{t[i] * 1000.0:.1f}",
                    _format_date(float(t[i])),
                    f"{data['ax'][i]:.6f}",
                    f"{data['ay'][i]:.6f}",
                    f"{data['az'][i]:.6f}",
                    "0.000000",
                    "0.000000",
                    f"{G:.6f}",
                    f"{data['gz'][i]:.7f}",
                    f"{data['gy'][i]:.7f}",
                    f"{data['gx'][i]:.7f}",
                    f"{20.0 + 0.4 * np.sin(t[i]):.3f}",
                    f"{5.0 + 0.3 * np.cos(t[i]):.3f}",
                    "-41.200",
                    f"{data['heading_deg'][i]:.3f}",
                    "0.000",
                    "0.000",
                    1 if ok else 0,
                    f"{data['speed_kmh'][i]:.4f}",
                    f"{np.rad2deg(data['gz'][i]):.5f}",
                    f"{data['ax'][i] / G:.6f}",
                    f"{data['ay'][i] / G:.6f}",
                ]
            )
    return dest


def main() -> Path:
    path = write_csv()
    print(f"wrote {path}")
    return path


if __name__ == "__main__":
    main()
