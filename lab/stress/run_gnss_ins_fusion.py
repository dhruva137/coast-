"""GNSS+INS fusion while GNSS is *present* — measured, falsifiable.

Background
----------
The problem statement grades a GNSS-aided INS path, not only GNSS denial.
``docs/AUDIT_AND_PLAN.md`` item 10 says the acceptance bar is: fused position
beats raw GNSS on the *degraded-accuracy* rows. This script is that test.

IO-VNBD smartphone tables expose LLA / speed / horizontal accuracy — not
pseudoranges or carrier phase. Without raw observables, a true tightly-
coupled filter (range-domain) cannot be run on this corpus. What we implement
here is therefore an honest **loosely-coupled** error-state EKF in the
position domain: IMU / speed propagate the state; each *changed* phone GNSS
fix updates position (and optionally speed/bearing). Labelling it "tight"
would be false.

Three estimators, same windows, same CAN ground truth
-----------------------------------------------------
``gnss_only``   phone lat/lon held between sparse fixes (the product baseline
                when GPS is "working").
``ins_only``    car-style dead reckoning from gyro yaw + phone speed, seeded
                once at window start, no GNSS updates afterward.
``fused``       loosely-coupled EKF: same INS propagation, Kalman update on
                every new phone GNSS fix using reported ``acc_h`` as R.

Windows are contiguous stretches where the phone's own outage mask is False
(GNSS available). Scoring is against paired ``V-*.csv`` CAN 10 Hz GNSS when
present; otherwise the script aborts that file rather than silently scoring
against interpolated phone GNSS.

Run:
    python lab/stress/run_gnss_ins_fusion.py [--files N] [--segments N]

Writes lab/stress/results/gnss_ins_fusion/{report.json,summary.md}.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

_STRESS = Path(__file__).resolve().parent
_LAB = _STRESS.parent
for _p in (_STRESS, _LAB / "eval"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from gyro_preprocess import lowpass_causal  # noqa: E402
from load_iovnbd import (  # noqa: E402
    attach_vehicle_truth,
    find_smartphone_csvs,
    load_smartphone_csv,
)
from metrics import lla_to_enu  # noqa: E402

EARTH_R_M = 6_371_008.8
GYRO_CUTOFF_HZ = 0.5
WINDOW_S = 60.0
MIN_SPEED_MPS = 3.0
SEED_SAMPLES = 40
DEGRADED_ACC_H_M = 8.0  # phone reports worse than this → "degraded" subset
MIN_FIX_CHANGE_DEG = 1e-7


def _wrap_pi(a: float) -> float:
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def _enu_err(est_xy: np.ndarray, truth_xy: np.ndarray) -> np.ndarray:
    d = est_xy - truth_xy
    return np.hypot(d[:, 0], d[:, 1])


def _changed_fix_mask(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """True on samples where phone lat/lon actually updates (not a hold)."""
    n = lat.size
    changed = np.zeros(n, dtype=bool)
    if n == 0:
        return changed
    changed[0] = np.isfinite(lat[0]) and np.isfinite(lon[0])
    dlat = np.abs(np.diff(lat))
    dlon = np.abs(np.diff(lon))
    changed[1:] = (
        np.isfinite(lat[1:])
        & np.isfinite(lon[1:])
        & ((dlat > MIN_FIX_CHANGE_DEG) | (dlon > MIN_FIX_CHANGE_DEG))
    )
    return changed


@dataclass
class LcState:
    """Loosely-coupled planar state: east, north, speed, yaw, gyro bias."""

    e: float
    n: float
    v: float
    yaw: float
    bg: float
    # P is 5x5: [e, n, v, yaw, bg]
    P: np.ndarray


def _lc_seed(
    e0: float, n0: float, v0: float, yaw0: float, acc_h: float
) -> LcState:
    r = max(float(acc_h), 2.0) ** 2
    P = np.diag([r, r, 1.0, (10.0 * math.pi / 180.0) ** 2, (0.05) ** 2])
    return LcState(e=e0, n=n0, v=max(v0, 0.0), yaw=yaw0, bg=0.0, P=P)


def _lc_propagate(st: LcState, dt: float, gz: float, speed_meas: float) -> LcState:
    """Constant-speed planar INS with yaw from bias-corrected gyro."""
    if dt <= 0.0 or dt > 0.5:
        return st
    yaw_rate = gz - st.bg
    yaw = _wrap_pi(st.yaw + yaw_rate * dt)
    # Soft pull speed toward phone GNSS speed (odometry), keep process honest.
    alpha = dt / (dt + 0.4)
    v = (1.0 - alpha) * st.v + alpha * max(float(speed_meas), 0.0)
    e = st.e + v * math.sin(st.yaw) * dt
    n = st.n + v * math.cos(st.yaw) * dt

    F = np.eye(5)
    F[0, 2] = math.sin(st.yaw) * dt
    F[0, 3] = v * math.cos(st.yaw) * dt
    F[1, 2] = math.cos(st.yaw) * dt
    F[1, 3] = -v * math.sin(st.yaw) * dt
    F[3, 4] = -dt

    qe = (0.5 * dt) ** 2
    qn = qe
    qv = (0.8 * dt) ** 2
    qyaw = (0.05 * dt) ** 2
    qbg = (1e-4 * dt) ** 2
    Q = np.diag([qe, qn, qv, qyaw, qbg])
    P = F @ st.P @ F.T + Q
    return LcState(e=e, n=n, v=v, yaw=yaw, bg=st.bg, P=P)


def _lc_update_gnss(
    st: LcState,
    e_meas: float,
    n_meas: float,
    acc_h: float,
    *,
    speed: float | None = None,
    bearing_rad: float | None = None,
) -> LcState:
    """Position update; optional soft speed/bearing when motion is clear."""
    r = max(float(acc_h) if np.isfinite(acc_h) else 5.0, 2.0)
    R = np.diag([r * r, r * r])
    H = np.zeros((2, 5))
    H[0, 0] = 1.0
    H[1, 1] = 1.0
    z = np.array([e_meas - st.e, n_meas - st.n], dtype=np.float64)
    S = H @ st.P @ H.T + R
    try:
        K = st.P @ H.T @ np.linalg.inv(S)
    except np.linalg.LinAlgError:
        k = 1.0 / (1.0 + r * r / 25.0)
        return LcState(
            e=st.e + k * z[0],
            n=st.n + k * z[1],
            v=st.v,
            yaw=st.yaw,
            bg=st.bg,
            P=st.P.copy(),
        )
    dx = K @ z
    P = (np.eye(5) - K @ H) @ st.P
    yaw = _wrap_pi(st.yaw + float(dx[3]))
    bg = st.bg + float(dx[4])
    v = max(st.v + float(dx[2]), 0.0)
    e = st.e + float(dx[0])
    n = st.n + float(dx[1])

    if speed is not None and speed > 1.0 and bearing_rad is not None and np.isfinite(
        bearing_rad
    ):
        # Soft heading / speed pull — mirrors C++ InvariantEKF::updateGnss.
        yaw = _wrap_pi(yaw + 0.35 * _wrap_pi(float(bearing_rad) - yaw))
        v = 0.65 * float(speed) + 0.35 * v

    return LcState(e=e, n=n, v=v, yaw=yaw, bg=bg, P=P)


def _ins_only_track(
    t: np.ndarray,
    speed: np.ndarray,
    gz: np.ndarray,
    e0: float,
    n0: float,
    yaw0: float,
) -> np.ndarray:
    n = t.size
    xy = np.empty((n, 2), dtype=np.float64)
    xy[0] = (e0, n0)
    yaw = yaw0
    v = max(float(speed[0]), 0.0)
    for i in range(1, n):
        dt = float(t[i] - t[i - 1])
        if dt <= 0.0 or dt > 0.5:
            xy[i] = xy[i - 1]
            continue
        yaw = _wrap_pi(yaw + float(gz[i - 1]) * dt)
        if np.isfinite(speed[i - 1]):
            v = max(float(speed[i - 1]), 0.0)
        xy[i, 0] = xy[i - 1, 0] + v * math.sin(yaw) * dt
        xy[i, 1] = xy[i - 1, 1] + v * math.cos(yaw) * dt
    return xy


def _fused_track(
    t: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    speed: np.ndarray,
    bearing_deg: np.ndarray,
    acc_h: np.ndarray,
    gz: np.ndarray,
    fix_changed: np.ndarray,
    lat0: float,
    lon0: float,
    e0: float,
    n0: float,
    yaw0: float,
) -> np.ndarray:
    n = t.size
    xy = np.empty((n, 2), dtype=np.float64)
    st = _lc_seed(e0, n0, float(speed[0]) if np.isfinite(speed[0]) else 0.0, yaw0, float(acc_h[0]))
    xy[0] = (st.e, st.n)
    for i in range(1, n):
        dt = float(t[i] - t[i - 1])
        spd = float(speed[i - 1]) if np.isfinite(speed[i - 1]) else st.v
        st = _lc_propagate(st, dt, float(gz[i - 1]), spd)
        if fix_changed[i] and np.isfinite(lat[i]) and np.isfinite(lon[i]):
            enu = lla_to_enu(
                np.array([lat[i]]),
                np.array([lon[i]]),
                origin_lat_deg=lat0,
                origin_lon_deg=lon0,
            )[0]
            br = float(bearing_deg[i]) if np.isfinite(bearing_deg[i]) else float("nan")
            br_rad = math.radians(br) if np.isfinite(br) else None
            spd_i = float(speed[i]) if np.isfinite(speed[i]) else None
            st = _lc_update_gnss(
                st,
                float(enu[0]),
                float(enu[1]),
                float(acc_h[i]),
                speed=spd_i,
                bearing_rad=br_rad,
            )
        xy[i] = (st.e, st.n)
    return xy


def _yaw0_from_truth(cla: np.ndarray, clo: np.ndarray, i0: int) -> float | None:
    j = max(0, i0 - SEED_SAMPLES)
    dn = math.radians(float(cla[i0] - cla[j])) * EARTH_R_M
    de = (
        math.radians(float(clo[i0] - clo[j]))
        * EARTH_R_M
        * math.cos(math.radians(float(cla[j])))
    )
    if math.hypot(dn, de) < 5.0:
        return None
    return math.atan2(de, dn)


def run_window(
    data: dict[str, Any],
    i0: int,
    i1: int,
    gz: np.ndarray,
    fix_changed: np.ndarray,
) -> dict[str, Any] | None:
    t = data["_t"]
    lat, lon = data["_lat"], data["_lon"]
    speed = data["_v"]
    bearing = data["_bearing"]
    acc_h = data["_acc"]
    cla, clo = data["_cla"], data["_clo"]

    yaw0 = _yaw0_from_truth(cla, clo, i0)
    if yaw0 is None:
        return None

    lat0, lon0 = float(cla[i0]), float(clo[i0])
    # Seed all estimators at CAN truth so the comparison is filter quality,
    # not an arbitrary phone-fix offset at t0.
    e0, n0 = 0.0, 0.0
    sl = slice(i0, i1)
    n_samp = i1 - i0
    if n_samp < 30:
        return None

    truth = lla_to_enu(cla[sl], clo[sl], origin_lat_deg=lat0, origin_lon_deg=lon0)
    gnss_xy = lla_to_enu(lat[sl], lon[sl], origin_lat_deg=lat0, origin_lon_deg=lon0)

    ins_xy = _ins_only_track(
        t[sl], speed[sl], gz[sl], e0, n0, yaw0
    )
    fused_xy = _fused_track(
        t[sl],
        lat[sl],
        lon[sl],
        speed[sl],
        bearing[sl],
        acc_h[sl],
        gz[sl],
        fix_changed[sl],
        lat0,
        lon0,
        e0,
        n0,
        yaw0,
    )

    err_g = _enu_err(gnss_xy, truth)
    err_i = _enu_err(ins_xy, truth)
    err_f = _enu_err(fused_xy, truth)

    acc = np.asarray(acc_h[sl], dtype=np.float64)
    degraded = np.isfinite(acc) & (acc >= DEGRADED_ACC_H_M)
    # Also treat long holds between unique fixes as "degraded utility":
    # phone position is stale while the car has moved.
    held = ~fix_changed[sl]
    held[0] = False
    soft_degraded = degraded | held

    def _stats(err: np.ndarray, mask: np.ndarray | None = None) -> dict[str, float]:
        e = err if mask is None else err[mask]
        e = e[np.isfinite(e)]
        if e.size == 0:
            return {
                "n": 0,
                "rmse_m": float("nan"),
                "median_m": float("nan"),
                "p90_m": float("nan"),
                "end_m": float("nan"),
            }
        return {
            "n": int(e.size),
            "rmse_m": float(np.sqrt(np.mean(e * e))),
            "median_m": float(np.median(e)),
            "p90_m": float(np.percentile(e, 90)),
            "end_m": float(e[-1]),
        }

    dt = np.diff(t[sl], prepend=t[i0])
    dist = float(np.nansum(np.clip(data["_cv"][sl], 0, None) * np.clip(dt, 0, 0.5)))
    n_fixes = int(np.sum(fix_changed[sl]))

    return {
        "start_idx": int(i0),
        "n_samples": n_samp,
        "duration_s": float(t[i1 - 1] - t[i0]),
        "distance_m": dist,
        "n_gnss_fixes": n_fixes,
        "all": {
            "gnss_only": _stats(err_g),
            "ins_only": _stats(err_i),
            "fused": _stats(err_f),
        },
        "degraded": {
            "gnss_only": _stats(err_g, soft_degraded),
            "ins_only": _stats(err_i, soft_degraded),
            "fused": _stats(err_f, soft_degraded),
            "n_mask": int(np.sum(soft_degraded)),
            "n_acc_h_ge": int(np.sum(degraded)),
            "n_held": int(np.sum(held)),
        },
        "fused_beats_gnss_median": bool(
            _stats(err_f)["median_m"] < _stats(err_g)["median_m"]
        ),
        "fused_beats_ins_median": bool(
            _stats(err_f)["median_m"] < _stats(err_i)["median_m"]
        ),
        "fused_beats_gnss_degraded": bool(
            _stats(err_f, soft_degraded)["median_m"]
            < _stats(err_g, soft_degraded)["median_m"]
        ),
    }


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"n_windows": 0}

    def gather(bucket: str, method: str, key: str) -> np.ndarray:
        vals = []
        for r in rows:
            v = r[bucket][method].get(key, float("nan"))
            if np.isfinite(v):
                vals.append(v)
        return np.asarray(vals, dtype=np.float64)

    out: dict[str, Any] = {"n_windows": len(rows)}
    for bucket in ("all", "degraded"):
        block: dict[str, Any] = {}
        for method in ("gnss_only", "ins_only", "fused"):
            med = gather(bucket, method, "median_m")
            rmse = gather(bucket, method, "rmse_m")
            p90 = gather(bucket, method, "p90_m")
            block[method] = {
                "median_of_medians_m": float(np.median(med)) if med.size else float("nan"),
                "median_of_rmse_m": float(np.median(rmse)) if rmse.size else float("nan"),
                "median_of_p90_m": float(np.median(p90)) if p90.size else float("nan"),
            }
        g = block["gnss_only"]["median_of_medians_m"]
        i = block["ins_only"]["median_of_medians_m"]
        f = block["fused"]["median_of_medians_m"]
        block["fused_vs_gnss_x"] = float(g / max(f, 1e-9)) if np.isfinite(g) and np.isfinite(f) else float("nan")
        block["fused_vs_ins_x"] = float(i / max(f, 1e-9)) if np.isfinite(i) and np.isfinite(f) else float("nan")
        block["fused_beats_gnss"] = bool(np.isfinite(f) and np.isfinite(g) and f < g)
        block["fused_beats_ins"] = bool(np.isfinite(f) and np.isfinite(i) and f < i)
        out[bucket] = block

    out["windows_fused_beats_gnss"] = int(sum(r["fused_beats_gnss_median"] for r in rows))
    out["windows_fused_beats_ins"] = int(sum(r["fused_beats_ins_median"] for r in rows))
    out["windows_fused_beats_gnss_degraded"] = int(
        sum(r["fused_beats_gnss_degraded"] for r in rows)
    )
    return out


def write_summary(path: Path, report: dict[str, Any]) -> None:
    s = report["summary"]
    lim = report.get("limitations", [])
    lines = [
        "# GNSS+INS fusion while GNSS is present",
        "",
        "Falsification test for AUDIT item 10 / Block B1: does a loosely-coupled",
        "GNSS+INS filter beat phone GNSS-only and INS-only against CAN ground truth,",
        "especially on degraded-accuracy / held-fix rows?",
        "",
        f"**Coupling:** loosely-coupled (position-domain). IO-VNBD has no",
        "pseudoranges/carrier — true tight coupling is not runnable on this corpus.",
        "",
        (
            f"Drives used: **{report['n_files']}** | windows: **{s.get('n_windows', 0)}** | "
            f"window length: {report['window_s']:.0f} s | "
            f"gyro LP causal {GYRO_CUTOFF_HZ} Hz | "
            f"degraded threshold: acc_h ≥ {DEGRADED_ACC_H_M:.0f} m **or** held phone fix. "
            f"Truth: paired CAN 10 Hz (`truth_source=can_10hz` only)."
        ),
        "",
        "## All samples (GNSS-available windows)",
        "",
        "| Estimator | median of window medians | median of RMSEs | median of p90 |",
        "|---|---:|---:|---:|",
    ]
    if s.get("n_windows", 0) == 0:
        lines += [
            "",
            "**No scored windows.** See limitations.",
            "",
        ]
    else:
        a = s["all"]
        for name, key in (
            ("GNSS-only (phone)", "gnss_only"),
            ("INS-only (open DR)", "ins_only"),
            ("Fused LC-EKF", "fused"),
        ):
            b = a[key]
            lines.append(
                f"| {name} | {b['median_of_medians_m']:.2f} m | "
                f"{b['median_of_rmse_m']:.2f} m | {b['median_of_p90_m']:.2f} m |"
            )
        lines += [
            "",
            f"Fused vs GNSS-only: **{a['fused_vs_gnss_x']:.2f}×** "
            f"({'beats' if a['fused_beats_gnss'] else 'DOES NOT beat'} GNSS-only on "
            f"median-of-medians).",
            f"Fused vs INS-only: **{a['fused_vs_ins_x']:.2f}×** "
            f"({'beats' if a['fused_beats_ins'] else 'DOES NOT beat'} INS-only).",
            f"Windows where fused median < GNSS median: "
            f"**{s['windows_fused_beats_gnss']}/{s['n_windows']}**.",
            f"Windows where fused median < INS median: "
            f"**{s['windows_fused_beats_ins']}/{s['n_windows']}**.",
            "",
            "## Degraded subset (acc_h ≥ threshold OR held phone fix)",
            "",
            "This is the AUDIT acceptance slice: fusion should help when the phone",
            "fix is noisy or stale between sparse updates.",
            "",
            "| Estimator | median of window medians | median of RMSEs | median of p90 |",
            "|---|---:|---:|---:|",
        ]
        d = s["degraded"]
        for name, key in (
            ("GNSS-only (phone)", "gnss_only"),
            ("INS-only (open DR)", "ins_only"),
            ("Fused LC-EKF", "fused"),
        ):
            b = d[key]
            lines.append(
                f"| {name} | {b['median_of_medians_m']:.2f} m | "
                f"{b['median_of_rmse_m']:.2f} m | {b['median_of_p90_m']:.2f} m |"
            )
        verdict = (
            "PASS (fused beats GNSS-only on degraded median-of-medians)"
            if d["fused_beats_gnss"]
            else "FAIL (fused does **not** beat GNSS-only on degraded median-of-medians)"
        )
        lines += [
            "",
            f"**AUDIT item 10 verdict: {verdict}**",
            f"Fused vs GNSS-only (degraded): **{d['fused_vs_gnss_x']:.2f}×**.",
            f"Fused vs INS-only (degraded): **{d['fused_vs_ins_x']:.2f}×**.",
            f"Windows where fused beats GNSS on degraded mask: "
            f"**{s['windows_fused_beats_gnss_degraded']}/{s['n_windows']}**.",
            "",
        ]

    lines += [
        "## Method notes",
        "",
        "- Seed: CAN position + course-derived yaw at window start (same for all three).",
        "- INS-only / fused propagation: causal low-passed yaw rate "
        "`gz = -GYROSCOPE Pitch`, phone speed soft-hold.",
        "- Fused updates only on *changed* phone lat/lon (IO-VNBD holds fixes ~9 s).",
        "- Measurement noise R uses reported `GPS ACCURACY` (floored at 2 m).",
        "",
        "## Limitations",
        "",
    ]
    if lim:
        for item in lim:
            lines.append(f"- {item}")
    else:
        lines.append("- None recorded.")
    lines += [
        "",
        "Do not quote this as tightly-coupled fusion. Do not claim a win unless",
        "the degraded table above shows fused median-of-medians strictly below GNSS-only.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", type=int, default=0, help="Cap number of S-*.csv files (0=all)")
    ap.add_argument("--segments", type=int, default=8, help="Windows per file")
    ap.add_argument("--window-s", type=float, default=WINDOW_S)
    args = ap.parse_args()

    limitations: list[str] = []
    csvs = find_smartphone_csvs()
    if not csvs:
        limitations.append(
            "No real S-*.csv (>1 MB) under data/raw/IO-VNBD — cannot score. "
            "Run git lfs pull or unpack the Synchronised zip."
        )
        report = {
            "n_files": 0,
            "window_s": args.window_s,
            "summary": {"n_windows": 0},
            "limitations": limitations,
            "files": [],
            "coupling": "loosely-coupled position-domain",
            "tight_coupling_possible": False,
        }
        out_dir = _STRESS / "results" / "gnss_ins_fusion"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        write_summary(out_dir / "summary.md", report)
        print("NO DATA — wrote empty summary with limitation")
        return 1

    if args.files:
        csvs = csvs[: args.files]

    limitations.append(
        "IO-VNBD exposes LLA/speed/acc_h only — loosely-coupled fusion, not "
        "tight (no pseudoranges)."
    )
    limitations.append(
        "Phone GNSS is sparse (~0.1 Hz unique fixes held across ~10 Hz rows); "
        "GNSS-only error includes hold quantization vs 10 Hz CAN."
    )

    rows: list[dict[str, Any]] = []
    per_file: list[dict[str, Any]] = []
    n_files_used = 0

    for p in csvs:
        try:
            data = attach_vehicle_truth(load_smartphone_csv(p))
        except (OSError, ValueError) as exc:
            print(f"  skip {p.name}: {exc}")
            continue
        if data.get("truth_source") != "can_10hz":
            print(f"  skip {data['name']}: no CAN pair")
            continue
        n = min(int(data["n"]), int(data.get("can_n", 0)))
        if n < 2000:
            print(f"  skip {data['name']}: too short ({n})")
            continue

        data["_t"] = np.asarray(data["t_s"][:n], dtype=np.float64)
        data["_lat"] = np.asarray(data["lat"][:n], dtype=np.float64)
        data["_lon"] = np.asarray(data["lon"][:n], dtype=np.float64)
        data["_v"] = np.asarray(data["speed_mps"][:n], dtype=np.float64)
        data["_bearing"] = np.asarray(data["bearing_deg"][:n], dtype=np.float64)
        data["_acc"] = np.asarray(data["acc_h_m"][:n], dtype=np.float64)
        data["_cla"] = np.asarray(data["can_lat"][:n], dtype=np.float64)
        data["_clo"] = np.asarray(data["can_lon"][:n], dtype=np.float64)
        data["_cv"] = np.asarray(data["can_speed_mps"][:n], dtype=np.float64)
        outage = np.asarray(data["outage"][:n], dtype=bool)
        gz = -lowpass_causal(
            np.asarray(data["gyro_pitch_raw"][:n], dtype=np.float64),
            cutoff_hz=GYRO_CUTOFF_HZ,
            fs_hz=max(data["hz_est"], 5.0),
        )
        fix_changed = _changed_fix_mask(data["_lat"], data["_lon"])

        t = data["_t"]
        available = ~outage
        # Candidate starts: evenly spaced, require mostly GNSS-available window.
        starts = np.linspace(int(0.05 * n), int(0.80 * n), args.segments).astype(int)
        file_rows: list[dict[str, Any]] = []
        for i0 in starts:
            i1 = int(np.searchsorted(t, t[i0] + args.window_s))
            if i1 >= n - 1 or i1 - i0 < 30:
                continue
            if float(np.mean(available[i0:i1])) < 0.85:
                continue
            if float(np.nanmean(data["_cv"][i0:i1])) < MIN_SPEED_MPS:
                continue
            row = run_window(data, int(i0), i1, gz, fix_changed)
            if row is None:
                continue
            row["file"] = data["name"]
            file_rows.append(row)
            rows.append(row)

        if file_rows:
            n_files_used += 1
            med_g = float(np.median([r["all"]["gnss_only"]["median_m"] for r in file_rows]))
            med_i = float(np.median([r["all"]["ins_only"]["median_m"] for r in file_rows]))
            med_f = float(np.median([r["all"]["fused"]["median_m"] for r in file_rows]))
            print(
                f"  {data['name']:16s} n={len(file_rows):2d}  "
                f"gnss={med_g:6.1f}m  ins={med_i:6.1f}m  fused={med_f:6.1f}m"
            )
            per_file.append(
                {
                    "name": data["name"],
                    "n_windows": len(file_rows),
                    "med_gnss_m": med_g,
                    "med_ins_m": med_i,
                    "med_fused_m": med_f,
                    "windows": file_rows,
                }
            )

    summary = summarise(rows)
    report = {
        "coupling": "loosely-coupled position-domain",
        "tight_coupling_possible": False,
        "window_s": args.window_s,
        "degraded_acc_h_m": DEGRADED_ACC_H_M,
        "gyro_cutoff_hz": GYRO_CUTOFF_HZ,
        "n_files": n_files_used,
        "n_candidates_scanned": len(csvs),
        "summary": summary,
        "limitations": limitations,
        "files": [
            {
                "name": f["name"],
                "n_windows": f["n_windows"],
                "med_gnss_m": f["med_gnss_m"],
                "med_ins_m": f["med_ins_m"],
                "med_fused_m": f["med_fused_m"],
            }
            for f in per_file
        ],
        "windows": rows,
    }

    out_dir = _STRESS / "results" / "gnss_ins_fusion"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(
        json.dumps(report, indent=2, default=float), encoding="utf-8"
    )
    write_summary(out_dir / "summary.md", report)

    print(f"\nfiles={n_files_used} windows={summary.get('n_windows', 0)}")
    if summary.get("n_windows"):
        a, d = summary["all"], summary["degraded"]
        print(
            f"ALL      gnss={a['gnss_only']['median_of_medians_m']:.2f}  "
            f"ins={a['ins_only']['median_of_medians_m']:.2f}  "
            f"fused={a['fused']['median_of_medians_m']:.2f}  "
            f"({a['fused_vs_gnss_x']:.2f}× vs gnss, beats={a['fused_beats_gnss']})"
        )
        print(
            f"DEGRADED gnss={d['gnss_only']['median_of_medians_m']:.2f}  "
            f"ins={d['ins_only']['median_of_medians_m']:.2f}  "
            f"fused={d['fused']['median_of_medians_m']:.2f}  "
            f"({d['fused_vs_gnss_x']:.2f}× vs gnss, beats={d['fused_beats_gnss']})"
        )
    print(f"wrote {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
