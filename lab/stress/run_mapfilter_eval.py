"""Does putting the map inside the filter loop beat free dead reckoning?

This is the falsification test for `docs/ARCHITECTURE_V2.md`. That document
commits, in advance, to three ways this design could be shown wrong:

1. If the road-constrained filter does not beat free DR on the same segments
   against CAN truth, the core claim is refuted.
2. If branch-decision accuracy at junctions is near chance, the gyro carries no
   usable turn evidence and the map cannot be used this way at all.
3. If posterior spread does not correlate with actual error, the uncertainty is
   decorative and must not be shown to a user as if it meant something.

All three are computed here. The point of writing them down first is that the
evaluation cannot then be tuned until it agrees.

Scenarios
---------
``junctions``  the segment as it really is, branches live. This is what
               IO-VNBD gives us: open road with junctions throughout, which is
               a *harder* case than the ISRO benchmark's tunnel.
``corridor``   the filter is restricted to the true sequence of edges, so no
               branch decision can be got wrong. This is the topological
               equivalent of a tunnel or underpass -- exactly the scenario the
               problem statement's 1 km / 60 kmph benchmark describes -- and it
               isolates along-track error from branch error.

Reporting them separately matters. A corridor number quoted as if it were a
junctions number would be dishonest, and a junctions number quoted as the
tunnel benchmark would undersell the design.

Run:
    python lab/stress/run_mapfilter_eval.py [--segments N] [--particles N]

Writes lab/stress/results/mapfilter/{report.json,summary.md}.
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
for _p in (_STRESS, _LAB / "nav"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

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


def _true_edge_at(graph: MapGraph, lat: float, lon: float, radius_m: float = 60.0) -> int:
    """Edge whose centreline is closest to a true position, or -1."""
    best, best_d = -1, radius_m
    for e in graph.nearby_edges(lat, lon, radius_m):
        _, _, d, _, _ = graph.project(int(e), lat, lon)
        if math.isfinite(d) and d < best_d:
            best, best_d = int(e), d
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


def run_segment(
    data: dict[str, Any],
    graph: MapGraph,
    i0: int,
    i1: int,
    n_particles: int,
    yaw_sigma: float,
    corridor: bool,
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

    allowed: set[int] | None = None
    if corridor:
        # Topologically 1D: the filter may only occupy edges the vehicle really
        # traversed. This models a tunnel, where no branch decision exists.
        allowed = set()
        for k in range(i0, i1, 10):
            e = _true_edge_at(graph, float(cla[k]), float(clo[k]))
            if e >= 0:
                allowed.add(e)
        if not allowed:
            return None

    pf = RoadParticleFilter(
        graph, n_particles=n_particles, yaw_sigma_rad_s=yaw_sigma, allowed_edges=allowed
    )
    if not pf.seed_from_fix(float(cla[i0 - 1]), float(clo[i0 - 1]), heading0):
        return None
    st = None
    for k in range(i0, i1):
        st = pf.step(float(v[k]), float(gz[k]), float(t[k] - t[k - 1]))
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
        "pf_m_per_km": pf_err / max(dist, 1.0) * 1000.0,
        "free_drift_pct": 100.0 * free_err / max(dist, 1.0),
        "spread_m": st.spread_m,
        "on_true_edge": bool(true_edge >= 0 and st.edge == true_edge),
        "true_edge_known": bool(true_edge >= 0),
        "pf_pass": bool(
            100.0 * pf_err / max(dist, 1.0) < 10.0
            and pf_err / max(dist, 1.0) * 1000.0 < 100.0
        ),
        "free_pass": bool(
            100.0 * free_err / max(dist, 1.0) < 10.0
            and free_err / max(dist, 1.0) * 1000.0 < 100.0
        ),
    }


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"n": 0}
    free = np.array([r["free_error_m"] for r in rows])
    pf = np.array([r["pf_error_m"] for r in rows])
    spread = np.array([r["spread_m"] for r in rows])
    known = np.array([r["true_edge_known"] for r in rows])
    on_edge = np.array([r["on_true_edge"] for r in rows])
    # Falsification test 3: does the filter's own uncertainty predict its error?
    corr = float("nan")
    if np.isfinite(spread).sum() > 5 and np.std(spread) > 1e-9:
        corr = float(np.corrcoef(spread, pf)[0, 1])
    return {
        "n": len(rows),
        "free_median_error_m": float(np.median(free)),
        "pf_median_error_m": float(np.median(pf)),
        "free_median_drift_pct": float(np.median([r["free_drift_pct"] for r in rows])),
        "pf_median_drift_pct": float(np.median([r["pf_drift_pct"] for r in rows])),
        "free_pass": int(sum(r["free_pass"] for r in rows)),
        "pf_pass": int(sum(r["pf_pass"] for r in rows)),
        "improvement_x": float(np.median(free) / max(np.median(pf), 1e-6)),
        "helped": int(np.sum(pf < free)),
        "hurt": int(np.sum(pf > free)),
        "edge_accuracy": (
            float(on_edge[known].mean()) if int(known.sum()) > 0 else float("nan")
        ),
        "edge_accuracy_n": int(known.sum()),
        "spread_error_correlation": corr,
    }


def write_summary(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Road-constrained particle filter vs free dead reckoning",
        "",
        "Falsification test for `docs/ARCHITECTURE_V2.md`. Ground truth is the "
        "paired CAN 10 Hz trajectory.",
        "",
        f"Graph: {report['graph_meta'].get('n_edges')} edges, "
        f"{report['graph_meta'].get('total_edge_length_km', 0):.0f} km, "
        f"OpenStreetMap only "
        f"(`built_from_drive_data: {report['graph_meta'].get('built_from_drive_data')}`). "
        f"Particles: {report['particles']}, yaw sigma {report['yaw_sigma']} rad/s, "
        f"gyro low-passed causally at {GYRO_CUTOFF_HZ} Hz.",
        "",
    ]
    for scen in ("junctions", "corridor"):
        s = report["scenarios"].get(scen)
        if not s or not s.get("n"):
            continue
        label = {
            "junctions": "Junctions live (open road) - HARDER than the ISRO benchmark",
            "corridor": "Corridor (topologically 1D) - models a tunnel/underpass",
        }[scen]
        lines += [
            f"## {label}",
            "",
            "| | median error | median drift % | PASS_ISRO |",
            "|---|---:|---:|---:|",
            f"| Free DR | {s['free_median_error_m']:.1f} m | "
            f"{s['free_median_drift_pct']:.1f} | {s['free_pass']}/{s['n']} |",
            f"| **Map-in-loop PF** | **{s['pf_median_error_m']:.1f} m** | "
            f"**{s['pf_median_drift_pct']:.1f}** | **{s['pf_pass']}/{s['n']}** |",
            "",
            f"Improvement **{s['improvement_x']:.2f}x** | helped {s['helped']} | "
            f"hurt {s['hurt']}",
            "",
            f"- Correct-edge rate: "
            f"{100.0 * s['edge_accuracy']:.0f}% of {s['edge_accuracy_n']} segments "
            "where the true edge could be identified (falsification test 2).",
            f"- Spread-vs-error correlation: {s['spread_error_correlation']:+.2f} "
            "(falsification test 3 - if this is near zero the uncertainty is "
            "decorative and must not be shown to a user).",
            "",
        ]
    lines += [
        "## Reading these two tables",
        "",
        "The corridor scenario is the one the ISRO benchmark actually describes: "
        "a tunnel has no junctions, so no branch decision can be got wrong and "
        "only along-track speed error accumulates. The junctions scenario is "
        "open road with live branches, which IO-VNBD gives us throughout and "
        "which is strictly harder than the benchmark.",
        "",
        "Quoting a corridor number as though it were a junctions number would be "
        "dishonest; quoting a junctions number as the tunnel benchmark would "
        "undersell the design. They are reported separately for that reason.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--segments", type=int, default=6)
    ap.add_argument("--files", type=int, default=0)
    ap.add_argument("--particles", type=int, default=600)
    ap.add_argument("--yaw-sigma", type=float, default=0.30)
    ap.add_argument("--graph", default=DEFAULT_GRAPH)
    args = ap.parse_args()

    graph = MapGraph.load(args.graph)
    if graph.meta.get("built_from_drive_data", True):
        print("ABORT: graph is not independent of the drive data.", file=sys.stderr)
        return 2

    csvs = find_smartphone_csvs()
    if args.files:
        csvs = csvs[: args.files]
    scen_rows: dict[str, list[dict[str, Any]]] = {"junctions": [], "corridor": []}
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
        gz = -lowpass_causal(
            np.asarray(data["gyro_pitch_raw"][:n], dtype=np.float64),
            cutoff_hz=GYRO_CUTOFF_HZ,
        )
        t, cv = data["_t"], data["_cv"]
        file_rows = {"name": data["name"], "junctions": [], "corridor": []}
        for i0 in np.linspace(int(0.08 * n), int(0.85 * n), args.segments).astype(int):
            i1 = int(np.searchsorted(t, t[i0] + DENY_S))
            if i1 >= n - 1 or float(np.nanmean(cv[i0:i1])) < MIN_SPEED_MPS:
                continue
            for scen in ("junctions", "corridor"):
                row = run_segment(
                    data, graph, int(i0), i1, args.particles, args.yaw_sigma,
                    corridor=(scen == "corridor"), gz=gz,
                )
                if row is not None:
                    scen_rows[scen].append(row)
                    file_rows[scen].append(row)
        if file_rows["junctions"] or file_rows["corridor"]:
            per_file.append(file_rows)
            jn = file_rows["junctions"]
            print(
                f"  {data['name']:16s} junctions n={len(jn):2d} "
                f"free={np.median([r['free_error_m'] for r in jn]) if jn else float('nan'):7.1f}m "
                f"pf={np.median([r['pf_error_m'] for r in jn]) if jn else float('nan'):7.1f}m"
            )

    report = {
        "graph": args.graph,
        "graph_meta": graph.meta,
        "particles": args.particles,
        "yaw_sigma": args.yaw_sigma,
        "deny_s": DENY_S,
        "scenarios": {k: summarise(v) for k, v in scen_rows.items()},
        "files": per_file,
    }
    out_dir = _STRESS / "results" / "mapfilter"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_summary(out_dir / "summary.md", report)

    for scen in ("junctions", "corridor"):
        s = report["scenarios"][scen]
        if not s.get("n"):
            continue
        print(
            f"\n{scen.upper()}  n={s['n']}\n"
            f"  free DR : {s['free_median_error_m']:8.1f} m  PASS {s['free_pass']}/{s['n']}\n"
            f"  map PF  : {s['pf_median_error_m']:8.1f} m  PASS {s['pf_pass']}/{s['n']}  "
            f"({s['improvement_x']:.2f}x, helped {s['helped']}, hurt {s['hurt']})\n"
            f"  edge acc: {100.0 * s['edge_accuracy']:.0f}%  "
            f"spread-err corr {s['spread_error_correlation']:+.2f}"
        )
    print(f"\nwrote {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
