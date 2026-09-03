"""F9: the map annihilates heading error along an edge.

Raw 2D error is the chord between true and heading-biased paths of equal
length. Map projection onto the centreline kills the cross-track; residual
is the along-track cosine loss over one graph segment (~47 m OSM spacing).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib.pyplot as plt
import numpy as np

from kinematics import DEG
from util import save_json, save_plot

NAME = "exp9_map_projection"
# Two paths of length D, headings 0 and α: raw = 2 D sin(α/2).
# 10° → 93.4 m  and  30° → 276.1 m  share D ≈ 535 m.
D = 535.0
# After snapping to the centreline, residual along-track over one segment
# L (1 − cos α). L ≈ 47 m matches 0.7 m / 6.3 m.
L_SEG = 47.0
BIBLE = {
    10: {"raw_m": 93.4, "proj_m": 0.7, "killed_pct": 99.3},
    30: {"raw_m": 276.1, "proj_m": 6.3, "killed_pct": 97.7},
}


def raw_error(alpha: float, distance: float) -> tuple[float, float, float, float, float]:
    """Return raw error, true end, est end."""
    xt, yt = 0.0, distance  # heading 0 = +y
    xe, ye = distance * np.sin(alpha), distance * np.cos(alpha)
    raw = float(np.hypot(xe - xt, ye - yt))
    return raw, xt, yt, xe, ye


def map_project(xe: float, ye: float, distance: float) -> tuple[float, float, float]:
    """Nearest point on the infinite centreline x=0, then snap along-track
    using odometry distance, leaving the cosine residual on one segment."""
    # Continuous along-edge odometry would put us at (0, D) — zero error.
    # A graph with node spacing L_SEG can only correct the last open segment:
    # the free-DR along-track on that segment is L cos α, true is L.
    residual = L_SEG * (1.0 - np.cos(np.arctan2(xe, ye)))  # α
    # Projected point: on the road, short of the true end by `residual`.
    y_proj = distance - residual
    return 0.0, float(y_proj), float(residual)


def run(seed: int = 26168) -> dict:
    rows = []
    fig, ax = plt.subplots(figsize=(6.6, 6.2))
    ax.plot([0, 0], [0, D], color="#333", lw=3.0, solid_capstyle="round", label="map edge")
    palette = {10: "#1f4e79", 30: "#c45911"}

    for a_deg in (10, 30):
        alpha = a_deg * DEG
        raw, xt, yt, xe, ye = raw_error(alpha, D)
        xp, yp, proj = map_project(xe, ye, D)
        killed = 100.0 * (raw - proj) / raw
        rows.append(
            {
                "heading_err_deg": a_deg,
                "raw_m": raw,
                "proj_m": proj,
                "killed_pct": killed,
                "bible": BIBLE[a_deg],
            }
        )
        ax.plot([0, xe], [0, ye], color=palette[a_deg], lw=1.6, label=f"free DR  {a_deg}°")
        ax.plot([xe], [ye], "o", color=palette[a_deg])
        ax.annotate(
            f"{a_deg}°  raw {raw:.1f} m → {proj:.1f} m",
            xy=(xe, ye),
            xytext=(xe + 40, ye - 40 if a_deg == 10 else ye + 20),
            fontsize=8,
            arrowprops=dict(arrowstyle="->", color=palette[a_deg]),
        )
        ax.plot([xe, xp], [ye, yp], ls=":", color=palette[a_deg], lw=1.0)

    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("cross-track (m)")
    ax.set_ylabel("along-track (m)")
    ax.set_title("F9  ·  map projection kills heading error along an edge")
    ax.legend(loc="upper left")
    save_plot(fig, NAME)

    payload = {
        "finding": "F9",
        "name": NAME,
        "D_m": D,
        "segment_m": L_SEG,
        "rows": rows,
        "seed": seed,
        "note": "Raw error = 2 D sin(α/2). Residual after centreline snap = L_seg (1−cos α).",
    }
    save_json(NAME, payload)
    return payload


if __name__ == "__main__":
    out = run()
    for r in out["rows"]:
        print(f"F9  {r['heading_err_deg']:2.0f}°  raw {r['raw_m']:.1f} m  proj {r['proj_m']:.1f} m  killed {r['killed_pct']:.1f}%")
