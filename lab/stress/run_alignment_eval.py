"""Online mount/alignment eval: does GNSS-prefix calibration lift branch accuracy?

Baseline to beat
----------------
``lab/stress/results/mapfilter/summary.md`` reports **26%** correct-edge rate
on junctions-live map-in-loop (43 segments). That is the number an online
alignment engine is supposed to move.

Oracle bound (not deployable)
-----------------------------
``lab/stress/results/heading_ablation/summary.md``: CAN-fitted mount + low-pass
vs raw ``-gyro_pitch`` is **~1.57x** on free-DR median error
(321.6 m → 205.2 m). That bounds what *perfect* linear mount correction can buy.
This script must not claim more than it measures.

Methods compared (same outage segments, map-in-loop PF, junctions live)
-----------------------------------------------------------------------
``baseline``      shipped contract: causal 0.5 Hz low-pass of ``gz = -gyro_pitch``
``online``        GNSS-supervised scale+bias on the mapped yaw channel, fit only
                  on the GNSS-visible *prefix before* each outage
                  (``lab/advanced/gyro_mount_calibration.py``). Uses phone GPS
                  course, never CAN. If the fit abstains, falls back to baseline
                  (honest: no silent garbage mount).
``oracle_mount``  CAN least-squares 3-axis mount + low-pass on the whole drive
                  *(oracle upper bound; not phone-deployable)*.

Also reports free-DR median error for the same three yaw streams so the online
gain can be compared against the 1.57x oracle bound without conflating map help.

Run:
    python lab/stress/run_alignment_eval.py [--segments N] [--particles N]

Writes lab/stress/results/alignment/{summary.md,report.json}.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

_STRESS = Path(__file__).resolve().parent
_LAB = _STRESS.parent
_ROOT = _LAB.parent
for _p in (_STRESS, _LAB / "nav", _LAB / "advanced"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from gyro_mount_calibration import (  # noqa: E402
    fit_calibration,
    predict_yaw_rate,
)
from gyro_preprocess import lowpass_causal  # noqa: E402
from load_iovnbd import (  # noqa: E402
    attach_vehicle_truth,
    find_smartphone_csvs,
    load_smartphone_csv,
)
from mapfilter import RoadParticleFilter  # noqa: E402
from mapmatch import MapGraph  # noqa: E402

EARTH_R_M = 6_371_008.8
DENY_S = 60.0
MIN_SPEED_MPS = 8.0
SEED_SAMPLES = 50
GYRO_CUTOFF_HZ = 0.5
DEFAULT_GRAPH = "maps/graphs/iovnbd_midlands.graph.npz"
BASELINE_EDGE_PCT = 26.0  # documented junctions correct-edge rate
ORACLE_FREE_DR_X = 1.57  # documented A→D free-DR bound; cite only, do not invent
RESULTS = _STRESS / "results" / "alignment"
METHODS = ("baseline", "online", "oracle_mount")


def _gcd_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dn = math.radians(lat2 - lat1) * EARTH_R_M
    de = math.radians(lon2 - lon1) * EARTH_R_M * math.cos(math.radians(lat1))
    return math.hypot(de, dn)


def _in_coverage(data: dict[str, Any], graph: MapGraph) -> bool:
    m = graph.meta
    lat = float(np.nanmedian(data["lat"]))
    lon = float(np.nanmedian(data["lon"]))
    return (
        m.get("bbox_lat_min", -90.0) <= lat <= m.get("bbox_lat_max", 90.0)
        and m.get("bbox_lon_min", -180.0) <= lon <= m.get("bbox_lon_max", 180.0)
    )


_EDGE_AT_CACHE: dict[tuple[int, int], int] = {}


def _true_edge_at(graph: MapGraph, lat: float, lon: float, radius_m: float = 60.0) -> int:
    key = (int(lat * 1e5), int(lon * 1e5))
    hit = _EDGE_AT_CACHE.get(key)
    if hit is not None:
        return hit
    best, best_d = -1, radius_m
    for e in graph.nearby_edges(lat, lon, radius_m):
        _, _, d, _, _ = graph.project(int(e), lat, lon)
        if math.isfinite(d) and d < best_d:
            best, best_d = int(e), d
    _EDGE_AT_CACHE[key] = best
    return best


def _free_dr(
    t: np.ndarray, v: np.ndarray, gz: np.ndarray, lat0: float, lon0: float, yaw0: float
) -> tuple[float, float]:
    dt = np.diff(t)
    yaw = yaw0 + np.cumsum(gz[:-1] * dt)
    x = float(np.sum(v[:-1] * np.sin(yaw) * dt))
    y = float(np.sum(v[:-1] * np.cos(yaw) * dt))
    lat = lat0 + math.degrees(y / EARTH_R_M)
    lon = lon0 + math.degrees(x / (EARTH_R_M * math.cos(math.radians(lat0))))
    return lat, lon


def _oracle_mount_yaw(data: dict[str, Any], n: int) -> np.ndarray | None:
    """CAN-fitted 3-axis mount + LP (oracle). Same construction as heading ablation D."""
    gyro = np.column_stack(
        [
            np.asarray(data["gyro_yaw_raw"][:n], dtype=np.float64),
            np.asarray(data["gyro_pitch_raw"][:n], dtype=np.float64),
            np.asarray(data["gyro_roll_raw"][:n], dtype=np.float64),
        ]
    )
    can_yaw = np.asarray(data["can_yaw_rate_rad_s"][:n], dtype=np.float64)
    truth_speed = np.asarray(data["can_speed_mps"][:n], dtype=np.float64)
    course_rate = -can_yaw
    gyro_lp = np.stack(
        [lowpass_causal(gyro[:, i], cutoff_hz=GYRO_CUTOFF_HZ) for i in range(3)],
        axis=1,
    )
    fit = np.isfinite(course_rate) & (truth_speed > 4.0) & np.isfinite(gyro_lp).all(axis=1)
    if int(fit.sum()) < 2000:
        return None
    w_lp, *_ = np.linalg.lstsq(gyro_lp[fit], course_rate[fit], rcond=None)
    return gyro_lp @ w_lp


def _online_yaw_for_prefix(
    data: dict[str, Any], n: int, end_idx: int, baseline: np.ndarray
) -> tuple[np.ndarray, dict[str, Any]]:
    """GNSS-prefix scale+bias on mapped (gx,gy,gz); abstain → baseline."""
    gyro_xyz = np.column_stack(
        [
            np.asarray(data["gx"][:n], dtype=np.float64),
            np.asarray(data["gy"][:n], dtype=np.float64),
            np.asarray(data["gz"][:n], dtype=np.float64),
        ]
    )
    cal = fit_calibration(
        np.asarray(data["t_s"][:n], dtype=np.float64),
        gyro_xyz,
        np.asarray(data["bearing_deg"][:n], dtype=np.float64),
        np.asarray(data["speed_mps"][:n], dtype=np.float64),
        end_idx=end_idx,
    )
    meta = {
        "trusted": bool(cal.trusted_prefix),
        "reason": cal.reason,
        "validation_correlation": float(cal.validation_correlation),
        "axis_norm": float(cal.axis_norm),
        "bias_rps": float(cal.bias_rps),
        "lag_s": float(cal.gps_gyro_lag_s),
        "n_fit": int(cal.n_fit),
    }
    if not cal.trusted_prefix:
        return baseline.copy(), meta
    yaw = predict_yaw_rate(gyro_xyz, cal, fs=10.0)
    # Causal LP to match the baseline filter path.
    return lowpass_causal(yaw, cutoff_hz=GYRO_CUTOFF_HZ), meta


def run_segment(
    data: dict[str, Any],
    graph: MapGraph,
    i0: int,
    i1: int,
    n_particles: int,
    yaw_sigma: float,
    gz: np.ndarray,
) -> dict[str, Any] | None:
    t = data["_t"]
    cla, clo, cv = data["_cla"], data["_clo"], data["_cv"]
    v = data["_v"]

    j = max(0, i0 - SEED_SAMPLES)
    dn = math.radians(float(cla[i0 - 1] - cla[j])) * EARTH_R_M
    de = (
        math.radians(float(clo[i0 - 1] - clo[j]))
        * EARTH_R_M
        * math.cos(math.radians(float(cla[j])))
    )
    if math.hypot(dn, de) < 10.0:
        return None
    yaw0 = math.atan2(de, dn)
    heading0 = math.degrees(yaw0) % 360.0
    end_lat, end_lon = float(cla[i1 - 1]), float(clo[i1 - 1])

    free_lat, free_lon = _free_dr(
        t[i0 - 1 : i1], v[i0 - 1 : i1], gz[i0 - 1 : i1], float(cla[i0 - 1]),
        float(clo[i0 - 1]), yaw0,
    )
    free_err = _gcd_m(end_lat, end_lon, free_lat, free_lon)

    pf = RoadParticleFilter(
        graph, n_particles=n_particles, yaw_sigma_rad_s=yaw_sigma, allowed_edges=None
    )
    if not pf.seed_from_fix(float(cla[i0 - 1]), float(clo[i0 - 1]), heading0):
        return None
    st = None
    last = i1 - 1
    for k in range(i0, i1):
        st = pf.step(
            float(v[k]), float(gz[k]), float(t[k] - t[k - 1]),
            want_position=(k == last),
        )
        if not st.on_graph:
            break
    if st is None or not st.on_graph:
        return None
    pf_err = _gcd_m(end_lat, end_lon, st.lat, st.lon)
    true_edge = _true_edge_at(graph, end_lat, end_lon)
    dt = np.diff(t[i0:i1], prepend=t[i0])
    dist = float(np.nansum(np.clip(cv[i0:i1], 0, None) * np.clip(dt, 0, 0.5)))
    return {
        "start_idx": int(i0),
        "distance_m": dist,
        "free_error_m": free_err,
        "pf_error_m": pf_err,
        "pf_drift_pct": 100.0 * pf_err / max(dist, 1.0),
        "free_drift_pct": 100.0 * free_err / max(dist, 1.0),
        "on_true_edge": bool(true_edge >= 0 and st.edge == true_edge),
        "true_edge_known": bool(true_edge >= 0),
        "pf_pass": bool(
            100.0 * pf_err / max(dist, 1.0) < 10.0
            and pf_err / max(dist, 1.0) * 1000.0 < 100.0
        ),
    }


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"n": 0}
    free = np.array([r["free_error_m"] for r in rows])
    pf = np.array([r["pf_error_m"] for r in rows])
    known = np.array([r["true_edge_known"] for r in rows])
    on_edge = np.array([r["on_true_edge"] for r in rows])
    return {
        "n": len(rows),
        "free_median_error_m": float(np.median(free)),
        "pf_median_error_m": float(np.median(pf)),
        "free_median_drift_pct": float(np.median([r["free_drift_pct"] for r in rows])),
        "pf_median_drift_pct": float(np.median([r["pf_drift_pct"] for r in rows])),
        "pf_pass": int(sum(r["pf_pass"] for r in rows)),
        "edge_accuracy": (
            float(on_edge[known].mean()) if int(known.sum()) > 0 else float("nan")
        ),
        "edge_accuracy_n": int(known.sum()),
        "edge_accuracy_pct": (
            100.0 * float(on_edge[known].mean()) if int(known.sum()) > 0 else float("nan")
        ),
    }


def write_summary(path: Path, report: dict[str, Any]) -> None:
    methods = report["methods"]
    base = methods.get("baseline", {})
    online = methods.get("online", {})
    oracle = methods.get("oracle_mount", {})
    cal = report.get("online_calibration", {})

    def pct(s: dict[str, Any]) -> str:
        if not s.get("n") or not math.isfinite(s.get("edge_accuracy_pct", float("nan"))):
            return "n/a"
        return f"{s['edge_accuracy_pct']:.0f}%"

    def free_x(num: dict[str, Any], den: dict[str, Any]) -> str:
        a = den.get("free_median_error_m")
        b = num.get("free_median_error_m")
        if not a or not b or b <= 0:
            return "n/a"
        return f"{a / b:.2f}x"

    lines = [
        "# Online alignment eval — branch accuracy vs mount correction",
        "",
        "Measured on IO-VNBD with paired CAN truth for scoring. Graph is the "
        "independent OSM midlands graph (not built from drives).",
        "",
        f"Documented baseline correct-edge rate (mapfilter junctions): "
        f"**{BASELINE_EDGE_PCT:.0f}%**. "
        f"Documented oracle free-DR bound (heading ablation A→D): "
        f"**~{ORACLE_FREE_DR_X:.2f}×** — cited as a ceiling, not a claim.",
        "",
        f"Particles: {report['particles']}, yaw σ {report['yaw_sigma']} rad/s, "
        f"outage {report['deny_s']:.0f} s, gyro LP {GYRO_CUTOFF_HZ} Hz.",
        "",
        "## Junctions-live map-in-loop",
        "",
        "| Method | What it is | median PF err | PASS_ISRO | correct-edge |",
        "|---|---|---:|---:|---:|",
        f"| `baseline` | LP(`-gyro_pitch`) shipped contract | "
        f"{base.get('pf_median_error_m', float('nan')):.1f} m | "
        f"{base.get('pf_pass', 0)}/{base.get('n', 0)} | "
        f"**{pct(base)}** of {base.get('edge_accuracy_n', 0)} |",
        f"| `online` | GNSS-prefix scale+bias on mapped gz *(deployable)* | "
        f"{online.get('pf_median_error_m', float('nan')):.1f} m | "
        f"{online.get('pf_pass', 0)}/{online.get('n', 0)} | "
        f"**{pct(online)}** of {online.get('edge_accuracy_n', 0)} |",
        f"| `oracle_mount` | CAN 3-axis mount + LP *(oracle)* | "
        f"{oracle.get('pf_median_error_m', float('nan')):.1f} m | "
        f"{oracle.get('pf_pass', 0)}/{oracle.get('n', 0)} | "
        f"**{pct(oracle)}** of {oracle.get('edge_accuracy_n', 0)} |",
        "",
        "## Free-DR median error (same segments; heading only)",
        "",
        "| Method | median free-DR err | vs baseline |",
        "|---|---:|---:|",
        f"| `baseline` | {base.get('free_median_error_m', float('nan')):.1f} m | 1.00× |",
        f"| `online` | {online.get('free_median_error_m', float('nan')):.1f} m | "
        f"{free_x(online, base)} |",
        f"| `oracle_mount` | {oracle.get('free_median_error_m', float('nan')):.1f} m | "
        f"{free_x(oracle, base)} |",
        "",
        f"Oracle free-DR improvement measured here: **{free_x(oracle, base)}** "
        f"(document bound ~{ORACLE_FREE_DR_X:.2f}×). "
        f"Online free-DR improvement measured here: **{free_x(online, base)}**.",
        "",
        "## Online calibration trust",
        "",
        f"Prefix fits attempted: **{cal.get('attempts', 0)}**. "
        f"Trusted (applied): **{cal.get('trusted', 0)}**. "
        f"Abstained → baseline: **{cal.get('abstained', 0)}**.",
        "",
        "Abstention reasons are recorded in `report.json` "
        "(`online_calibration.reasons`). A rejected prefix never invents a mount.",
        "",
        "## Verdict",
        "",
    ]

    base_edge = base.get("edge_accuracy_pct", float("nan"))
    online_edge = online.get("edge_accuracy_pct", float("nan"))
    base_free = base.get("free_median_error_m", float("nan"))
    online_free = online.get("free_median_error_m", float("nan"))
    if math.isfinite(base_edge) and math.isfinite(online_edge):
        delta = online_edge - base_edge
        if online_edge > base_edge + 0.5:
            edge_line = (
                f"**Edge: positive** — {base_edge:.0f}% → {online_edge:.0f}% "
                f"(Δ {delta:+.1f} pp vs this run; doc baseline "
                f"{BASELINE_EDGE_PCT:.0f}%)."
            )
        elif abs(delta) <= 0.5:
            edge_line = (
                f"**Edge: wash** — {online_edge:.0f}% vs baseline "
                f"{base_edge:.0f}% (doc baseline {BASELINE_EDGE_PCT:.0f}%)."
            )
        else:
            edge_line = (
                f"**Edge: negative** — {base_edge:.0f}% → {online_edge:.0f}% "
                f"(Δ {delta:+.1f} pp). Do not claim improvement."
            )
        lines.append(edge_line)
    else:
        lines.append("**Edge: inconclusive** — insufficient known true edges.")

    if math.isfinite(base_free) and math.isfinite(online_free) and online_free > 0:
        ratio = base_free / online_free
        if ratio < 0.98:
            lines.append(
                f"**Free-DR: negative** — online median {online_free:.1f} m vs "
                f"baseline {base_free:.1f} m ({ratio:.2f}×; <1 means worse). "
                f"The documented ~{ORACLE_FREE_DR_X:.2f}× oracle bound was "
                f"**not** achieved by the deployable online method on this cohort."
            )
        elif ratio > 1.02:
            lines.append(
                f"**Free-DR: positive** — {ratio:.2f}× vs baseline "
                f"(still do not claim beyond measured; oracle doc bound "
                f"~{ORACLE_FREE_DR_X:.2f}×)."
            )
        else:
            lines.append(
                f"**Free-DR: wash** — online {online_free:.1f} m ≈ baseline "
                f"{base_free:.1f} m."
            )

    lines += [
        "",
        "## Limitations",
        "",
        "- `oracle_mount` consumes CAN and is **not** a phone method.",
        "- Online fit needs a GNSS-visible turning prefix; many highway segments "
        "abstain (weak excitation / scale gate).",
        "- Android `MountCalibration.kt` remains the **straight-line start** UX "
        "path (accel gravity + Δv). GNSS-prefix scale+bias was **not** ported "
        "into that class in this commit — different protocol, would risk the "
        "existing unit suite without a measured on-device win.",
        "- Do not quote online free-DR improvement above the measured ratio, "
        f"and do not imply the ~{ORACLE_FREE_DR_X:.2f}× bound was achieved online.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--segments", type=int, default=6)
    ap.add_argument("--files", type=int, default=0)
    ap.add_argument("--particles", type=int, default=600)
    ap.add_argument("--yaw-sigma", type=float, default=0.30)
    ap.add_argument("--graph", default=DEFAULT_GRAPH)
    args = ap.parse_args()

    graph_path = Path(args.graph)
    if not graph_path.is_absolute():
        graph_path = _ROOT / graph_path
    graph = MapGraph.load(str(graph_path))
    if graph.meta.get("built_from_drive_data", True):
        print("ABORT: graph is not independent of the drive data.", file=sys.stderr)
        return 2

    csvs = find_smartphone_csvs()
    if args.files:
        csvs = csvs[: args.files]

    method_rows: dict[str, list[dict[str, Any]]] = {m: [] for m in METHODS}
    cal_stats = {
        "attempts": 0,
        "trusted": 0,
        "abstained": 0,
        "reasons": {},
    }
    per_file: list[dict[str, Any]] = []

    for p in csvs:
        try:
            data = attach_vehicle_truth(load_smartphone_csv(p))
        except (OSError, ValueError):
            continue
        if data.get("truth_source") != "can_10hz" or not _in_coverage(data, graph):
            continue
        n = min(int(data["n"]), int(data.get("can_n", 0)))
        if n < 5000:
            continue

        data["_t"] = np.asarray(data["t_s"][:n], dtype=np.float64)
        data["_cla"] = np.asarray(data["can_lat"][:n], dtype=np.float64)
        data["_clo"] = np.asarray(data["can_lon"][:n], dtype=np.float64)
        data["_cv"] = np.asarray(data["can_speed_mps"][:n], dtype=np.float64)
        data["_v"] = np.asarray(data["speed_mps"][:n], dtype=np.float64)

        baseline = lowpass_causal(
            np.asarray(data["gz"][:n], dtype=np.float64),
            cutoff_hz=GYRO_CUTOFF_HZ,
        )
        oracle = _oracle_mount_yaw(data, n)
        if oracle is None:
            continue

        t, cv = data["_t"], data["_cv"]
        file_summary: dict[str, Any] = {"name": data["name"], "segments": []}

        for i0 in np.linspace(int(0.08 * n), int(0.85 * n), args.segments).astype(int):
            i1 = int(np.searchsorted(t, t[i0] + DENY_S))
            slice_v = cv[i0:i1]
            if i1 >= n - 1 or not np.isfinite(slice_v).any():
                continue
            if float(np.nanmean(slice_v)) < MIN_SPEED_MPS:
                continue

            online_yaw, meta = _online_yaw_for_prefix(data, n, int(i0), baseline)
            cal_stats["attempts"] += 1
            if meta["trusted"]:
                cal_stats["trusted"] += 1
            else:
                cal_stats["abstained"] += 1
                reason = meta.get("reason") or "unknown"
                cal_stats["reasons"][reason] = cal_stats["reasons"].get(reason, 0) + 1

            yaw_by_method = {
                "baseline": baseline,
                "online": online_yaw,
                "oracle_mount": oracle,
            }
            seg_row: dict[str, Any] = {"start_idx": int(i0), "online_cal": meta}
            for method, gz in yaw_by_method.items():
                row = run_segment(
                    data, graph, int(i0), i1, args.particles, args.yaw_sigma, gz=gz
                )
                if row is None:
                    continue
                method_rows[method].append(row)
                seg_row[method] = {
                    "pf_error_m": row["pf_error_m"],
                    "free_error_m": row["free_error_m"],
                    "on_true_edge": row["on_true_edge"],
                    "true_edge_known": row["true_edge_known"],
                }
            if any(k in seg_row for k in METHODS):
                file_summary["segments"].append(seg_row)

        if file_summary["segments"]:
            per_file.append(file_summary)
            # Quick progress: baseline vs online edge hits on this file.
            b_hits = sum(
                1
                for s in file_summary["segments"]
                if s.get("baseline", {}).get("true_edge_known")
                and s["baseline"].get("on_true_edge")
            )
            o_hits = sum(
                1
                for s in file_summary["segments"]
                if s.get("online", {}).get("true_edge_known")
                and s["online"].get("on_true_edge")
            )
            known = sum(
                1
                for s in file_summary["segments"]
                if s.get("baseline", {}).get("true_edge_known")
            )
            print(
                f"  {data['name']:16s} segs={len(file_summary['segments']):2d} "
                f"edge baseline {b_hits}/{known}  online {o_hits}/{known}  "
                f"cal trusted "
                f"{sum(1 for s in file_summary['segments'] if s['online_cal']['trusted'])}"
                f"/{len(file_summary['segments'])}"
            )

    methods_summary = {m: summarise(rows) for m, rows in method_rows.items()}
    report = {
        "graph": str(graph_path),
        "graph_meta": graph.meta,
        "particles": args.particles,
        "yaw_sigma": args.yaw_sigma,
        "deny_s": DENY_S,
        "documented_baseline_edge_pct": BASELINE_EDGE_PCT,
        "documented_oracle_free_dr_x": ORACLE_FREE_DR_X,
        "methods": methods_summary,
        "online_calibration": cal_stats,
        "files": per_file,
        "android_port": {
            "ported": False,
            "reason": (
                "Online GNSS-prefix scale+bias is a different protocol from "
                "MountCalibration.kt straight-line accel start; no measured "
                "on-device win to justify breaking the existing unit suite."
            ),
        },
    }

    RESULTS.mkdir(parents=True, exist_ok=True)
    # Keep the existing ALIGNMENT_REPORT.md (axis audit) untouched.
    (RESULTS / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_summary(RESULTS / "summary.md", report)

    print("\n=== ALIGNMENT EVAL ===")
    for m in METHODS:
        s = methods_summary[m]
        if not s.get("n"):
            print(f"{m}: no rows")
            continue
        print(
            f"{m:14s} n={s['n']:3d}  PF {s['pf_median_error_m']:7.1f}m  "
            f"free {s['free_median_error_m']:7.1f}m  "
            f"edge {s['edge_accuracy_pct']:5.1f}%  "
            f"PASS {s['pf_pass']}/{s['n']}"
        )
    print(
        f"online cal: trusted {cal_stats['trusted']}/"
        f"{cal_stats['attempts']} (abstained {cal_stats['abstained']})"
    )
    print(f"\nwrote {RESULTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
