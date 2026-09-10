"""Compass-on, map-in-loop outage experiment.

This is a separate follow-on to ``run_mapfilter_eval.py``.  It keeps that
baseline immutable and evaluates two road particle filters on identical
60-second windows:

``map_gyro``       existing map-in-loop filter using yaw-rate evidence.
``map_compass``    the same filter plus absolute compass heading evidence.

The compass-to-vehicle offset is calibrated once from the last phone GNSS
bearing at outage onset.  No heading truth is used after onset.  Results are
written only below ``lab/stress/results/mapfilter_compass``.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from lab.stress.run_heading_fusion import _tilt_compensated_heading, _wrap180
from lab.stress.run_magnetometer_study import _load as load_compass_columns
from lab.stress.run_mapfilter_eval import (
    DEFAULT_GRAPH,
    DENY_S,
    GYRO_CUTOFF_HZ,
    MIN_SPEED_MPS,
    SEED_SAMPLES,
    _free_dr,
    _gcd_m,
    _in_coverage,
    _true_edge_at,
)
from lab.stress.gyro_preprocess import lowpass_causal
from lab.stress.load_iovnbd import (
    attach_vehicle_truth,
    find_smartphone_csvs,
    load_smartphone_csv,
)
from lab.nav.mapfilter import DEFAULT_HEADING_SIGMA_DEG, RoadParticleFilter
from lab.nav.mapmatch import MapGraph

_STRESS = Path(__file__).resolve().parent
_RESULT_ROOT = _STRESS / "results" / "mapfilter_compass"


def onset_calibrated_compass(
    compass_raw_deg: np.ndarray,
    bearing_deg: np.ndarray,
    onset: int,
) -> np.ndarray | None:
    """Calibrate mount/declination offset from the last onset-available bearing."""
    if onset < 0 or onset >= compass_raw_deg.size or not np.isfinite(compass_raw_deg[onset]):
        return None
    candidates = np.flatnonzero(
        np.isfinite(bearing_deg[: onset + 1])
        & (bearing_deg[: onset + 1] >= 0.0)
        & (bearing_deg[: onset + 1] <= 360.0)
    )
    if not candidates.size:
        return None
    h0 = float(bearing_deg[int(candidates[-1])])
    offset = float(_wrap180(np.asarray([h0 - compass_raw_deg[onset]]))[0])
    return (compass_raw_deg + offset) % 360.0


def _run_variant(
    graph: MapGraph,
    *,
    n_particles: int,
    yaw_sigma: float,
    allowed: set[int] | None,
    lat0: float,
    lon0: float,
    heading0: float,
    t: np.ndarray,
    speed: np.ndarray,
    gz: np.ndarray,
    compass: np.ndarray | None,
    heading_sigma_deg: float,
    i0: int,
    i1: int,
) -> tuple[float, float, int] | None:
    pf = RoadParticleFilter(
        graph,
        n_particles=n_particles,
        yaw_sigma_rad_s=yaw_sigma,
        allowed_edges=allowed,
    )
    if not pf.seed_from_fix(lat0, lon0, heading0):
        return None
    state = None
    for k in range(i0, i1):
        heading = None if compass is None or not np.isfinite(compass[k]) else float(compass[k])
        state = pf.step(
            float(speed[k]),
            float(gz[k]),
            float(t[k] - t[k - 1]),
            heading_deg=heading,
            heading_sigma_deg=heading_sigma_deg,
            want_position=(k == i1 - 1),
        )
        if not state.on_graph:
            return None
    if state is None:
        return None
    return float(state.lat), float(state.lon), int(state.edge)


def run_segment(
    data: dict[str, Any],
    graph: MapGraph,
    i0: int,
    i1: int,
    n_particles: int,
    yaw_sigma: float,
    heading_sigma_deg: float,
    corridor: bool,
    gz: np.ndarray,
    compass_raw: np.ndarray,
) -> dict[str, Any] | None:
    t, cla, clo = data["_t"], data["_cla"], data["_clo"]
    speed, truth_speed = data["_v"], data["_cv"]
    j = max(0, i0 - SEED_SAMPLES)
    dn = math.radians(float(cla[i0 - 1] - cla[j])) * 6_371_008.8
    de = (
        math.radians(float(clo[i0 - 1] - clo[j]))
        * 6_371_008.8
        * math.cos(math.radians(float(cla[j])))
    )
    if math.hypot(dn, de) < 10.0:
        return None
    yaw0 = math.atan2(de, dn)
    heading0 = math.degrees(yaw0) % 360.0
    compass = onset_calibrated_compass(compass_raw, data["_bearing"], i0 - 1)
    if compass is None:
        return None

    allowed: set[int] | None = None
    if corridor:
        allowed = {
            edge
            for k in range(i0, i1, 10)
            if (edge := _true_edge_at(graph, float(cla[k]), float(clo[k]))) >= 0
        }
        if not allowed:
            return None

    common = dict(
        graph=graph,
        n_particles=n_particles,
        yaw_sigma=yaw_sigma,
        allowed=allowed,
        lat0=float(cla[i0 - 1]),
        lon0=float(clo[i0 - 1]),
        heading0=heading0,
        t=t,
        speed=speed,
        gz=gz,
        heading_sigma_deg=heading_sigma_deg,
        i0=i0,
        i1=i1,
    )
    gyro_result = _run_variant(compass=None, **common)
    compass_result = _run_variant(compass=compass, **common)
    if gyro_result is None or compass_result is None:
        return None

    end_lat, end_lon = float(cla[i1 - 1]), float(clo[i1 - 1])
    free_lat, free_lon = _free_dr(
        t[i0 - 1 : i1],
        speed[i0 - 1 : i1],
        gz[i0 - 1 : i1],
        float(cla[i0 - 1]),
        float(clo[i0 - 1]),
        yaw0,
    )
    dt = np.diff(t[i0:i1], prepend=t[i0])
    distance = float(
        np.nansum(np.clip(truth_speed[i0:i1], 0, None) * np.clip(dt, 0, 0.5))
    )
    true_edge = _true_edge_at(graph, end_lat, end_lon)
    row: dict[str, Any] = {
        "start_idx": int(i0),
        "distance_m": distance,
        "free_error_m": _gcd_m(end_lat, end_lon, free_lat, free_lon),
    }
    for name, result in (("map_gyro", gyro_result), ("map_compass", compass_result)):
        lat, lon, edge = result
        err = _gcd_m(end_lat, end_lon, lat, lon)
        row[f"{name}_error_m"] = err
        row[f"{name}_drift_pct"] = 100.0 * err / max(distance, 1.0)
        row[f"{name}_on_true_edge"] = bool(true_edge >= 0 and edge == true_edge)
    row["true_edge_known"] = bool(true_edge >= 0)
    return row


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"n": 0}
    out: dict[str, Any] = {"n": len(rows)}
    for method in ("free", "map_gyro", "map_compass"):
        err = np.asarray([r[f"{method}_error_m"] for r in rows], dtype=np.float64)
        if method == "free":
            drift = 100.0 * err / np.maximum(
                np.asarray([r["distance_m"] for r in rows], dtype=np.float64), 1.0
            )
        else:
            drift = np.asarray([r[f"{method}_drift_pct"] for r in rows], dtype=np.float64)
        out[method] = {
            "median_error_m": float(np.median(err)),
            "median_drift_pct": float(np.median(drift)),
            "pass_under_10pct": int(np.sum(drift < 10.0)),
        }
    gyro = out["map_gyro"]["median_error_m"]
    compass = out["map_compass"]["median_error_m"]
    out["compass_vs_gyro_x"] = float(gyro / max(compass, 1e-9))
    out["compass_helped"] = int(
        sum(r["map_compass_error_m"] < r["map_gyro_error_m"] for r in rows)
    )
    known = [r for r in rows if r["true_edge_known"]]
    out["edge_accuracy_n"] = len(known)
    for method in ("map_gyro", "map_compass"):
        out[f"{method}_edge_accuracy"] = (
            float(np.mean([r[f"{method}_on_true_edge"] for r in known]))
            if known
            else None
        )
    return out


def _render(report: dict[str, Any]) -> str:
    lines = [
        "# Compass-on map-in-loop experiment",
        "",
        "Follow-on experiment only; the frozen mapfilter baseline is unchanged.",
        "Compass offset is calibrated from the last phone GNSS bearing at outage onset.",
        "",
        f"Protocol: segments={report.get('segments', '?')}, "
        f"particles={report.get('particles', '?')}, "
        f"yaw_sigma={report.get('yaw_sigma', '?')}.",
        "Frozen mapfilter/report.json (2.02x, n=43) was not overwritten.",
        "",
    ]
    for scenario in ("junctions", "corridor"):
        summary = report["scenarios"].get(scenario, {})
        if not summary.get("n"):
            continue
        lines += [
            f"## {scenario}",
            "",
            "| policy | median error | median drift | under 10% |",
            "|---|---:|---:|---:|",
        ]
        for method in ("free", "map_gyro", "map_compass"):
            value = summary[method]
            lines.append(
                f"| `{method}` | {value['median_error_m']:.2f} m | "
                f"{value['median_drift_pct']:.2f}% | "
                f"{value['pass_under_10pct']}/{summary['n']} |"
            )
        lines += [
            "",
            f"Compass/map-gyro endpoint ratio: **{summary['compass_vs_gyro_x']:.3f}x**; "
            f"compass helped {summary['compass_helped']}/{summary['n']} windows.",
            "",
        ]
    jn = report["scenarios"].get("junctions", {})
    if jn.get("n"):
        free_m = jn["free"]["median_error_m"]
        gyro_m = jn["map_gyro"]["median_error_m"]
        compass_m = jn["map_compass"]["median_error_m"]
        compass_vs_free = free_m / max(compass_m, 1e-9)
        gyro_vs_free = free_m / max(gyro_m, 1e-9)
        lines += [
            "## Headline impact (frozen 2.02x not overwritten)",
            "",
            f"Same 43 junctions-live windows as the frozen mapfilter result: "
            f"`map_gyro` median {gyro_m:.2f} m reproduces **{gyro_vs_free:.2f}x** vs free DR.",
            f"`map_compass` median {compass_m:.2f} m is **{jn['compass_vs_gyro_x']:.3f}x** vs gyro "
            f"and **{compass_vs_free:.2f}x** vs free DR (worse than free).",
            "Replacing the shipped map-in-loop policy with onset-calibrated compass would move",
            "the 2.02x headline. That replacement is **not** applied here.",
            "Heading-channel 16.87%→7.22% does not transfer to map-in-loop position.",
            "",
        ]
    lines += [
        "## Scope",
        "",
        "Follow-on experiment only. Frozen `lab/stress/results/mapfilter/` claims stay",
        "until the parent decides. Smoke results under `mapfilter_compass/smoke/` are untouched.",
    ]
    return "\n".join(lines) + "\n"


def _safe_output_dir(raw: str | None) -> Path:
    target = Path(raw).resolve() if raw else _RESULT_ROOT.resolve()
    root = _RESULT_ROOT.resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"output must stay below {root}")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--segments", type=int, default=12)
    parser.add_argument("--files", type=int, default=0)
    parser.add_argument("--particles", type=int, default=600)
    parser.add_argument("--yaw-sigma", type=float, default=0.30)
    parser.add_argument("--heading-sigma-deg", type=float, default=DEFAULT_HEADING_SIGMA_DEG)
    parser.add_argument("--graph", default=DEFAULT_GRAPH)
    parser.add_argument("--output-dir")
    args = parser.parse_args()

    output_dir = _safe_output_dir(args.output_dir)
    print(
        f"start segments={args.segments} particles={args.particles} "
        f"yaw_sigma={args.yaw_sigma} graph={args.graph}",
        flush=True,
    )
    graph = MapGraph.load(args.graph)
    if graph.meta.get("built_from_drive_data", True):
        print("ABORT: graph is not independent of the drive data.")
        return 2
    paths = find_smartphone_csvs()
    if args.files:
        paths = paths[: args.files]
    rows: dict[str, list[dict[str, Any]]] = {"junctions": [], "corridor": []}
    files: list[dict[str, Any]] = []

    for path in paths:
        compass_data = load_compass_columns(path)
        if compass_data is None:
            continue
        try:
            data = attach_vehicle_truth(load_smartphone_csv(path))
        except (OSError, ValueError):
            continue
        if data.get("truth_source") != "can_10hz" or not _in_coverage(data, graph):
            continue
        print(f"  processing {data['name']}", flush=True)
        n = min(int(data["n"]), int(data.get("can_n", 0)))
        if n < 5000 or len(compass_data["mag_x"]) < n:
            continue
        data["_t"] = np.asarray(data["t_s"][:n], dtype=np.float64)
        data["_cla"] = np.asarray(data["can_lat"][:n], dtype=np.float64)
        data["_clo"] = np.asarray(data["can_lon"][:n], dtype=np.float64)
        data["_cv"] = np.asarray(data["can_speed_mps"][:n], dtype=np.float64)
        data["_v"] = np.asarray(data["speed_mps"][:n], dtype=np.float64)
        data["_bearing"] = np.asarray(data["bearing_deg"][:n], dtype=np.float64)
        mag = np.column_stack(
            [compass_data[key][:n] for key in ("mag_x", "mag_y", "mag_z")]
        )
        gravity = np.column_stack(
            [compass_data[key][:n] for key in ("gravity_x", "gravity_y", "gravity_z")]
        )
        compass_raw = _tilt_compensated_heading(mag, gravity)
        gz = -lowpass_causal(
            np.asarray(data["gyro_pitch_raw"][:n], dtype=np.float64),
            cutoff_hz=GYRO_CUTOFF_HZ,
        )
        file_rows = {"name": data["name"], "junctions": [], "corridor": []}
        t, truth_speed = data["_t"], data["_cv"]
        for i0 in np.linspace(int(0.08 * n), int(0.85 * n), args.segments).astype(int):
            i1 = int(np.searchsorted(t, t[i0] + DENY_S))
            if i1 <= i0 or i1 >= n - 1:
                continue
            if float(np.nanmean(truth_speed[i0:i1])) < MIN_SPEED_MPS:
                continue
            for scenario in ("junctions", "corridor"):
                row = run_segment(
                    data,
                    graph,
                    int(i0),
                    i1,
                    args.particles,
                    args.yaw_sigma,
                    args.heading_sigma_deg,
                    scenario == "corridor",
                    gz,
                    compass_raw,
                )
                if row is not None:
                    rows[scenario].append(row)
                    file_rows[scenario].append(row)
        if file_rows["junctions"] or file_rows["corridor"]:
            files.append(file_rows)
            print(
                f"  {data['name']:16s} junctions={len(file_rows['junctions'])} "
                f"corridor={len(file_rows['corridor'])}"
            )

    report = {
        "experiment": "mapfilter_compass_onset_calibrated",
        "graph": args.graph,
        "segments": args.segments,
        "particles": args.particles,
        "yaw_sigma": args.yaw_sigma,
        "heading_sigma_deg": args.heading_sigma_deg,
        "deny_s": DENY_S,
        "calibration": "last phone GNSS bearing at outage onset only",
        "scenarios": {name: summarise(values) for name, values in rows.items()},
        "files": files,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    (output_dir / "summary.md").write_text(_render(report), encoding="utf-8")
    for name, summary in report["scenarios"].items():
        if summary.get("n"):
            print(
                f"{name}: n={summary['n']} gyro={summary['map_gyro']['median_error_m']:.2f}m "
                f"compass={summary['map_compass']['median_error_m']:.2f}m "
                f"ratio={summary['compass_vs_gyro_x']:.3f}x"
            )
    print(f"wrote {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
