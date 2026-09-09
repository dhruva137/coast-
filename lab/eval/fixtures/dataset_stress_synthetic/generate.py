"""Generate the tiny dataset-stress synthetic fixture (deterministic).

Run once from repo root::

    python lab/eval/fixtures/dataset_stress_synthetic/generate.py

Produces imu.csv / gnss.csv / meta.json / track.csv under this directory.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np

SEED = 26168
HZ = 10.0
DURATION_S = 40.0
SPEED_MPS = 5.0
YAW_RATE = 0.08  # rad/s true
GYRO_BIAS = 0.015  # rad/s bias → free-DR heading drift
# Outside iovnbd_midlands OSM bbox on purpose → harness reports free-DR only
# (honest: map-in-loop needs independent OSM coverage; do not invent it).
LAT0 = 12.9716
LON0 = 77.5946
M_PER_DEG_LAT = 111_132.92
M_PER_DEG_LON = 111_412.84 * math.cos(math.radians(LAT0))


def main() -> None:
    rng = np.random.default_rng(SEED)
    out = Path(__file__).resolve().parent
    n = int(DURATION_S * HZ) + 1
    t = np.arange(n, dtype=np.float64) / HZ
    dt = 1.0 / HZ

    # Truth trajectory: constant speed + constant yaw rate (gentle curve).
    yaw = YAW_RATE * t
    east = np.zeros(n)
    north = np.zeros(n)
    for i in range(1, n):
        east[i] = east[i - 1] + SPEED_MPS * math.sin(yaw[i - 1]) * dt
        north[i] = north[i - 1] + SPEED_MPS * math.cos(yaw[i - 1]) * dt
    lat = LAT0 + north / M_PER_DEG_LAT
    lon = LON0 + east / M_PER_DEG_LON
    bearing = (np.degrees(yaw) % 360.0)

    # IMU: gravity on z; small noise; gyro z = truth yaw rate + bias.
    ax = 0.05 * rng.normal(size=n)
    ay = 0.05 * rng.normal(size=n)
    az = 9.80665 + 0.02 * rng.normal(size=n)
    gx = 0.002 * rng.normal(size=n)
    gy = 0.002 * rng.normal(size=n)
    gz = YAW_RATE + GYRO_BIAS + 0.002 * rng.normal(size=n)

    t_ns = (t * 1e9).astype(np.int64)

    imu_path = out / "imu.csv"
    with imu_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
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
            ]
        )
        for i in range(n):
            w.writerow(
                [
                    int(t_ns[i]),
                    f"{ax[i]:.6f}",
                    f"{ay[i]:.6f}",
                    f"{az[i]:.6f}",
                    f"{gx[i]:.6f}",
                    f"{gy[i]:.6f}",
                    f"{gz[i]:.6f}",
                    "20.0",
                    "5.0",
                    "-40.0",
                    "1013.25",
                    "100.0",
                ]
            )

    # GNSS at 1 Hz.
    gnss_path = out / "gnss.csv"
    with gnss_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            ["t_ns", "lat", "lon", "alt", "speed", "bearing", "acc_h", "acc_v", "n_sats"]
        )
        for i in range(0, n, int(HZ)):
            w.writerow(
                [
                    int(t_ns[i]),
                    f"{lat[i]:.9f}",
                    f"{lon[i]:.9f}",
                    "80.0",
                    f"{SPEED_MPS:.3f}",
                    f"{bearing[i]:.3f}",
                    "3.0",
                    "5.0",
                    "12",
                ]
            )

    track_path = out / "track.csv"
    with track_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "t_s",
                "ax",
                "ay",
                "az",
                "gx",
                "gy",
                "gz",
                "lat",
                "lon",
                "speed",
                "bearing_deg",
            ]
        )
        for i in range(n):
            w.writerow(
                [
                    f"{t[i]:.3f}",
                    f"{ax[i]:.6f}",
                    f"{ay[i]:.6f}",
                    f"{az[i]:.6f}",
                    f"{gx[i]:.6f}",
                    f"{gy[i]:.6f}",
                    f"{gz[i]:.6f}",
                    f"{lat[i]:.9f}",
                    f"{lon[i]:.9f}",
                    f"{SPEED_MPS:.3f}",
                    f"{bearing[i]:.3f}",
                ]
            )

    meta = {
        "phone_model": "Synthetic Fixture Phone",
        "mount_type": "handlebar",
        "vehicle": "scooter",
        "rider": "fixture",
        "route_id": "dataset_stress_synthetic",
        "loop_closure": {"lat": float(lat[0]), "lon": float(lon[0])},
        "notes": (
            "SYNTHETIC dataset-stress fixture — NOT a real field log. "
            "Manager drops real data under data/field/. Avoid Kaggle notebooks."
        ),
        "imu_hz": HZ,
        "leans": True,
        "fixture": True,
        "truth_yaw_rate_rad_s": YAW_RATE,
        "injected_gyro_bias_rad_s": GYRO_BIAS,
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    (out / "README.md").write_text(
        "# dataset_stress_synthetic (SYNTHETIC)\n\n"
        "Tiny fixture for `python lab/stress/run_dataset_stress.py "
        "lab/eval/fixtures/dataset_stress_synthetic --adapter synthetic`.\n\n"
        "**Not field proof.** Drop real downloads under `data/field/` and score "
        "locally — do not fork into a Kaggle notebook.\n",
        encoding="utf-8",
    )
    print(f"wrote {n} IMU rows -> {out}")


if __name__ == "__main__":
    main()
