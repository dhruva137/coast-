"""Export map-in-loop particle-filter traces for Phase 3 engine visualisation.

Writes ``lab/stress/results/traces/<drive>_<t0>.json`` with per-step particles,
``n_eff``, edge posterior, truth, free-DR ghost, and estimate.

Default mode replays frozen outages from
``lab/stress/results/mapfilter/report.json`` (drive + ``start_idx``, 60 s,
600 particles, yaw_sigma 0.30, junctions not corridor) so the demo matches
the 2.02x benchmark instead of ranking the hardest turns.

Honesty
-------
- Real path: IO-VNBD outage + midlands OSM graph + ``RoadParticleFilter``.
  Particles are downsampled for transport (``particles_shown`` /
  ``particles_total``) — never invented.
- Demo set: two outages where PF helped and one where it hurt, labelled in
  meta (``pf_helped``, ``ratio``, ``matched_benchmark``).
- Synthetic path: a tiny labelled plumbing graph + filter run. Meta carries
  ``honesty: "SYNTHETIC"``. Do not quote as field evidence.

Run
---
    python lab/stress/export_filter_trace.py
    python lab/stress/export_filter_trace.py --synthetic
    python lab/stress/export_filter_trace.py --mode max-turn
    python lab/stress/export_filter_trace.py --drive S-S1.csv --start-idx 18628

Requires local IO-VNBD under ``data/raw/IO-VNBD`` and
``maps/graphs/iovnbd_midlands.graph.npz`` for the real path.
Does not rewrite ``lab/stress/results/mapfilter/report.json``.
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
_REPO = _LAB.parent
for _p in (_STRESS, _LAB / "nav", _REPO / "maps"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from gyro_preprocess import lowpass_causal  # noqa: E402
from load_iovnbd import (  # noqa: E402
    attach_vehicle_truth,
    find_smartphone_csvs,
    load_smartphone_csv,
)
from mapfilter import DEFAULT_ESS_FRACTION, RoadParticleFilter  # noqa: E402
from mapmatch import MapGraph  # noqa: E402

EARTH_R_M = 6_371_008.8
DENY_S = 60.0
MIN_SPEED_MPS = 8.0
GYRO_CUTOFF_HZ = 0.5
SEED_SAMPLES = 50
DEFAULT_GRAPH = "maps/graphs/iovnbd_midlands.graph.npz"
# Match run_mapfilter_eval.py --particles 600 (old exporter defaulted to 200).
DEFAULT_PARTICLES = 600
DEFAULT_SHOW = 180
DEFAULT_YAW_SIGMA = 0.30
DEFAULT_REPORT = _STRESS / "results" / "mapfilter" / "report.json"
BENCHMARK_REPORT = DEFAULT_REPORT
GRAPH_PAD_M = 120.0
EDGE_SAMPLE_STRIDE = 5
OUT_DIR = _STRESS / "results" / "traces"
# Demo windows: 60 s at road speed, errors that fit on a map. km-scale CAN
# glitches and PF blow-ups are real but unreadable as a particle-cloud demo.
DEMO_MIN_DIST_M = 300.0
DEMO_MAX_DIST_M = 2500.0
DEMO_MAX_END_ERROR_M = 800.0
N_HELP_DEFAULT = 2
N_HURT_DEFAULT = 1


def _gcd_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dn = math.radians(lat2 - lat1) * EARTH_R_M
    de = math.radians(lon2 - lon1) * EARTH_R_M * math.cos(math.radians(lat1))
    return math.hypot(de, dn)


def _enu_step(v: float, yaw: float, dt: float, lat: float, lon: float) -> tuple[float, float]:
    dn = v * math.cos(yaw) * dt
    de = v * math.sin(yaw) * dt
    nlat = lat + math.degrees(dn / EARTH_R_M)
    nlon = lon + math.degrees(de / (EARTH_R_M * math.cos(math.radians(lat))))
    return nlat, nlon


def _eval_seed_yaw(
    cla: np.ndarray, clo: np.ndarray, i0: int
) -> tuple[float, float]:
    """Exact ``run_mapfilter_eval.run_segment`` seed: 50 samples, hypot >= 10 m."""
    j = max(0, i0 - SEED_SAMPLES)
    dn = math.radians(float(cla[i0 - 1] - cla[j])) * EARTH_R_M
    de = (
        math.radians(float(clo[i0 - 1] - clo[j]))
        * EARTH_R_M
        * math.cos(math.radians(float(cla[j])))
    )
    if math.hypot(dn, de) < 10.0:
        return float("nan"), float("nan")
    yaw0 = math.atan2(de, dn)
    return yaw0, math.degrees(yaw0) % 360.0


def _seed_yaw(
    cla: np.ndarray, clo: np.ndarray, i0: int
) -> tuple[float, float]:
    """Heading from pre-outage CAN track; widen lookback if the car was slow.

    Benchmark replay uses ``_eval_seed_yaw`` only. This wider lookback is for
    the opt-in max-turn picker.
    """
    yaw0, heading0 = _eval_seed_yaw(cla, clo, i0)
    if math.isfinite(yaw0):
        return yaw0, heading0
    for lookback in (100, 200, 400):
        j = max(0, i0 - lookback)
        if j >= i0 - 1:
            continue
        dn = math.radians(float(cla[i0 - 1] - cla[j])) * EARTH_R_M
        de = (
            math.radians(float(clo[i0 - 1] - clo[j]))
            * EARTH_R_M
            * math.cos(math.radians(float(cla[j])))
        )
        if math.hypot(dn, de) >= 10.0:
            yaw0 = math.atan2(de, dn)
            return yaw0, math.degrees(yaw0) % 360.0
    return float("nan"), float("nan")


def _free_dr(
    t: np.ndarray, v: np.ndarray, gz: np.ndarray, lat0: float, lon0: float, yaw0: float
) -> tuple[float, float]:
    """Eval's flat-earth free DR (end pose only)."""
    dt = np.diff(t)
    yaw = yaw0 + np.cumsum(gz[:-1] * dt)
    x = float(np.sum(v[:-1] * np.sin(yaw) * dt))
    y = float(np.sum(v[:-1] * np.cos(yaw) * dt))
    lat = lat0 + math.degrees(y / EARTH_R_M)
    lon = lon0 + math.degrees(x / (EARTH_R_M * math.cos(math.radians(lat0))))
    return lat, lon


def _free_dr_trajectory(
    t: np.ndarray, v: np.ndarray, gz: np.ndarray, lat0: float, lon0: float, yaw0: float
) -> tuple[np.ndarray, np.ndarray]:
    """Per-step free-DR lat/lon matching eval ``_free_dr`` prefix sums."""
    dt = np.diff(t)
    if dt.size == 0:
        return np.zeros(0), np.zeros(0)
    yaw = yaw0 + np.cumsum(gz[:-1] * dt)
    x = np.cumsum(v[:-1] * np.sin(yaw) * dt)
    y = np.cumsum(v[:-1] * np.cos(yaw) * dt)
    clat = math.cos(math.radians(lat0))
    lats = lat0 + np.degrees(y / EARTH_R_M)
    lons = lon0 + np.degrees(x / (EARTH_R_M * clat))
    return lats, lons


def load_benchmark_junctions(report_path: Path | None = None) -> list[dict[str, Any]]:
    """Read frozen junctions outages. Never writes the report."""
    path = Path(report_path) if report_path is not None else DEFAULT_REPORT
    report = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for f in report.get("files") or []:
        name = str(f.get("name", ""))
        for j in f.get("junctions") or []:
            free_e = float(j["free_error_m"])
            pf_e = float(j["pf_error_m"])
            rows.append(
                {
                    "name": name,
                    "start_idx": int(j["start_idx"]),
                    "distance_m": float(j.get("distance_m", 0.0)),
                    "free_error_m": free_e,
                    "pf_error_m": pf_e,
                    "on_true_edge": bool(j.get("on_true_edge", False)),
                    "pf_helped": bool(pf_e < free_e),
                }
            )
    return rows


def demo_usable(row: dict[str, Any]) -> bool:
    dist = float(row["distance_m"])
    free_e = float(row["free_error_m"])
    pf_e = float(row["pf_error_m"])
    if not (DEMO_MIN_DIST_M <= dist <= DEMO_MAX_DIST_M):
        return False
    if not (math.isfinite(free_e) and math.isfinite(pf_e)):
        return False
    if max(free_e, pf_e) > DEMO_MAX_END_ERROR_M:
        return False
    return True


def _improvement_x(row: dict[str, Any]) -> float:
    return float(row["free_error_m"]) / max(float(row["pf_error_m"]), 1e-6)


def select_demo_outages(
    rows: list[dict[str, Any]],
    *,
    n_help: int = N_HELP_DEFAULT,
    n_hurt: int = N_HURT_DEFAULT,
) -> list[dict[str, Any]]:
    """Two helped + one hurt among plottable windows. Not max-turn, not wins-only."""
    usable = [r for r in rows if demo_usable(r)]
    helped = [r for r in usable if r["pf_error_m"] < r["free_error_m"]]
    hurt = [r for r in usable if r["pf_error_m"] > r["free_error_m"]]
    helped.sort(
        key=lambda r: (_improvement_x(r), 1 if r.get("on_true_edge") else 0),
        reverse=True,
    )
    picked: list[dict[str, Any]] = []
    used_drives: set[str] = set()
    for r in helped:
        if r["name"] in used_drives:
            continue
        picked.append(r)
        used_drives.add(r["name"])
        if len(picked) >= n_help:
            break
    if len(picked) < n_help:
        for r in helped:
            if r in picked:
                continue
            picked.append(r)
            used_drives.add(r["name"])
            if len(picked) >= n_help:
                break
    if n_hurt > 0 and hurt:
        hurt_sorted = sorted(
            hurt, key=lambda r: float(r["pf_error_m"]) / max(float(r["free_error_m"]), 1e-6)
        )
        median = hurt_sorted[len(hurt_sorted) // 2]
        med_h = float(median["pf_error_m"]) / max(float(median["free_error_m"]), 1e-6)
        diversified = [r for r in hurt_sorted if r["name"] not in used_drives]
        pool = diversified or hurt_sorted
        remaining = list(pool)
        for _ in range(n_hurt):
            if not remaining:
                break
            choice = min(
                remaining,
                key=lambda r: abs(
                    float(r["pf_error_m"]) / max(float(r["free_error_m"]), 1e-6) - med_h
                ),
            )
            picked.append(choice)
            used_drives.add(choice["name"])
            remaining = [r for r in remaining if r is not choice]
    # Hurt first so mtime-based ``latest.json`` lands on a win (helped last).
    hurt_out = [p for p in picked if p["pf_error_m"] > p["free_error_m"]]
    help_out = [p for p in picked if p["pf_error_m"] < p["free_error_m"]]
    return hurt_out + help_out


def _load_drive_by_name(name: str) -> dict[str, Any]:
    csvs = find_smartphone_csvs()
    want = name.lower()
    exact = [p for p in csvs if p.name.lower() == want]
    if exact:
        path = exact[0]
    else:
        fuzzy = [p for p in csvs if want in p.name.lower()]
        if not fuzzy:
            raise FileNotFoundError(f"IO-VNBD drive not found: {name}")
        path = fuzzy[0]
    data = attach_vehicle_truth(load_smartphone_csv(path))
    if data.get("truth_source") != "can_10hz":
        raise RuntimeError(f"{path.name} has no CAN 10 Hz truth")
    return data


def _window_end_idx(t: np.ndarray, i0: int, n: int) -> int:
    i1 = int(np.searchsorted(t, float(t[i0]) + DENY_S))
    return min(i1, n)


def _edge_posterior(pf: RoadParticleFilter, top_k: int = 8) -> list[list[float]]:
    mass: dict[int, float] = {}
    for e, w in zip(pf.edge.tolist(), pf.w.tolist()):
        mass[int(e)] = mass.get(int(e), 0.0) + float(w)
    ranked = sorted(mass.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
    return [[int(e), round(float(p), 6)] for e, p in ranked]


def _particle_snapshot(
    pf: RoadParticleFilter, show: int, rng: np.random.Generator
) -> tuple[list[dict[str, float]], int, int]:
    """Downsample living particles; never invent positions."""
    n = int(pf.n)
    show_n = min(int(show), n)
    if show_n < n:
        idx = np.sort(rng.choice(n, size=show_n, replace=False))
    else:
        idx = np.arange(n)
    out: list[dict[str, float]] = []
    for i in idx:
        i = int(i)
        lat, lon, _ = pf._pos_on_edge(int(pf.edge[i]), float(pf.s[i]), bool(pf.forward[i]))
        out.append(
            {
                "e": int(pf.edge[i]),
                "s": round(float(pf.s[i]), 2),
                "w": round(float(pf.w[i]), 6),
                "lat": round(float(lat), 6),
                "lon": round(float(lon), 6),
            }
        )
    return out, show_n, n


def _estimate_heading(pf: RoadParticleFilter, edge: int) -> float:
    """Weight-mean bearing of particles on the MAP edge; else MAP particle."""
    bears: list[float] = []
    weights: list[float] = []
    for i in range(pf.n):
        if int(pf.edge[i]) != edge:
            continue
        _, _, b = pf._pos_on_edge(int(pf.edge[i]), float(pf.s[i]), bool(pf.forward[i]))
        bears.append(float(b))
        weights.append(float(pf.w[i]))
    if not bears:
        i = int(np.argmax(pf.w))
        _, _, b = pf._pos_on_edge(int(pf.edge[i]), float(pf.s[i]), bool(pf.forward[i]))
        return float(b) % 360.0
    # Circular mean via unit vectors.
    w = np.asarray(weights, dtype=np.float64)
    w = w / max(float(w.sum()), 1e-300)
    rad = np.radians(np.asarray(bears, dtype=np.float64))
    ang = math.atan2(float(np.sum(w * np.sin(rad))), float(np.sum(w * np.cos(rad))))
    return math.degrees(ang) % 360.0


def _edge_polyline(graph: MapGraph, edge: int) -> list[list[float]]:
    a, b = int(graph.edge_ptr[edge]), int(graph.edge_ptr[edge + 1])
    nodes = graph.edge_nodes[a:b]
    return [
        [round(float(graph.node_lat[int(n)]), 7), round(float(graph.node_lon[int(n)]), 7)]
        for n in nodes
    ]


def _export_local_graph(
    graph: MapGraph,
    lat: np.ndarray,
    lon: np.ndarray,
    used_edges: set[int],
    pad_m: float = GRAPH_PAD_M,
) -> dict[str, Any]:
    """Compact subgraph around the drive — full midlands dump would be huge."""
    keep: set[int] = set(used_edges)
    for k in range(0, len(lat), EDGE_SAMPLE_STRIDE):
        for e in graph.nearby_edges(float(lat[k]), float(lon[k]), pad_m):
            keep.add(int(e))
    # Node remapping for a small export.
    node_ids: dict[int, int] = {}
    nodes: list[list[float]] = []
    edges_out: list[dict[str, Any]] = []

    def _nid(raw: int) -> int:
        if raw not in node_ids:
            node_ids[raw] = len(nodes)
            nodes.append(
                [
                    round(float(graph.node_lat[raw]), 7),
                    round(float(graph.node_lon[raw]), 7),
                ]
            )
        return node_ids[raw]

    for e in sorted(keep):
        a_raw = int(graph.edge_u[e])
        b_raw = int(graph.edge_v[e])
        pts = _edge_polyline(graph, e)
        # Ensure polyline endpoints are in the node table.
        if pts:
            # Prefer real u/v indices for topology; pts keep geometry.
            edges_out.append(
                {
                    "id": int(e),
                    "a": _nid(a_raw),
                    "b": _nid(b_raw),
                    "pts": pts,
                }
            )
    return {"nodes": nodes, "edges": edges_out}


def _segment_ok(
    t: np.ndarray,
    cv: np.ndarray,
    cla: np.ndarray,
    clo: np.ndarray,
    i0: int,
    i1: int,
) -> tuple[bool, float]:
    """Return (ok, turn_rad). Reject resets, slow windows, and unsseedable starts."""
    if i1 >= len(t) or i1 - i0 < 200 or i0 < 2:
        return False, 0.0
    dts = np.diff(t[i0:i1])
    if dts.size == 0 or float(np.max(dts)) > 1.5 or float(np.min(dts)) <= 0:
        return False, 0.0
    if float(np.nanmean(cv[i0:i1])) < MIN_SPEED_MPS:
        return False, 0.0
    yaw0, _ = _seed_yaw(cla, clo, i0)
    if not math.isfinite(yaw0):
        return False, 0.0
    e = (
        np.deg2rad(clo[i0:i1] - clo[i0])
        * EARTH_R_M
        * math.cos(math.radians(float(cla[i0])))
    )
    nn = np.deg2rad(cla[i0:i1] - cla[i0]) * EARTH_R_M
    head = np.arctan2(np.gradient(e), np.gradient(nn))
    turn = float(np.ptp(np.unwrap(head)))
    return True, turn


def _pick_all_segments(
    graph: MapGraph,
    drive_substr: str | None,
    t0_s: float | None,
    limit: int = 12,
) -> list[tuple[dict[str, Any], int, int]]:
    """Ranked candidate outages (most turning first) across matching drives."""
    m = graph.meta
    csvs = find_smartphone_csvs()
    if drive_substr:
        csvs = [p for p in csvs if drive_substr.lower() in p.name.lower()]
    ranked: list[tuple[float, dict[str, Any], int, int]] = []
    for p in csvs:
        try:
            d = attach_vehicle_truth(load_smartphone_csv(p))
        except (OSError, ValueError):
            continue
        if d.get("truth_source") != "can_10hz":
            continue
        lat = float(np.nanmedian(d["lat"]))
        lon = float(np.nanmedian(d["lon"]))
        if not (
            m.get("bbox_lat_min", -90.0) <= lat <= m.get("bbox_lat_max", 90.0)
            and m.get("bbox_lon_min", -180.0) <= lon <= m.get("bbox_lon_max", 180.0)
        ):
            continue
        n = min(int(d["n"]), int(d.get("can_n", 0)))
        if n < 5000:
            continue
        t = np.asarray(d["t_s"][:n], dtype=np.float64)
        cv = np.asarray(d["can_speed_mps"][:n], dtype=np.float64)
        cla = np.asarray(d["can_lat"][:n], dtype=np.float64)
        clo = np.asarray(d["can_lon"][:n], dtype=np.float64)

        if t0_s is not None:
            i0 = int(np.searchsorted(t, float(t0_s)))
            i0 = max(SEED_SAMPLES + 1, min(i0, n - 300))
            i1 = int(np.searchsorted(t, t[i0] + DENY_S))
            ok, turn = _segment_ok(t, cv, cla, clo, i0, i1)
            if ok:
                ranked.append((turn, d, i0, i1))
            continue

        for i0 in np.linspace(int(0.1 * n), int(0.8 * n), 50).astype(int):
            i1 = int(np.searchsorted(t, t[i0] + DENY_S))
            ok, turn = _segment_ok(t, cv, cla, clo, int(i0), i1)
            if ok:
                ranked.append((turn, d, int(i0), int(i1)))
    ranked.sort(key=lambda r: r[0], reverse=True)
    # Deduplicate near-identical starts on the same drive.
    out: list[tuple[dict[str, Any], int, int]] = []
    seen: set[tuple[str, int]] = set()
    for _, d, i0, i1 in ranked:
        key = (str(d.get("name")), i0 // 50)
        if key in seen:
            continue
        seen.add(key)
        out.append((d, i0, i1))
        if len(out) >= limit:
            break
    return out


def _pick_segment(
    graph: MapGraph,
    drive_substr: str | None,
    t0_s: float | None,
) -> tuple[dict[str, Any], int, int] | None:
    all_seg = _pick_all_segments(graph, drive_substr, t0_s, limit=1)
    return all_seg[0] if all_seg else None


def run_real_trace(
    graph: MapGraph,
    graph_path: str,
    data: dict[str, Any],
    i0: int,
    i1: int,
    *,
    n_particles: int,
    show: int,
    yaw_sigma: float,
    seed: int = 26168,
    benchmark: dict[str, Any] | None = None,
    eval_seed: bool = True,
) -> dict[str, Any]:
    n = min(int(data["n"]), int(data.get("can_n", 0)))
    t = np.asarray(data["t_s"][:n], dtype=np.float64)
    cla = np.asarray(data["can_lat"][:n], dtype=np.float64)
    clo = np.asarray(data["can_lon"][:n], dtype=np.float64)
    v = np.asarray(data["speed_mps"][:n], dtype=np.float64)
    gz = -lowpass_causal(
        np.asarray(data["gyro_pitch_raw"][:n], dtype=np.float64),
        cutoff_hz=GYRO_CUTOFF_HZ,
    )

    if eval_seed:
        yaw0, heading0 = _eval_seed_yaw(cla, clo, i0)
    else:
        yaw0, heading0 = _seed_yaw(cla, clo, i0)
    if not math.isfinite(yaw0):
        raise RuntimeError("cannot seed yaw from pre-outage CAN track")

    # Same kwargs as run_mapfilter_eval.run_segment (junctions: allowed_edges=None).
    # Do not pass seed= — eval relies on RoadParticleFilter's default (26168).
    pf = RoadParticleFilter(
        graph,
        n_particles=n_particles,
        yaw_sigma_rad_s=yaw_sigma,
        allowed_edges=None,
    )
    if not pf.seed_from_fix(float(cla[i0 - 1]), float(clo[i0 - 1]), heading0):
        raise RuntimeError("filter failed to seed on graph")

    rng = np.random.default_rng(int(seed) + 17)
    free_lats, free_lons = _free_dr_trajectory(
        t[i0 - 1 : i1],
        v[i0 - 1 : i1],
        gz[i0 - 1 : i1],
        float(cla[i0 - 1]),
        float(clo[i0 - 1]),
        yaw0,
    )
    t0 = float(t[i0])
    used_edges: set[int] = set(int(e) for e in pf.edge.tolist())
    steps: list[dict[str, Any]] = []
    last = i1 - 1
    st = None

    for k in range(i0, i1):
        dt = float(t[k] - t[k - 1])
        speed = float(v[k])
        yaw_rate = float(gz[k])
        st = pf.step(speed, yaw_rate, dt, want_position=True)
        if not st.on_graph:
            break

        resampled = bool(st.ess < DEFAULT_ESS_FRACTION * pf.n)
        si = k - i0
        free_lat = float(free_lats[si]) if si < len(free_lats) else float("nan")
        free_lon = float(free_lons[si]) if si < len(free_lons) else float("nan")

        particles, shown, total = _particle_snapshot(pf, show, rng)
        used_edges.update(int(e) for e in pf.edge.tolist())
        heading = _estimate_heading(pf, int(st.edge))

        steps.append(
            {
                "t": round(float(t[k] - t0), 3),
                "particles": particles,
                "particles_shown": shown,
                "particles_total": total,
                "estimate": {
                    "lat": round(float(st.lat), 7),
                    "lon": round(float(st.lon), 7),
                    "edge": int(st.edge),
                    "heading": round(heading, 2),
                },
                "truth": {
                    "lat": round(float(cla[k]), 7),
                    "lon": round(float(clo[k]), 7),
                },
                "free_dr": {
                    "lat": round(free_lat, 7),
                    "lon": round(free_lon, 7),
                },
                "speed_mps": round(speed, 3),
                "yaw_rate": round(yaw_rate, 5),
                "n_eff": round(float(st.ess), 3),
                "resampled": resampled,
                "edge_posterior": _edge_posterior(pf),
            }
        )

    if not steps or st is None:
        raise RuntimeError("no filter steps recorded")

    k_end = i0 + len(steps) - 1
    end_lat, end_lon = float(cla[k_end]), float(clo[k_end])
    pf_end = _gcd_m(end_lat, end_lon, float(st.lat), float(st.lon))
    # Full-window free DR matches eval when the filter completed; otherwise
    # compare the ghost at the last recorded step.
    if k_end == last:
        free_end_lat, free_end_lon = _free_dr(
            t[i0 - 1 : i1],
            v[i0 - 1 : i1],
            gz[i0 - 1 : i1],
            float(cla[i0 - 1]),
            float(clo[i0 - 1]),
            yaw0,
        )
    else:
        si = k_end - i0
        free_end_lat = float(free_lats[si])
        free_end_lon = float(free_lons[si])
    free_end = _gcd_m(end_lat, end_lon, free_end_lat, free_end_lon)
    ratio = float(free_end) / max(float(pf_end), 1e-6)
    if pf_end < free_end:
        outcome = "helped"
    elif pf_end > free_end:
        outcome = "hurt"
    else:
        outcome = "tie"

    drive_name = str(data.get("name", "drive")).replace(".csv", "")
    t0_out = float(t[i0])
    local_graph = _export_local_graph(
        graph, cla[i0:i1], clo[i0:i1], used_edges
    )
    hz = (len(steps) - 1) / max(steps[-1]["t"], 1e-6) if len(steps) > 1 else 10.0
    completed = bool(st.on_graph and (i0 + len(steps)) >= i1)

    meta: dict[str, Any] = {
        "drive": drive_name,
        "t0_s": round(t0_out, 3),
        "start_idx": int(i0),
        "duration_s": round(float(steps[-1]["t"]), 3),
        "hz": round(float(hz), 2),
        "n_particles": int(n_particles),
        "particles_shown_cap": int(show),
        "graph": graph_path.replace("\\", "/"),
        "source": "real IO-VNBD outage, CAN speed truth",
        "honesty": "REAL",
        "built_from_drive_data": bool(graph.meta.get("built_from_drive_data", False)),
        "yaw_sigma_rad_s": float(yaw_sigma),
        "scenario": "junctions",
        "deny_s": DENY_S,
        "matched_benchmark": bool(benchmark is not None),
        "free_end_error_m": round(float(free_end), 3),
        "pf_end_error_m": round(float(pf_end), 3),
        "ratio": round(float(ratio), 4),
        "pf_helped": bool(pf_end < free_end),
        "outcome": outcome,
        "completed_window": completed,
        "notes": (
            "Particles are a downsampled subset of the live filter cloud. "
            "n_eff is effective sample size before resampling. "
            "Do not use spread as confidence (gated; corr≈−0.23). "
            "ratio = free_end_error_m / pf_end_error_m (>1 means PF better)."
        ),
    }
    if benchmark is not None:
        meta["report_free_error_m"] = round(float(benchmark["free_error_m"]), 3)
        meta["report_pf_error_m"] = round(float(benchmark["pf_error_m"]), 3)
        meta["report_ratio"] = round(_improvement_x(benchmark), 4)
        meta["benchmark_drive"] = str(benchmark.get("name", "")).replace(".csv", "")
        meta["benchmark_start_idx"] = int(benchmark["start_idx"])

    return {
        "meta": meta,
        "graph": local_graph,
        "steps": steps,
    }


def _build_synthetic_y_graph() -> MapGraph:
    """Tiny Y-junction graph for plumbing only (not OSM / not field data)."""
    # Nodes: stem south → junction → left / right forks.
    #   0 (52.40000, -1.50000)
    #   1 (52.40100, -1.50000)  junction
    #   2 (52.40200, -1.50080)  left
    #   3 (52.40200, -1.49920)  right
    node_lat = np.array([52.40000, 52.40100, 52.40200, 52.40200], dtype=np.float64)
    node_lon = np.array([-1.50000, -1.50000, -1.50080, -1.49920], dtype=np.float64)
    # Edges: 0: 0→1, 1: 1→2, 2: 1→3
    edge_u = np.array([0, 1, 1], dtype=np.int64)
    edge_v = np.array([1, 2, 3], dtype=np.int64)
    edge_nodes = np.array([0, 1, 1, 2, 1, 3], dtype=np.int64)
    edge_ptr = np.array([0, 2, 4, 6], dtype=np.int64)

    def _len_bear(a: int, b: int) -> tuple[float, float]:
        dn = math.radians(float(node_lat[b] - node_lat[a])) * EARTH_R_M
        de = (
            math.radians(float(node_lon[b] - node_lon[a]))
            * EARTH_R_M
            * math.cos(math.radians(float(node_lat[a])))
        )
        return math.hypot(de, dn), math.degrees(math.atan2(de, dn)) % 360.0

    lens, bears = [], []
    for u, v in zip(edge_u, edge_v):
        L, B = _len_bear(int(u), int(v))
        lens.append(L)
        bears.append(B)
    edge_len_m = np.asarray(lens, dtype=np.float64)
    edge_bearing_deg = np.asarray(bears, dtype=np.float64)
    # One segment per edge.
    seg_ptr = np.array([0, 1, 2, 3], dtype=np.int64)
    seg_len_m = edge_len_m.copy()
    seg_bearing_deg = edge_bearing_deg.copy()

    # Adjacency: at each node, directed edge codes (forward < n_edges).
    # node0: leave via edge0 forward
    # node1: arrive edge0; leave edge1 fwd, edge2 fwd; also reverse edge0
    # node2: arrive edge1; reverse edge1
    # node3: arrive edge2; reverse edge2
    n_edges = 3
    adj: list[list[int]] = [[] for _ in range(4)]
    for e, (u, v) in enumerate(zip(edge_u.tolist(), edge_v.tolist())):
        adj[u].append(e)  # forward from u
        adj[v].append(e + n_edges)  # reverse from v
    flat: list[int] = []
    adj_ptr = [0]
    for row in adj:
        flat.extend(row)
        adj_ptr.append(len(flat))

    # Spatial grid covering the four nodes.
    grid_lat0, grid_lon0, grid_deg = 52.3995, -1.5015, 0.001
    grid_n_lat, grid_n_lon = 4, 4
    # Put all edges in every cell (tiny graph).
    grid_edge = np.array([0, 1, 2] * (grid_n_lat * grid_n_lon), dtype=np.int64)
    grid_ptr = np.arange(0, len(grid_edge) + 1, 3, dtype=np.int64)

    return MapGraph(
        {
            "node_lat": node_lat,
            "node_lon": node_lon,
            "edge_ptr": edge_ptr,
            "edge_nodes": edge_nodes,
            "edge_u": edge_u,
            "edge_v": edge_v,
            "edge_len_m": edge_len_m,
            "edge_bearing_deg": edge_bearing_deg,
            "adj_ptr": np.asarray(adj_ptr, dtype=np.int64),
            "adj_edge": np.asarray(flat, dtype=np.int64),
            "seg_ptr": seg_ptr,
            "seg_len_m": seg_len_m,
            "seg_bearing_deg": seg_bearing_deg,
            "grid_ptr": grid_ptr,
            "grid_edge": grid_edge,
            "grid_lat0": grid_lat0,
            "grid_lon0": grid_lon0,
            "grid_deg": grid_deg,
            "grid_n_lat": grid_n_lat,
            "grid_n_lon": grid_n_lon,
            "meta": {
                "built_from_drive_data": False,
                "n_edges": 3,
                "honesty": "SYNTHETIC",
                "note": "Y-junction plumbing graph for UI only",
            },
        }
    )


def run_synthetic_trace(
    *,
    n_particles: int,
    show: int,
    yaw_sigma: float,
    seed: int,
    duration_s: float = 12.0,
    hz: float = 10.0,
) -> dict[str, Any]:
    """Run the real filter on a synthetic Y-graph + synthetic motion.

    Labelled SYNTHETIC end-to-end. Particles come from the filter, not hand-drawn.
    """
    graph = _build_synthetic_y_graph()
    n_steps = int(duration_s * hz)
    dt = 1.0 / hz
    # Drive up the stem, then take the right fork with a mild yaw cue.
    stem_len = float(graph.edge_len_m[0])
    right_len = float(graph.edge_len_m[2])
    speed = (stem_len + 0.7 * right_len) / duration_s
    t = np.arange(n_steps, dtype=np.float64) * dt
    # Truth hugs edge 0 then edge 2.
    truth_lat = np.empty(n_steps)
    truth_lon = np.empty(n_steps)
    dist = 0.0
    for k in range(n_steps):
        dist += speed * dt
        if dist <= stem_len:
            frac = dist / stem_len
            truth_lat[k] = 52.40000 + frac * (52.40100 - 52.40000)
            truth_lon[k] = -1.50000
        else:
            along = min(dist - stem_len, right_len)
            frac = along / right_len
            truth_lat[k] = 52.40100 + frac * (52.40200 - 52.40100)
            truth_lon[k] = -1.50000 + frac * (-1.49920 - -1.50000)

    # Yaw: ~0 on stem, then a right turn pulse near the junction.
    yaw_rate = np.zeros(n_steps, dtype=np.float64)
    turn_i = int(0.45 * n_steps)
    yaw_rate[turn_i : turn_i + 8] = 0.35  # rad/s right

    pf = RoadParticleFilter(
        graph, n_particles=n_particles, yaw_sigma_rad_s=yaw_sigma, seed=seed
    )
    if not pf.seed_from_fix(float(truth_lat[0]), float(truth_lon[0]), 0.0):
        raise RuntimeError("synthetic seed failed")

    rng = np.random.default_rng(seed + 17)
    free_lat, free_lon = float(truth_lat[0]), float(truth_lon[0])
    free_yaw = 0.0
    used_edges: set[int] = set(int(e) for e in pf.edge.tolist())
    steps: list[dict[str, Any]] = []

    for k in range(1, n_steps):
        st = pf.step(float(speed), float(yaw_rate[k]), dt, want_position=True)
        if not st.on_graph:
            break
        resampled = bool(st.ess < DEFAULT_ESS_FRACTION * pf.n)
        free_yaw = free_yaw + float(yaw_rate[k]) * dt
        # Bias free-DR heading a bit so the ghost leaves the road (demo contrast).
        free_lat, free_lon = _enu_step(
            speed, free_yaw + 0.08, dt, free_lat, free_lon
        )
        particles, shown, total = _particle_snapshot(pf, show, rng)
        used_edges.update(int(e) for e in pf.edge.tolist())
        steps.append(
            {
                "t": round(float(t[k]), 3),
                "particles": particles,
                "particles_shown": shown,
                "particles_total": total,
                "estimate": {
                    "lat": round(float(st.lat), 7),
                    "lon": round(float(st.lon), 7),
                    "edge": int(st.edge),
                    "heading": round(_estimate_heading(pf, int(st.edge)), 2),
                },
                "truth": {
                    "lat": round(float(truth_lat[k]), 7),
                    "lon": round(float(truth_lon[k]), 7),
                },
                "free_dr": {
                    "lat": round(free_lat, 7),
                    "lon": round(free_lon, 7),
                },
                "speed_mps": round(float(speed), 3),
                "yaw_rate": round(float(yaw_rate[k]), 5),
                "n_eff": round(float(st.ess), 3),
                "resampled": resampled,
                "edge_posterior": _edge_posterior(pf),
            }
        )

    local_graph = _export_local_graph(graph, truth_lat, truth_lon, used_edges, pad_m=80.0)
    return {
        "meta": {
            "drive": "SYNTHETIC-Y",
            "t0_s": 0.0,
            "duration_s": round(float(steps[-1]["t"]), 3) if steps else 0.0,
            "hz": float(hz),
            "n_particles": int(n_particles),
            "particles_shown_cap": int(show),
            "graph": "synthetic://y_junction",
            "source": "SYNTHETIC plumbing trace — not IO-VNBD, not field evidence",
            "honesty": "SYNTHETIC",
            "built_from_drive_data": False,
            "yaw_sigma_rad_s": float(yaw_sigma),
            "notes": (
                "UI / schema plumbing only. Particles are from RoadParticleFilter "
                "on a hand-built Y-graph with synthetic speed/yaw — never present as real."
            ),
        },
        "graph": local_graph,
        "steps": steps,
    }


def _out_path(trace: dict[str, Any]) -> Path:
    meta = trace["meta"]
    drive = str(meta["drive"]).replace("/", "_").replace("\\", "_").replace(" ", "_")
    t0 = meta["t0_s"]
    t0_tag = f"{t0:.0f}" if float(t0) == int(t0) else f"{t0:.1f}".replace(".", "p")
    return OUT_DIR / f"{drive}_{t0_tag}.json"


def _write_trace(trace: dict[str, Any]) -> Path:
    path = _out_path(trace)
    path.write_text(json.dumps(trace, separators=(",", ":")), encoding="utf-8")
    return path


def _print_real_summary(trace: dict[str, Any], path: Path) -> None:
    meta = trace["meta"]
    mb = path.stat().st_size / (1024 * 1024)
    print(
        f"REAL  drive={meta.get('drive')}  start_idx={meta.get('start_idx')}  "
        f"outcome={meta.get('outcome')}  ratio={meta.get('ratio')}  "
        f"free={meta.get('free_end_error_m')}m  pf={meta.get('pf_end_error_m')}m  "
        f"matched_benchmark={meta.get('matched_benchmark')}  "
        f"steps={len(trace['steps'])}  {mb:.2f} MB  -> {path}",
        flush=True,
    )


def _resolve_benchmark_picks(
    *,
    report_path: Path,
    drive: str | None,
    start_idx: int | None,
    n_help: int,
    n_hurt: int,
) -> list[dict[str, Any]]:
    rows = load_benchmark_junctions(report_path)
    if drive:
        want = drive.lower()
        rows = [
            r
            for r in rows
            if want in str(r["name"]).lower() or want in str(r["name"]).replace(".csv", "").lower()
        ]
    if start_idx is not None:
        exact = [r for r in rows if int(r["start_idx"]) == int(start_idx)]
        if not exact:
            raise RuntimeError(
                f"no junctions outage with start_idx={start_idx} "
                f"in {report_path} (drive={drive!r})"
            )
        return exact
    picks = select_demo_outages(rows, n_help=n_help, n_hurt=n_hurt)
    if not picks:
        raise RuntimeError("no demo-usable junctions outages in frozen report")
    return picks


def _export_benchmark_traces(
    graph: MapGraph,
    rel_graph: str,
    picks: list[dict[str, Any]],
    *,
    n_particles: int,
    show: int,
    yaw_sigma: float,
    seed: int,
) -> list[Path]:
    written: list[Path] = []
    cache: dict[str, dict[str, Any]] = {}
    last_err: Exception | None = None
    for row in picks:
        name = str(row["name"])
        try:
            if name not in cache:
                cache[name] = _load_drive_by_name(name)
            data = cache[name]
            n = min(int(data["n"]), int(data.get("can_n", 0)))
            t = np.asarray(data["t_s"][:n], dtype=np.float64)
            i0 = int(row["start_idx"])
            if i0 < 2 or i0 >= n - 2:
                raise RuntimeError(f"start_idx {i0} out of range for {name} n={n}")
            i1 = _window_end_idx(t, i0, n)
            print(
                f"benchmark  {name}  start_idx={i0}  "
                f"report free={row['free_error_m']:.1f}m pf={row['pf_error_m']:.1f}m  "
                f"particles={n_particles}",
                flush=True,
            )
            trace = run_real_trace(
                graph,
                rel_graph,
                data,
                i0,
                i1,
                n_particles=n_particles,
                show=show,
                yaw_sigma=yaw_sigma,
                seed=seed,
                benchmark=row,
                eval_seed=True,
            )
            path = _write_trace(trace)
            written.append(path)
            _print_real_summary(trace, path)
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            print(f"  skip {name} start_idx={row.get('start_idx')}: {exc}", flush=True)
            continue
    if not written:
        raise RuntimeError(f"all benchmark outages failed ({last_err})")
    return written


def _remove_stale_real_traces(keep: set[str]) -> None:
    if not OUT_DIR.is_dir():
        return
    for old in OUT_DIR.glob("*.json"):
        if old.name.upper().startswith("SYNTHETIC"):
            continue
        if old.name in keep:
            continue
        old.unlink()
        print(f"removed stale {old.name}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--synthetic", action="store_true", help="Force SYNTHETIC plumbing trace")
    ap.add_argument(
        "--mode",
        choices=("benchmark", "max-turn"),
        default="benchmark",
        help="benchmark (default): replay frozen report outages. "
        "max-turn: old hardest-turn picker (not the 2.02x set).",
    )
    ap.add_argument(
        "--from-benchmark",
        action="store_true",
        help="Deprecated alias for --mode benchmark",
    )
    ap.add_argument("--drive", default=None, help="Substring match on CSV name (e.g. S-S1)")
    ap.add_argument("--t0", type=float, default=None, help="Outage start time in file seconds")
    ap.add_argument(
        "--start-idx",
        type=int,
        default=None,
        help="Exact junctions start_idx from mapfilter/report.json",
    )
    ap.add_argument("--particles", type=int, default=DEFAULT_PARTICLES)
    ap.add_argument("--show", type=int, default=DEFAULT_SHOW, help="Particles kept per step")
    ap.add_argument("--yaw-sigma", type=float, default=DEFAULT_YAW_SIGMA)
    ap.add_argument("--graph", default=DEFAULT_GRAPH)
    ap.add_argument("--report", default=str(DEFAULT_REPORT))
    ap.add_argument("--seed", type=int, default=26168)
    ap.add_argument("--n-help", type=int, default=N_HELP_DEFAULT)
    ap.add_argument("--n-hurt", type=int, default=N_HURT_DEFAULT)
    ap.add_argument(
        "--no-synthetic",
        action="store_true",
        help="Do not write the SYNTHETIC plumbing file",
    )
    ap.add_argument(
        "--keep-old",
        action="store_true",
        help="Do not delete previously exported REAL traces",
    )
    args = ap.parse_args()

    write_synthetic = not bool(args.no_synthetic)
    mode = "benchmark" if args.from_benchmark else args.mode

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    if args.synthetic:
        trace = run_synthetic_trace(
            n_particles=min(args.particles, 64),
            show=min(args.show, 48),
            yaw_sigma=args.yaw_sigma,
            seed=args.seed,
        )
        path = _write_trace(trace)
        written.append(path)
        print(f"SYNTHETIC  steps={len(trace['steps'])}  -> {path}")
        print("honesty=SYNTHETIC — do not present as field evidence")
        return 0

    graph_path = Path(args.graph)
    if not graph_path.is_absolute():
        graph_path = _REPO / graph_path
    real_ok = False
    try:
        if not graph_path.exists():
            raise FileNotFoundError(graph_path)
        graph = MapGraph.load(graph_path)
        if graph.meta.get("built_from_drive_data", True):
            print("ABORT: graph is not independent of drive data.", file=sys.stderr)
            return 2
        rel_graph = str(Path(args.graph)).replace("\\", "/")

        if mode == "benchmark":
            report_path = Path(args.report)
            if not report_path.is_absolute():
                report_path = _REPO / report_path
            if not report_path.exists():
                raise FileNotFoundError(report_path)
            picks = _resolve_benchmark_picks(
                report_path=report_path,
                drive=args.drive,
                start_idx=args.start_idx,
                n_help=args.n_help,
                n_hurt=args.n_hurt,
            )
            written.extend(
                _export_benchmark_traces(
                    graph,
                    rel_graph,
                    picks,
                    n_particles=args.particles,
                    show=args.show,
                    yaw_sigma=args.yaw_sigma,
                    seed=args.seed,
                )
            )
            real_ok = True
        else:
            candidates = _pick_all_segments(graph, args.drive, args.t0, limit=12)
            if not candidates:
                raise RuntimeError("no suitable IO-VNBD outage found in graph bbox")
            last_err: Exception | None = None
            trace: dict[str, Any] | None = None
            for data, i0, i1 in candidates:
                print(
                    f"try max-turn  drive={data.get('name')}  "
                    f"t0={float(data['t_s'][i0]):.1f}s  "
                    f"n={i1 - i0} samples  particles={args.particles} show={args.show}",
                    flush=True,
                )
                try:
                    trace = run_real_trace(
                        graph,
                        rel_graph,
                        data,
                        i0,
                        i1,
                        n_particles=args.particles,
                        show=args.show,
                        yaw_sigma=args.yaw_sigma,
                        seed=args.seed,
                        benchmark=None,
                        eval_seed=False,
                    )
                    break
                except Exception as exc:  # noqa: BLE001
                    last_err = exc
                    print(f"  skip: {exc}", flush=True)
                    continue
            if trace is None:
                raise RuntimeError(f"all candidate outages failed ({last_err})")
            path = _write_trace(trace)
            written.append(path)
            _print_real_summary(trace, path)
            real_ok = True
    except Exception as exc:  # noqa: BLE001 — fall back honestly
        print(
            f"real export unavailable ({exc}); writing SYNTHETIC plumbing trace",
            file=sys.stderr,
        )
        write_synthetic = True

    if write_synthetic:
        syn = run_synthetic_trace(
            n_particles=min(args.particles, 64),
            show=min(args.show, 48),
            yaw_sigma=args.yaw_sigma,
            seed=args.seed,
        )
        syn_path = _write_trace(syn)
        if syn_path not in written:
            written.append(syn_path)
        print(f"SYNTHETIC  steps={len(syn['steps'])}  -> {syn_path}")
        print("honesty=SYNTHETIC — do not present as field evidence")

    if real_ok and not args.keep_old:
        _remove_stale_real_traces({p.name for p in written})

    for p in written:
        print(f"wrote {p}")
    return 0 if real_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
