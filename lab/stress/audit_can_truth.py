"""Audit the S-*.csv processing contract against IO-VNBD's own CAN ground truth.

The Synchronised IO-VNBD release ships row-aligned pairs: ``S-<id>.csv`` is the
smartphone log, ``V-<id>.csv`` is the vehicle log for the *same* drive, same
row count. ``V`` carries CAN yaw rate, indicated vehicle speed, wheel speeds
and a 10 Hz GPS fix. That makes it an independent reference for three things
the smartphone file alone cannot settle:

1. the unit of ``GPS SPEED (Kmh)`` in the S file,
2. the phone-gyro to vehicle-yaw-rate mapping (axis, sign and gain),
3. what a 60 s dead-reckon can achieve at all, given perfect yaw and speed.

Run:
    python lab/stress/audit_can_truth.py

Writes lab/stress/results/can_truth/report.json and prints the tables.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

EARTH_R_M = 6_371_008.8
DENY_S = 60.0
N_SEGMENTS = 10
MIN_SEG_SPEED_MPS = 5.0
ISRO_DRIFT_PCT = 10.0
ISRO_M_PER_KM = 100.0


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def find_pairs() -> list[tuple[str, Path, Path]]:
    """Return (name, S csv, V csv) for every synchronised pair on disk."""
    root = repo_root() / "data" / "raw" / "IO-VNBD"
    pairs: list[tuple[str, Path, Path]] = []
    for s_path in sorted(root.rglob("S-*.csv")):
        if s_path.stat().st_size < 1_000_000:
            continue
        v_path = s_path.with_name("V-" + s_path.name[2:])
        if v_path.is_file() and v_path.stat().st_size > 1_000_000:
            pairs.append((s_path.stem, s_path, v_path))
    return pairs


def _read(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="latin-1")
    df.columns = [c.strip() for c in df.columns]
    return df


def enu(lat: np.ndarray, lon: np.ndarray, lat0: float, lon0: float) -> np.ndarray:
    east = np.deg2rad(lon - lon0) * EARTH_R_M * np.cos(np.deg2rad(lat0))
    north = np.deg2rad(lat - lat0) * EARTH_R_M
    return np.column_stack([east, north])


def load_pair(s_path: Path, v_path: Path) -> dict[str, Any]:
    s = _read(s_path)
    v = _read(v_path)
    sc, vc = list(s.columns), list(v.columns)
    n = min(len(s), len(v))
    out = {
        "n": n,
        "t_s": s[sc[7]].to_numpy(float)[:n] / 1000.0,
        "phone_lat": s[sc[0]].to_numpy(float)[:n],
        "phone_lon": s[sc[1]].to_numpy(float)[:n],
        "speed_col": s[sc[3]].to_numpy(float)[:n],
        "gyro_yaw": s[sc[15]].to_numpy(float)[:n],
        "gyro_pitch": s[sc[16]].to_numpy(float)[:n],
        "gyro_roll": s[sc[17]].to_numpy(float)[:n],
        "can_lat": v[vc[2]].to_numpy(float)[:n],
        "can_lon": v[vc[3]].to_numpy(float)[:n],
        "can_yaw_rate": np.deg2rad(v[vc[14]].to_numpy(float)[:n]),
        "can_speed_mps": v[vc[15]].to_numpy(float)[:n] / 3.6,
    }
    out["gt_enu"] = enu(out["can_lat"], out["can_lon"], out["can_lat"][0], out["can_lon"][0])
    return out


def audit_speed_unit(d: dict[str, Any]) -> dict[str, Any]:
    """Ratio of the S-file speed column to CAN indicated speed in m/s."""
    m = np.isfinite(d["speed_col"]) & np.isfinite(d["can_speed_mps"]) & (d["can_speed_mps"] > 4.0)
    ratio = float(np.nanmean(d["speed_col"][m]) / np.nanmean(d["can_speed_mps"][m]))
    if abs(ratio - 1.0) < 0.15:
        unit = "m/s"
    elif abs(ratio - 3.6) < 0.4:
        unit = "km/h"
    else:
        unit = "unknown"
    return {"col_over_true": ratio, "implied_unit": unit, "n": int(m.sum())}


def audit_yaw_mapping(d: dict[str, Any]) -> dict[str, Any]:
    """Correlate each gyro channel with the CAN yaw rate at full 10 Hz."""
    m = np.isfinite(d["can_yaw_rate"]) & np.isfinite(d["gyro_pitch"]) & (d["can_speed_mps"] > 4.0)
    y = d["can_yaw_rate"][m]
    per_axis = {}
    for name in ("gyro_yaw", "gyro_pitch", "gyro_roll"):
        g = d[name][m]
        per_axis[name] = {
            "correlation": float(np.corrcoef(g, y)[0, 1]),
            "gain": float(np.dot(g, y) / np.dot(g, g)),
        }
    A = np.stack([d["gyro_yaw"][m], d["gyro_pitch"][m], d["gyro_roll"][m]], axis=1)
    w, *_ = np.linalg.lstsq(A, y, rcond=None)
    pred = A @ w
    return {
        "n": int(m.sum()),
        "per_axis": per_axis,
        "lsq_mount_vector": [float(x) for x in w],
        "lsq_norm": float(np.linalg.norm(w)),
        "lsq_correlation": float(np.corrcoef(pred, y)[0, 1]),
        "residual_deg_s_rms": float(np.degrees(np.std(y - pred))),
        "true_yaw_deg_s_std": float(np.degrees(np.std(y))),
    }


def replay(d: dict[str, Any], yaw_rate: np.ndarray, speed: np.ndarray) -> dict[str, Any]:
    """Score forced 60 s outages against the CAN 10 Hz GPS trajectory."""
    n, t, P = d["n"], d["t_s"], d["gt_enu"]
    rows: list[tuple[float, float, float]] = []
    for i0 in np.linspace(int(0.10 * n), int(0.85 * n), N_SEGMENTS).astype(int):
        i1 = i0 + int(DENY_S / 0.1)
        if i1 >= n or float(np.nanmean(d["can_speed_mps"][i0:i1])) < MIN_SEG_SPEED_MPS:
            continue
        seed = P[i0 - 1] - P[max(0, i0 - 50)]
        if float(np.hypot(*seed)) < 10.0:
            continue
        dt = np.diff(t[i0 - 1 : i1])
        yaw = np.arctan2(seed[0], seed[1]) + np.cumsum(yaw_rate[i0 - 1 : i1 - 1] * dt)
        v = speed[i0:i1]
        x = P[i0 - 1, 0] + np.cumsum(v * np.sin(yaw) * dt)
        y = P[i0 - 1, 1] + np.cumsum(v * np.cos(yaw) * dt)
        err = float(np.hypot(x[-1] - P[i1 - 1, 0], y[-1] - P[i1 - 1, 1]))
        dist = float(np.nansum(d["can_speed_mps"][i0:i1] * dt))
        rows.append((err, 100.0 * err / max(dist, 1.0), err / max(dist, 1.0) * 1000.0))
    if not rows:
        return {"n": 0}
    a = np.asarray(rows)
    return {
        "n": len(rows),
        "median_final_error_m": float(np.median(a[:, 0])),
        "median_drift_pct": float(np.median(a[:, 1])),
        "median_m_per_km": float(np.median(a[:, 2])),
        "pass_isro": int(((a[:, 1] < ISRO_DRIFT_PCT) & (a[:, 2] < ISRO_M_PER_KM)).sum()),
    }


def configurations(d: dict[str, Any]) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """The four DR contracts under test, plus the sensor-perfect ceiling."""
    pitch, roll = d["gyro_pitch"], d["gyro_roll"]
    col, can_v = d["speed_col"], d["can_speed_mps"]
    return {
        "A_repo_contract": (-pitch, col / 3.6),
        "B_speed_unit_fixed": (-pitch, col),
        "C_sign_flipped": (pitch, col),
        "D_lsq_mount": (-(0.944 * pitch + 0.431 * roll), col),
        "E_oracle_can": (-d["can_yaw_rate"], can_v),
    }


def main() -> None:
    pairs = find_pairs()
    if not pairs:
        raise SystemExit(
            "no synchronised S-/V- pair found >1 MB. Run: git lfs install && git lfs pull "
            "inside data/raw/IO-VNBD"
        )
    report: dict[str, Any] = {"pairs": {}}
    for name, s_path, v_path in pairs:
        d = load_pair(s_path, v_path)
        speed = audit_speed_unit(d)
        yaw = audit_yaw_mapping(d)
        scores = {k: replay(d, g, v) for k, (g, v) in configurations(d).items()}
        report["pairs"][name] = {
            "s_csv": str(s_path.relative_to(repo_root())),
            "v_csv": str(v_path.relative_to(repo_root())),
            "rows": d["n"],
            "phone_gps_unique_fixes": int(len(np.unique(d["phone_lat"]))),
            "can_gps_unique_fixes": int(len(np.unique(d["can_lat"]))),
            "speed_unit": speed,
            "yaw_mapping": yaw,
            "outage_60s": scores,
        }

        print(f"\n=== {name} ===  rows={d['n']}")
        print(
            f"  GPS fixes: phone={len(np.unique(d['phone_lat']))} vs CAN={len(np.unique(d['can_lat']))}"
        )
        print(
            f"  speed column / CAN true = {speed['col_over_true']:.3f}"
            f"  -> column is {speed['implied_unit']} (header claims Kmh)"
        )
        print("  gyro channel vs CAN yaw rate (10 Hz):")
        for axis, st in yaw["per_axis"].items():
            print(f"    {axis:11s} corr={st['correlation']:+.3f} gain={st['gain']:+.3f}")
        w = yaw["lsq_mount_vector"]
        print(
            f"    lsq mount  = [{w[0]:+.3f} {w[1]:+.3f} {w[2]:+.3f}] |w|={yaw['lsq_norm']:.3f}"
            f" corr={yaw['lsq_correlation']:+.3f} residual={yaw['residual_deg_s_rms']:.2f} deg/s"
        )
        print(f"  forced {DENY_S:.0f} s outage, scored against CAN 10 Hz GPS:")
        print(f"    {'config':22s} {'n':>3s} {'err_m':>7s} {'drift%':>7s} {'m/km':>7s} {'PASS':>7s}")
        for cfg, sc in scores.items():
            if not sc.get("n"):
                continue
            print(
                f"    {cfg:22s} {sc['n']:3d} {sc['median_final_error_m']:7.1f}"
                f" {sc['median_drift_pct']:7.1f} {sc['median_m_per_km']:7.1f}"
                f" {sc['pass_isro']:4d}/{sc['n']}"
            )

    out = repo_root() / "lab" / "stress" / "results" / "can_truth" / "report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nwrote {out.relative_to(repo_root())}")


if __name__ == "__main__":
    main()
