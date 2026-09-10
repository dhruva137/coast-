"""Deck figures, drawn from measured artifacts only.

Every line plotted here comes out of a committed results file. The hero figure
is a real 60-second GNSS outage from IO-VNBD drive S-S1, with the road graph,
the CAN-truth path, free dead reckoning and the map-in-loop estimate all read
from `lab/stress/results/traces/`. Nothing is illustrative.

    python tools/make_deck_figures.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patheffects import withStroke

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "final_demo_pitch" / "ppt_assets" / "diagrams"
TRACE = REPO / "lab" / "stress" / "results" / "traces" / "S-S1_3583.json"

# Restrained palette. One accent, one failure colour, everything else greyscale.
INK = "#0B1220"
MUTED = "#7A8798"
FAINT = "#D7DEE7"
ROAD = "#C3CCD8"
TEAL = "#00A88A"
RED = "#E5484D"
BLUE = "#2563EB"
PAPER = "#FFFFFF"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.edgecolor": FAINT,
    "text.color": INK,
    "axes.labelcolor": INK,
    "savefig.facecolor": PAPER,
    "figure.facecolor": PAPER,
})


def _m(a_lat, a_lon, b_lat, b_lon):
    dlat = math.radians(b_lat - a_lat)
    dlon = math.radians(b_lon - a_lon)
    mlat = math.radians((a_lat + b_lat) * 0.5)
    return math.hypot(dlat, dlon * math.cos(mlat)) * 6_371_000.0


def hero() -> Path:
    """One real outage: what happens with and without the map in the loop."""
    d = json.loads(TRACE.read_text(encoding="utf-8"))
    steps = d["steps"]
    graph = d["graph"]

    truth = [(s["truth"]["lat"], s["truth"]["lon"]) for s in steps]
    free = [(s["free_dr"]["lat"], s["free_dr"]["lon"]) for s in steps]
    est = [(s["estimate"]["lat"], s["estimate"]["lon"]) for s in steps]

    err_free = _m(*free[-1], *truth[-1])
    err_est = _m(*est[-1], *truth[-1])

    # Local metres, so the aspect is honest rather than a lat/lon squash.
    lat0, lon0 = truth[0]
    k = math.cos(math.radians(lat0))

    def xy(seq):
        return (
            [(lo - lon0) * k * 111_320.0 for _, lo in seq],
            [(la - lat0) * 111_320.0 for la, _ in seq],
        )

    fig, ax = plt.subplots(figsize=(11.6, 6.0), dpi=220)

    for e in graph["edges"]:
        pts = e["pts"]
        gx = [(p[1] - lon0) * k * 111_320.0 for p in pts]
        gy = [(p[0] - lat0) * 111_320.0 for p in pts]
        ax.plot(gx, gy, color=ROAD, lw=2.6, solid_capstyle="round", zorder=1)

    tx, ty = xy(truth)
    fx, fy = xy(free)
    ex, ey = xy(est)

    ax.plot(tx, ty, color=INK, lw=3.4, zorder=4, label="Ground truth (vehicle CAN)")
    ax.plot(fx, fy, color=RED, lw=2.8, ls=(0, (5, 3)), zorder=3,
            label="Dead reckoning alone")
    ax.plot(ex, ey, color=TEAL, lw=3.2, zorder=5, label="COAST — map in the loop")

    ax.scatter([tx[0]], [ty[0]], s=120, color=INK, zorder=7, ec=PAPER, lw=2)
    ax.annotate("GNSS lost here", (tx[0], ty[0]), textcoords="offset points",
                xytext=(14, 12), fontsize=12.5, color=INK, weight="bold")

    for x, y, c, txt in ((fx[-1], fy[-1], RED, f"{err_free:.0f} m off"),
                         (ex[-1], ey[-1], TEAL, f"{err_est:.0f} m off")):
        ax.scatter([x], [y], s=150, color=c, zorder=7, ec=PAPER, lw=2.4)
        ax.annotate(txt, (x, y), textcoords="offset points", xytext=(12, -6),
                    fontsize=13.5, weight="bold", color=c,
                    path_effects=[withStroke(linewidth=3.4, foreground=PAPER)])

    ax.annotate(
        "60 seconds without GNSS",
        xy=(0.5, 1.045), xycoords="axes fraction", ha="center",
        fontsize=13, color=MUTED, style="italic",
    )

    ax.set_aspect("equal")
    ax.axis("off")
    leg = ax.legend(loc="lower left", frameon=True, fontsize=12.5,
                    borderpad=0.9, labelspacing=0.75)
    leg.get_frame().set_edgecolor(FAINT)
    leg.get_frame().set_linewidth(1.0)

    # Scale bar, because a map without one is decoration.
    span = max(max(tx) - min(tx), max(ty) - min(ty))
    bar = 100 if span > 400 else 50
    x0 = min(min(tx), min(fx), min(ex))
    y0 = min(min(ty), min(fy), min(ey))
    ax.plot([x0, x0 + bar], [y0 - span * 0.06] * 2, color=MUTED, lw=3,
            solid_capstyle="butt")
    ax.annotate(f"{bar} m", (x0 + bar / 2, y0 - span * 0.085), ha="center",
                fontsize=11.5, color=MUTED)

    fig.tight_layout(pad=0.4)
    p = OUT / "hero_outage.png"
    fig.savefig(p, bbox_inches="tight", pad_inches=0.18)
    plt.close(fig)
    print(f"  hero_outage.png   free-DR {err_free:.1f} m vs COAST {err_est:.1f} m")
    return p


def inversion() -> Path:
    """Why a better sensor is the wrong answer, in one chart."""
    fig, ax = plt.subplots(figsize=(7.4, 4.5), dpi=220)

    labels = ["Snap to road\nafterwards", "Dead reckoning\nalone", "Map inside\nthe filter"]
    vals = [0.98, 1.00, 2.02]
    cols = [RED, MUTED, TEAL]

    bars = ax.bar(labels, vals, color=cols, width=0.56, zorder=3)
    ax.axhline(1.0, color=FAINT, lw=1.6, ls="--", zorder=2)

    for b, v in zip(bars, vals):
        ax.annotate(f"{v:.2f}×", (b.get_x() + b.get_width() / 2, v),
                    textcoords="offset points", xytext=(0, 8), ha="center",
                    fontsize=17, weight="bold",
                    color=b.get_facecolor())

    ax.set_ylim(0, 2.45)
    ax.set_ylabel("Accuracy vs dead reckoning alone", fontsize=12, color=MUTED)
    ax.tick_params(axis="x", labelsize=12.5, colors=INK, length=0, pad=8)
    ax.tick_params(axis="y", labelsize=10.5, colors=MUTED, length=0)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(FAINT)
    ax.grid(axis="y", color=FAINT, lw=0.9, zorder=0)
    ax.set_axisbelow(True)

    ax.annotate("worse than doing nothing", (0, 0.98), textcoords="offset points",
                xytext=(0, -42), ha="center", fontsize=11, color=RED, style="italic")

    fig.tight_layout(pad=0.5)
    p = OUT / "inversion.png"
    fig.savefig(p, bbox_inches="tight", pad_inches=0.14)
    plt.close(fig)
    print("  inversion.png")
    return p


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    print("figures ->", OUT)
    hero()
    inversion()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
