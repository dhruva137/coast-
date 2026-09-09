"""The screening plots, and the demo's money shot: COAST vs free dead reckoning.

The problem statement requires, for the proposal, "the results of the position
plot inferenced from the subset of IO-VNBD". This is that, and it doubles as the
argument the demo makes out loud: *free inertial dead reckoning drifts off the
road; the map-constrained engine holds it; we beat the naive baseline by ~2x on
real data, and the ISRO bar is in reach.*

Everything here is real:
  * real IO-VNBD smartphone IMU,
  * scored against the paired vehicle CAN GPS (true 10 Hz),
  * a real OpenStreetMap road graph the estimator never saw the answer in.

Produces, under lab/eval/results/demo/:
  1. trajectory_overlay.png  - one 60 s outage: truth vs free DR vs COAST, on the
     real road network. This is the "free DR flies off the map, COAST stays on
     the road" picture.
  2. drift_comparison.png    - aggregate drift %: free DR vs COAST vs the ISRO
     10 % bar, over every scored segment.

Run:
    python lab/eval/demo_plots.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
for _p in (_REPO / "lab" / "stress", _REPO / "lab" / "nav"):
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
GRAPH = _REPO / "maps" / "graphs" / "iovnbd_midlands.graph.npz"
OUT = _HERE / "results" / "demo"

# COAST palette, so the plots match the app.
C_TRUTH = "#2ec4b6"
C_FREE = "#e63946"
C_COAST = "#ff9f1c"
C_ROAD = "#3a4658"
C_BAR_FREE = "#e63946"
C_BAR_COAST = "#ff9f1c"
C_BAR_BAR = "#2ec4b6"


def _enu(lat, lon, lat0, lon0):
    e = np.deg2rad(lon - lon0) * EARTH_R_M * math.cos(math.radians(lat0))
    n = np.deg2rad(lat - lat0) * EARTH_R_M
    return e, n


def _pick_drive_and_segment(graph: MapGraph):
    """Find a drive in the graph bbox with a clean, turning 60 s outage."""
    m = graph.meta
    for p in find_smartphone_csvs():
        try:
            d = attach_vehicle_truth(load_smartphone_csv(p))
        except (OSError, ValueError):
            continue
        if d.get("truth_source") != "can_10hz":
            continue
        lat = float(np.nanmedian(d["lat"]))
        lon = float(np.nanmedian(d["lon"]))
        if not (
            m["bbox_lat_min"] <= lat <= m["bbox_lat_max"]
            and m["bbox_lon_min"] <= lon <= m["bbox_lon_max"]
        ):
            continue
        n = min(int(d["n"]), int(d.get("can_n", 0)))
        if n < 8000:
            continue
        t = np.asarray(d["t_s"][:n], float)
        cv = np.asarray(d["can_speed_mps"][:n], float)
        cla = np.asarray(d["can_lat"][:n], float)
        clo = np.asarray(d["can_lon"][:n], float)
        # Scan for a 60 s window at road speed that actually turns, so the
        # picture shows heading mattering rather than a straight line anyone
        # could dead-reckon.
        for i0 in np.linspace(int(0.1 * n), int(0.8 * n), 30).astype(int):
            i1 = int(np.searchsorted(t, t[i0] + DENY_S))
            if i1 >= n or float(np.nanmean(cv[i0:i1])) < 9.0:
                continue
            e, nn = _enu(cla[i0:i1], clo[i0:i1], cla[i0], clo[i0])
            head = np.arctan2(np.gradient(e), np.gradient(nn))
            if float(np.ptp(np.unwrap(head))) < 0.8:  # want >~45 deg of turning
                continue
            return d, int(i0), int(i1)
    return None, None, None


def trajectory_overlay(graph: MapGraph) -> dict | None:
    d, i0, i1 = _pick_drive_and_segment(graph)
    if d is None:
        return None
    n = int(min(d["n"], d["can_n"]))
    t = np.asarray(d["t_s"][:n], float)
    cla = np.asarray(d["can_lat"][:n], float)
    clo = np.asarray(d["can_lon"][:n], float)
    v = np.asarray(d["speed_mps"][:n], float)
    gz = -lowpass_causal(np.asarray(d["gyro_pitch_raw"][:n], float), cutoff_hz=0.5)
    lat0, lon0 = float(cla[i0]), float(clo[i0])

    # Ground truth (CAN).
    te, tn = _enu(cla[i0:i1], clo[i0:i1], lat0, lon0)

    # Free dead reckoning: seed heading from GNSS course, integrate gyro + speed.
    seed = np.array([te[10] - te[0], tn[10] - tn[0]])
    yaw0 = math.atan2(seed[0], seed[1])
    dt = np.diff(t[i0:i1], prepend=t[i0])
    yaw = yaw0 + np.cumsum(gz[i0:i1] * dt)
    fe = np.cumsum(v[i0:i1] * np.sin(yaw) * dt)
    fn = np.cumsum(v[i0:i1] * np.cos(yaw) * dt)

    # COAST: road-constrained particle filter.
    pf = RoadParticleFilter(graph, n_particles=600, yaw_sigma_rad_s=0.30)
    head0 = math.degrees(yaw0) % 360.0
    ce, cn = [], []
    if pf.seed_from_fix(lat0, lon0, head0):
        for k in range(i0, i1):
            st = pf.step(float(v[k]), float(gz[k]), float(t[k] - t[k - 1]))
            if not st.on_graph:
                break
            e, nnn = _enu(np.array([st.lat]), np.array([st.lon]), lat0, lon0)
            ce.append(float(e[0]))
            cn.append(float(nnn[0]))
    ce, cn = np.asarray(ce), np.asarray(cn)

    # Nearby road edges for context.
    fig, ax = plt.subplots(figsize=(8.5, 8.5), dpi=140)
    fig.patch.set_facecolor("#0f1318")
    ax.set_facecolor("#0f1318")
    cx = float(np.median(cla[i0:i1]))
    cy = float(np.median(clo[i0:i1]))
    drawn = 0
    for e in graph.nearby_edges(cx, cy, 900.0):
        a, b = int(graph.edge_ptr[e]), int(graph.edge_ptr[e + 1])
        idx = graph.edge_nodes[a:b]
        ee, en = _enu(graph.node_lat[idx], graph.node_lon[idx], lat0, lon0)
        ax.plot(ee, en, color=C_ROAD, lw=1.0, alpha=0.6, zorder=1)
        drawn += 1
    ax.plot(te, tn, color=C_TRUTH, lw=3.2, label="True path (car GPS)", zorder=4)
    ax.plot(fe, fn, color=C_FREE, lw=2.2, ls="--",
            label="Free dead reckoning (naive)", zorder=3)
    if ce.size:
        ax.plot(ce, cn, color=C_COAST, lw=2.6,
                label="COAST (map-constrained)", zorder=5)
    ax.scatter([te[0]], [tn[0]], c="white", s=90, zorder=6, label="GNSS lost here")

    free_err = float(math.hypot(fe[-1] - te[-1], fn[-1] - tn[-1]))
    coast_err = float(math.hypot(ce[-1] - te[-1], cn[-1] - tn[-1])) if ce.size else float("nan")
    dist = float(np.nansum(np.clip(d["can_speed_mps"][i0:i1], 0, None) * np.clip(dt, 0, 0.5)))

    ax.set_title(
        f"60 s GNSS outage on {d['name']}  ({dist:.0f} m travelled)\n"
        f"free DR ends {free_err:.0f} m off  |  COAST ends {coast_err:.0f} m off",
        color="white", fontsize=13,
    )
    ax.set_xlabel("East (m)", color="#8a94a6")
    ax.set_ylabel("North (m)", color="#8a94a6")
    ax.tick_params(colors="#8a94a6")
    for s in ax.spines.values():
        s.set_color("#2a3340")
    ax.set_aspect("equal", adjustable="datalim")
    leg = ax.legend(loc="best", framealpha=0.85, facecolor="#161b22", edgecolor="#2a3340")
    for txt in leg.get_texts():
        txt.set_color("#d7dde5")
    OUT.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(OUT / "trajectory_overlay.png", facecolor=fig.get_facecolor())
    plt.close(fig)
    return {
        "drive": d["name"], "distance_m": dist,
        "free_error_m": free_err, "coast_error_m": coast_err,
        "free_drift_pct": 100.0 * free_err / max(dist, 1.0),
        "coast_drift_pct": 100.0 * coast_err / max(dist, 1.0),
    }


def drift_comparison() -> dict | None:
    rep = _REPO / "lab" / "stress" / "results" / "mapfilter" / "report.json"
    if not rep.is_file():
        return None
    data = json.loads(rep.read_text(encoding="utf-8"))
    rows = [r for f in data["files"] for r in f["junctions"]]
    if not rows:
        return None
    free = np.array([r["free_drift_pct"] for r in rows])
    coast = np.array([r["pf_drift_pct"] for r in rows])

    fig, ax = plt.subplots(figsize=(8.5, 5.0), dpi=140)
    fig.patch.set_facecolor("#0f1318")
    ax.set_facecolor("#0f1318")
    labels = ["Free\ndead reckoning", "COAST\n(map-constrained)"]
    meds = [float(np.median(free)), float(np.median(coast))]
    bars = ax.bar(labels, meds, color=[C_BAR_FREE, C_BAR_COAST], width=0.55, zorder=3)
    ax.axhline(10.0, color=C_BAR_BAR, ls="--", lw=2.0, zorder=2,
               label="ISRO target: <10% drift")
    for b, m in zip(bars, meds):
        ax.text(b.get_x() + b.get_width() / 2, m + 1.5, f"{m:.0f}%",
                ha="center", color="white", fontsize=14, fontweight="bold")
    ax.set_ylabel("Median drift over a 60 s outage (%)", color="#8a94a6")
    ax.set_title(
        f"Real IO-VNBD, {len(rows)} outages, scored against car CAN GPS\n"
        f"COAST cuts drift {np.median(free) / max(np.median(coast), 1e-9):.1f}x  "
        "- the gap to the ISRO bar is the remaining work",
        color="white", fontsize=12,
    )
    ax.tick_params(colors="#8a94a6")
    for s in ax.spines.values():
        s.set_color("#2a3340")
    leg = ax.legend(framealpha=0.85, facecolor="#161b22", edgecolor="#2a3340")
    for txt in leg.get_texts():
        txt.set_color("#d7dde5")
    OUT.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(OUT / "drift_comparison.png", facecolor=fig.get_facecolor())
    plt.close(fig)
    return {
        "n": len(rows),
        "free_median_drift_pct": float(np.median(free)),
        "coast_median_drift_pct": float(np.median(coast)),
        "improvement_x": float(np.median(free) / max(np.median(coast), 1e-9)),
    }


def main() -> int:
    graph = MapGraph.load(GRAPH)
    print("building trajectory overlay...")
    traj = trajectory_overlay(graph)
    print("  ", traj)
    print("building drift comparison...")
    drift = drift_comparison()
    print("  ", drift)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "demo_plots.json").write_text(
        json.dumps({"trajectory": traj, "drift": drift}, indent=2), encoding="utf-8"
    )
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
