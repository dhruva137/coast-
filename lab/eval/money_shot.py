"""Projector money visual: free DR leaves the road; COAST stays on it.

Writes:
  final_demo_pitch/ppt_assets/diagrams/money_shot.png
  final_demo_pitch/ppt_assets/diagrams/money_shot.gif  (if pillow available)
  final_demo_pitch/ppt_assets/diagrams/money_shot.mp4 (if imageio/ffmpeg available)

Uses the same real IO-VNBD + OSM graph path as ``lab.eval.demo_plots`` — not
an illustration. Headline aggregate 2.02× stays in mapfilter/summary.md; this
figure is one measured outage window for the five-second test.

Run:
    python -m lab.eval.money_shot
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
for _p in (_REPO / "lab" / "stress", _REPO / "lab" / "nav", str(_HERE)):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from demo_plots import (  # noqa: E402
    GRAPH,
    _enu,
    _pick_drive_and_segment,
)
from gyro_preprocess import lowpass_causal  # noqa: E402
from mapfilter import RoadParticleFilter  # noqa: E402
from mapmatch import MapGraph  # noqa: E402

OUT_DIR = _REPO / "final_demo_pitch" / "ppt_assets" / "diagrams"

# Greyscale-safe: colour + dash + weight. Truth solid pale, free dotted red,
# COAST solid teal (heavier).
C_TRUTH = "#D0D4DA"
C_FREE = "#E63946"
C_COAST = "#00E0A4"
C_ROAD = "#4A5564"
C_BG = "#0B0E12"
C_LABEL = "#F2F4F7"


def _trajectories(graph: MapGraph):
    d, i0, i1 = _pick_drive_and_segment(graph)
    if d is None:
        raise RuntimeError("no suitable IO-VNBD segment found for money shot")
    n = int(min(d["n"], d["can_n"]))
    t = np.asarray(d["t_s"][:n], float)
    cla = np.asarray(d["can_lat"][:n], float)
    clo = np.asarray(d["can_lon"][:n], float)
    v = np.asarray(d["speed_mps"][:n], float)
    gz = -lowpass_causal(np.asarray(d["gyro_pitch_raw"][:n], float), cutoff_hz=0.5)
    lat0, lon0 = float(cla[i0]), float(clo[i0])

    te, tn = _enu(cla[i0:i1], clo[i0:i1], lat0, lon0)

    seed = np.array([te[10] - te[0], tn[10] - tn[0]])
    yaw0 = math.atan2(seed[0], seed[1])
    dt = np.diff(t[i0:i1], prepend=t[i0])
    yaw = yaw0 + np.cumsum(gz[i0:i1] * dt)
    fe = np.cumsum(v[i0:i1] * np.sin(yaw) * dt)
    fn = np.cumsum(v[i0:i1] * np.cos(yaw) * dt)

    pf = RoadParticleFilter(graph, n_particles=600, yaw_sigma_rad_s=0.30)
    head0 = math.degrees(yaw0) % 360.0
    ce, cn = [], []
    if pf.seed_from_fix(lat0, lon0, head0):
        for k in range(i0, i1):
            st = pf.step(float(v[k]), float(gz[k]), float(t[k] - t[k - 1]))
            if not st.on_graph:
                break
            e, nn = _enu(np.array([st.lat]), np.array([st.lon]), lat0, lon0)
            ce.append(float(e[0]))
            cn.append(float(nn[0]))
    ce, cn = np.asarray(ce, float), np.asarray(cn, float)

    dist = float(
        np.nansum(
            np.clip(d["can_speed_mps"][i0:i1], 0, None) * np.clip(dt, 0, 0.5)
        )
    )
    return {
        "drive": d["name"],
        "distance_m": dist,
        "lat0": lat0,
        "lon0": lon0,
        "cla": cla[i0:i1],
        "clo": clo[i0:i1],
        "te": te,
        "tn": tn,
        "fe": fe,
        "fn": fn,
        "ce": ce,
        "cn": cn,
    }


def _draw_frame(ax, graph: MapGraph, traj: dict, frac: float = 1.0) -> None:
    """Draw roads + up to ``frac`` of each trajectory. No axes/title/grid."""
    ax.set_facecolor(C_BG)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)

    lat0, lon0 = traj["lat0"], traj["lon0"]
    cx = float(np.median(traj["cla"]))
    cy = float(np.median(traj["clo"]))
    for e in graph.nearby_edges(cx, cy, 900.0):
        a, b = int(graph.edge_ptr[e]), int(graph.edge_ptr[e + 1])
        idx = graph.edge_nodes[a:b]
        ee, en = _enu(graph.node_lat[idx], graph.node_lon[idx], lat0, lon0)
        ax.plot(ee, en, color=C_ROAD, lw=1.4, alpha=0.75, zorder=1, solid_capstyle="round")

    def take(x, y):
        n = max(2, int(len(x) * frac))
        return x[:n], y[:n]

    te, tn = take(traj["te"], traj["tn"])
    fe, fn = take(traj["fe"], traj["fn"])
    ax.plot(
        te, tn, color=C_TRUTH, lw=5.0, ls="-", solid_capstyle="round",
        zorder=4, label="Truth",
    )
    ax.plot(
        fe, fn, color=C_FREE, lw=4.5, ls=(0, (1.2, 1.6)), solid_capstyle="round",
        zorder=3, label="Free DR",
    )
    if traj["ce"].size:
        ce, cn = take(traj["ce"], traj["cn"])
        ax.plot(
            ce, cn, color=C_COAST, lw=5.5, ls="-", solid_capstyle="round",
            zorder=5, label="COAST",
        )

    ax.scatter([traj["te"][0]], [traj["tn"][0]], c="white", s=120, zorder=6, edgecolors="#222", linewidths=1.2)
    ax.set_aspect("equal", adjustable="datalim")

    # Two-word labels, ≥28 pt, placed near path ends (projector-legible).
    if frac >= 0.98:
        ax.annotate(
            "Truth",
            xy=(te[-1], tn[-1]),
            xytext=(12, 18),
            textcoords="offset points",
            color=C_TRUTH,
            fontsize=28,
            fontweight="bold",
            zorder=7,
        )
        ax.annotate(
            "Free DR",
            xy=(fe[-1], fn[-1]),
            xytext=(12, -8),
            textcoords="offset points",
            color=C_FREE,
            fontsize=28,
            fontweight="bold",
            zorder=7,
        )
        if traj["ce"].size:
            ax.annotate(
                "COAST",
                xy=(ce[-1], cn[-1]),
                xytext=(12, 18),
                textcoords="offset points",
                color=C_COAST,
                fontsize=28,
                fontweight="bold",
                zorder=7,
            )


def write_money_shot(out_dir: Path | None = None) -> dict:
    out_dir = Path(out_dir) if out_dir is not None else OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    graph = MapGraph.load(GRAPH)
    traj = _trajectories(graph)

    fig, ax = plt.subplots(figsize=(10.5, 10.5), dpi=160)
    fig.patch.set_facecolor(C_BG)
    _draw_frame(ax, graph, traj, frac=1.0)
    fig.tight_layout(pad=0.4)
    png = out_dir / "money_shot.png"
    fig.savefig(png, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)

    meta = {
        "drive": traj["drive"],
        "distance_m": traj["distance_m"],
        "png": str(png),
        "gif": None,
        "mp4": None,
        "note": (
            "Single measured outage window for the five-second visual. "
            "Aggregate median position-error improvement remains 2.02× from "
            "lab/stress/results/mapfilter/summary.md — do not read a ratio off this plot."
        ),
    }

    # Animated progressive reveal (optional).
    frames: list[np.ndarray] = []
    fracs = np.linspace(0.08, 1.0, 36)
    for frac in fracs:
        fig, ax = plt.subplots(figsize=(8.0, 8.0), dpi=100)
        fig.patch.set_facecolor(C_BG)
        _draw_frame(ax, graph, traj, frac=float(frac))
        fig.tight_layout(pad=0.2)
        fig.canvas.draw()
        buf = np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy()
        frames.append(buf)
        plt.close(fig)

    try:
        from PIL import Image  # noqa: WPS433

        gif = out_dir / "money_shot.gif"
        imgs = [Image.fromarray(f) for f in frames]
        imgs[0].save(
            gif,
            save_all=True,
            append_images=imgs[1:],
            duration=90,
            loop=0,
            optimize=True,
        )
        meta["gif"] = str(gif)
    except Exception as exc:  # noqa: BLE001 — optional asset
        meta["gif_error"] = str(exc)

    try:
        import imageio.v2 as imageio  # noqa: WPS433

        mp4 = out_dir / "money_shot.mp4"
        imageio.mimwrite(mp4, frames, fps=12, quality=7)
        meta["mp4"] = str(mp4)
    except Exception as exc:  # noqa: BLE001 — optional asset
        meta["mp4_error"] = str(exc)

    (out_dir / "money_shot.json").write_text(
        __import__("json").dumps(
            {k: v for k, v in meta.items() if k != "note"} | {"note": meta["note"]},
            indent=2,
        ),
        encoding="utf-8",
    )
    return meta


def main() -> int:
    print("building money shot from real IO-VNBD + OSM graph...")
    meta = write_money_shot()
    for k, v in meta.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
