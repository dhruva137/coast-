"""Does an offline OSM map rescue dead reckoning through a GNSS outage?

This is the experiment the whole architecture rests on.
`run_heading_ablation.py` established that free-inertial DR cannot meet the
ISRO bar even with a perfect yaw sensor (84/186 segments pass with the car's
own CAN yaw rate substituted in). If the map does not close that gap, nothing
in the current design does.

Protocol
--------
For each drive with paired CAN ground truth:

1. Force a 60 s GNSS outage at road speed.
2. Dead-reckon through it (`outage_replay.run_outage_replay`).
3. Constrain the dead-reckoned track with Hidden Markov map matching against
   an OpenStreetMap graph (`lab/nav/mapmatch.py`, Newson & Krumm 2009).
4. Score free-DR and map-aided against the CAN 10 Hz trajectory.

Independence guarantee
----------------------
The graph is built by `maps/osm_extract.py` from OpenStreetMap alone. Its
metadata carries `built_from_drive_data: false`, and this script asserts that
flag before scoring anything. This matters because the superseded
`lab/stress/map_aid.py` snapped to a polyline derived from the evaluated
drive's own GNSS -- including the interval under test -- which cannot be
presented as evidence. If the assertion fails, the run aborts rather than
reporting a number.

Run:
    python lab/stress/run_mapmatch_eval.py [--segments N] [--files N]

Writes lab/stress/results/mapmatch/{report.json,summary.md}.
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

from load_iovnbd import (  # noqa: E402
    attach_vehicle_truth,
    find_smartphone_csvs,
    load_smartphone_csv,
)
from mapmatch import MapGraph, match  # noqa: E402
from outage_replay import run_outage_replay  # noqa: E402

EARTH_R_M = 6_371_008.8
DENY_S = 60.0
MIN_SPEED_MPS = 8.0
MATCH_DECIMATE = 10  # 10 Hz DR track -> 1 Hz for matching
DEFAULT_GRAPH = "maps/graphs/iovnbd_midlands.graph.npz"
METHOD = "idr_lean"


def _enu_to_lla(
    xy: np.ndarray, lat0: float, lon0: float
) -> tuple[np.ndarray, np.ndarray]:
    lat = lat0 + np.degrees(xy[:, 1] / EARTH_R_M)
    lon = lon0 + np.degrees(xy[:, 0] / (EARTH_R_M * math.cos(math.radians(lat0))))
    return lat, lon


def _err_m(lat_a: np.ndarray, lon_a: np.ndarray, lat_b: float, lon_b: float) -> float:
    dn = math.radians(float(lat_a[-1]) - lat_b) * EARTH_R_M
    de = (
        math.radians(float(lon_a[-1]) - lon_b)
        * EARTH_R_M
        * math.cos(math.radians(lat_b))
    )
    return float(math.hypot(de, dn))


def in_graph_coverage(data: dict[str, Any], graph: MapGraph) -> bool:
    """Is this drive inside the graph's bounding box?

    IO-VNBD spans the UK Midlands, Derbyshire and several regions of France,
    while one OSM extract covers one bbox. A drive outside coverage finds no
    candidates, so the matcher passes it through unchanged and `map_error ==
    free_error`. Scoring those rows would silently dilute the result toward
    "the map does nothing", so they are excluded and the coverage fraction is
    reported instead.
    """
    m = graph.meta
    lat = float(np.nanmedian(data["lat"]))
    lon = float(np.nanmedian(data["lon"]))
    return (
        m.get("bbox_lat_min", -90.0) <= lat <= m.get("bbox_lat_max", 90.0)
        and m.get("bbox_lon_min", -180.0) <= lon <= m.get("bbox_lon_max", 180.0)
    )


def run_file(
    data: dict[str, Any], graph: MapGraph, segments: int
) -> list[dict[str, Any]]:
    n = min(int(data["n"]), int(data.get("can_n", 0)))
    if n < 5000:
        return []
    t = np.asarray(data["t_s"][:n], dtype=np.float64)
    can_lat = np.asarray(data["can_lat"][:n], dtype=np.float64)
    can_lon = np.asarray(data["can_lon"][:n], dtype=np.float64)
    can_v = np.asarray(data["can_speed_mps"][:n], dtype=np.float64)
    rows: list[dict[str, Any]] = []

    for i0 in np.linspace(int(0.08 * n), int(0.85 * n), segments).astype(int):
        i1 = int(np.searchsorted(t, t[i0] + DENY_S))
        if i1 >= n - 1 or float(np.nanmean(can_v[i0:i1])) < MIN_SPEED_MPS:
            continue
        try:
            r = run_outage_replay(data, deny_s=DENY_S, start_idx=i0)
        except (ValueError, IndexError):
            continue
        if r.get("truth_source") != "can_10hz":
            continue
        est = r["est"].get(METHOD)
        if est is None or est.shape[0] < 20:
            continue

        lat0, lon0 = float(can_lat[0]), float(can_lon[0])
        dr_lat, dr_lon = _enu_to_lla(est, lat0, lon0)
        end_lat, end_lon = float(can_lat[i1 - 1]), float(can_lon[i1 - 1])
        free_err = _err_m(dr_lat, dr_lon, end_lat, end_lon)

        sub = slice(0, dr_lat.size, MATCH_DECIMATE)
        t_sub = t[i0 : i0 + dr_lat.size][sub]
        heading = np.degrees(np.arctan2(*np.gradient(est[sub], axis=0).T[::-1])) % 360.0
        try:
            m = match(dr_lat[sub], dr_lon[sub], graph, t_s=t_sub, heading_deg=heading)
        except (ValueError, IndexError):
            continue
        map_err = _err_m(m.lat, m.lon, end_lat, end_lon)

        dt = np.diff(t[i0:i1], prepend=t[i0])
        dist = float(np.nansum(np.clip(can_v[i0:i1], 0, None) * np.clip(dt, 0, 0.5)))
        rows.append(
            {
                "start_idx": int(i0),
                "distance_m": dist,
                "free_error_m": free_err,
                "map_error_m": map_err,
                "free_drift_pct": 100.0 * free_err / max(dist, 1.0),
                "map_drift_pct": 100.0 * map_err / max(dist, 1.0),
                "free_m_per_km": free_err / max(dist, 1.0) * 1000.0,
                "map_m_per_km": map_err / max(dist, 1.0) * 1000.0,
                "matched_frac": float(m.n_matched / max(m.n_points, 1)),
                "free_pass": bool(
                    100.0 * free_err / max(dist, 1.0) < 10.0
                    and free_err / max(dist, 1.0) * 1000.0 < 100.0
                ),
                "map_pass": bool(
                    100.0 * map_err / max(dist, 1.0) < 10.0
                    and map_err / max(dist, 1.0) * 1000.0 < 100.0
                ),
            }
        )
    return rows


def write_summary(path: Path, report: dict[str, Any]) -> None:
    s = report["summary"]
    lines = [
        "# Map-aided dead reckoning through a 60 s GNSS outage",
        "",
        f"Graph: `{report['graph']}` - {report['graph_meta'].get('n_edges', '?')} edges, "
        f"{report['graph_meta'].get('total_edge_length_km', 0):.0f} km, "
        f"built from OpenStreetMap only "
        f"(`built_from_drive_data: {report['graph_meta'].get('built_from_drive_data')}`).",
        "",
        f"Drives scored: **{report['n_files']}** of "
        f"{report['n_drives_with_can']} with CAN truth | segments: **{s['n']}** | "
        f"method: `{METHOD}`",
        "",
        f"{len(report['skipped_outside_coverage'])} drives were skipped as "
        "outside the graph bounding box. IO-VNBD spans the UK Midlands, "
        "Derbyshire and several regions of France; one OSM extract covers one "
        "bbox. Skipped drives would score `map_error == free_error` and "
        "silently dilute the result toward \"the map does nothing\", so they "
        "are excluded rather than counted.",
        "",
        "| | median error | median drift % | PASS_ISRO |",
        "|---|---:|---:|---:|",
        f"| Free DR | {s['free_median_error_m']:.1f} m | "
        f"{s['free_median_drift_pct']:.1f} | {s['free_pass']}/{s['n']} |",
        f"| **Map-aided** | **{s['map_median_error_m']:.1f} m** | "
        f"**{s['map_median_drift_pct']:.1f}** | **{s['map_pass']}/{s['n']}** |",
        "",
        f"Improvement: **{s['improvement_x']:.2f}x** on median error. "
        f"Segments where the map helped: {s['helped']}/{s['n']}. "
        f"Segments where it hurt: {s['hurt']}/{s['n']}.",
        "",
        "## Honesty notes",
        "",
        "- The map never sees the evaluated drive. The graph is built from "
        "OpenStreetMap by `maps/osm_extract.py`; this script asserts "
        "`built_from_drive_data == false` before scoring. Contrast "
        "`lab/stress/map_aid.py`, which snapped to the drive's own GNSS "
        "polyline and is not admissible.",
        "- Map matching can **hurt**: snapping to a confidently wrong road is "
        "worse than an honest drift. The `hurt` count above is that failure "
        "mode, reported rather than hidden.",
        f"- The DR track is decimated {MATCH_DECIMATE}:1 (10 Hz to 1 Hz) before "
        "matching, which is standard for HMM map matching and keeps the "
        "Viterbi tractable.",
        "- Scoring is final-position error at the end of the outage, against "
        "the CAN trajectory.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--segments", type=int, default=8)
    ap.add_argument("--files", type=int, default=0)
    ap.add_argument("--graph", default=DEFAULT_GRAPH)
    args = ap.parse_args()

    graph = MapGraph.load(args.graph)
    meta = graph.meta
    if meta.get("built_from_drive_data", True):
        print(
            "ABORT: graph metadata does not assert independence from the drive "
            "data. A map derived from the evaluated trajectory cannot be scored.",
            file=sys.stderr,
        )
        return 2
    print(
        f"graph: {meta.get('n_edges')} edges, "
        f"{meta.get('total_edge_length_km', 0):.0f} km, source={meta.get('source')}"
    )

    csvs = find_smartphone_csvs()
    if args.files:
        csvs = csvs[: args.files]
    files: list[dict[str, Any]] = []
    skipped_coverage: list[str] = []
    n_can = 0
    for p in csvs:
        try:
            data = attach_vehicle_truth(load_smartphone_csv(p))
        except (OSError, ValueError):
            continue
        if data.get("truth_source") != "can_10hz":
            continue
        n_can += 1
        if not in_graph_coverage(data, graph):
            skipped_coverage.append(data["name"])
            continue
        rows = run_file(data, graph, args.segments)
        if not rows:
            continue
        files.append({"name": data["name"], "rows": rows})
        free = np.median([r["free_error_m"] for r in rows])
        mapd = np.median([r["map_error_m"] for r in rows])
        print(
            f"  {data['name']:16s} n={len(rows):3d} "
            f"free={free:7.1f}m map={mapd:7.1f}m "
            f"pass {sum(r['free_pass'] for r in rows)}->{sum(r['map_pass'] for r in rows)}"
        )

    rows = [r for f in files for r in f["rows"]]
    if not rows:
        print("no scorable segments", file=sys.stderr)
        return 1
    free = np.array([r["free_error_m"] for r in rows])
    mapd = np.array([r["map_error_m"] for r in rows])
    summary = {
        "n": len(rows),
        "free_median_error_m": float(np.median(free)),
        "map_median_error_m": float(np.median(mapd)),
        "free_median_drift_pct": float(np.median([r["free_drift_pct"] for r in rows])),
        "map_median_drift_pct": float(np.median([r["map_drift_pct"] for r in rows])),
        "free_pass": int(sum(r["free_pass"] for r in rows)),
        "map_pass": int(sum(r["map_pass"] for r in rows)),
        "improvement_x": float(np.median(free) / max(np.median(mapd), 1e-6)),
        "helped": int(np.sum(mapd < free)),
        "hurt": int(np.sum(mapd > free)),
    }
    report = {
        "graph": args.graph,
        "graph_meta": meta,
        "n_files": len(files),
        "n_drives_with_can": n_can,
        "skipped_outside_coverage": skipped_coverage,
        "deny_s": DENY_S,
        "method": METHOD,
        "summary": summary,
        "files": files,
    }
    out_dir = _STRESS / "results" / "mapmatch"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_summary(out_dir / "summary.md", report)

    print(
        f"\nfree DR   : median {summary['free_median_error_m']:8.1f} m  "
        f"drift {summary['free_median_drift_pct']:5.1f}%  "
        f"PASS {summary['free_pass']}/{summary['n']}"
    )
    print(
        f"map-aided : median {summary['map_median_error_m']:8.1f} m  "
        f"drift {summary['map_median_drift_pct']:5.1f}%  "
        f"PASS {summary['map_pass']}/{summary['n']}"
    )
    print(
        f"improvement {summary['improvement_x']:.2f}x | "
        f"helped {summary['helped']} | hurt {summary['hurt']}"
    )
    print(f"\nwrote {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
