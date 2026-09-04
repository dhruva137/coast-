"""One-page SIH26168 proposal figure: trajectory + F8 error-budget table."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

EVAL_DIR = Path(__file__).resolve().parent
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from iovnbd_plots import (  # noqa: E402
    FIGURES_DIR,
    F8_ROWS,
    HZ,
    WINDOW_SAMPLES,
    WINDOW_SECONDS,
    infer,
    load_trace,
    resolve_csv,
)

_GNSS = "#1f4e79"
_DR = "#c45911"
_OUT = "#f4b183"


def build_onepager(dest: Path | None = None) -> Path:
    figures = FIGURES_DIR
    figures.mkdir(parents=True, exist_ok=True)
    out = Path(dest) if dest is not None else figures / "proposal_onepager.png"

    # Prefer the robust runner (tries real CSV, falls back to fixture).
    from iovnbd_plots import run as run_iovnbd_plots

    pack = run_iovnbd_plots(figures)
    path = Path(pack["csv_path"])
    source = str(pack["source"])
    result = pack

    fig, (ax_traj, ax_tab) = plt.subplots(
        1,
        2,
        figsize=(12.6, 6.15),
        dpi=170,
        gridspec_kw={"width_ratios": [1.12, 1.0]},
    )
    fig.suptitle(
        "SIH26168 preliminary inference (10 Hz windows)",
        fontsize=15,
        fontweight="semibold",
        y=0.98,
    )
    fig.text(
        0.5,
        0.915,
        f"{source}  ·  window = {WINDOW_SAMPLES} samples @ {HZ} Hz ({WINDOW_SECONDS:.0f} s)  ·  "
        f"not AVNet 200-sample / 200 Hz",
        ha="center",
        fontsize=8,
        color="#4a4a4a",
    )

    outage = result["outage"]
    e_aid = result["e_gt"].copy()
    n_aid = result["n_gt"].copy()
    e_aid[outage] = np.nan
    n_aid[outage] = np.nan
    ax_traj.plot(e_aid, n_aid, color=_GNSS, lw=2.1, label="GNSS")
    if outage.any():
        ax_traj.plot(
            result["e_gt"][outage],
            result["n_gt"][outage],
            color=_GNSS,
            lw=1.15,
            ls="--",
            label="GT during outage",
        )
    e_coast = result["e_dr"].copy()
    n_coast = result["n_dr"].copy()
    e_coast[~outage] = np.nan
    n_coast[~outage] = np.nan
    ax_traj.plot(e_coast, n_coast, color=_DR, lw=1.85, label="DR (windowed v + gyro)")
    if outage.any():
        i0 = int(np.flatnonzero(outage)[0])
        ax_traj.scatter([result["e_gt"][i0]], [result["n_gt"][i0]], c="#7b2d00", s=26, zorder=5)
        ax_traj.annotate(
            "GNSS outage",
            xy=(result["e_gt"][i0], result["n_gt"][i0]),
            xytext=(12, -18),
            textcoords="offset points",
            fontsize=7.5,
            color="#7b2d00",
        )
    ax_traj.set_aspect("equal", adjustable="box")
    ax_traj.set_xlabel("East (m)", fontsize=9)
    ax_traj.set_ylabel("North (m)", fontsize=9)
    ax_traj.set_title("Position: GNSS vs dead reckoning", fontsize=11, pad=8)
    ax_traj.grid(True, color="#d9d9d9", lw=0.6)
    ax_traj.spines["top"].set_visible(False)
    ax_traj.spines["right"].set_visible(False)
    ax_traj.legend(frameon=False, fontsize=8, loc="best")
    ax_traj.tick_params(labelsize=8)

    ax_tab.set_axis_off()
    ax_tab.set_title("Error budget [F8] — heading, not speed", fontsize=11, pad=8)

    cells = [["Error source", "F8 pos", "F8 drift", "Measured pos", "Measured drift"]]
    for row, meas in zip(F8_ROWS, result["f8_measured"]):
        cells.append(
            [
                row[0],
                f"{row[1]:.1f} m",
                f"{row[2]:.2f}%",
                f"{meas[0]:.1f} m",
                f"{meas[1]:.2f}%",
            ]
        )
    cells.append(
        [
            "This outage (windowed DR)",
            "—",
            "—",
            f"{result['outage_err_m']:.1f} m",
            f"{result['measured_drift_pct']:.2f}%",
        ]
    )

    table = ax_tab.table(
        cellText=cells,
        loc="upper center",
        cellLoc="center",
        colWidths=[0.44, 0.13, 0.13, 0.15, 0.15],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(7.4)
    table.scale(1.0, 1.72)

    bold = FontProperties(weight="semibold", size=7.4)
    header_c = "#1f4e79"
    gyro_c = "#f8e0d0"
    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor("#c8c8c8")
        cell.set_linewidth(0.4)
        if r == 0:
            cell.set_facecolor(header_c)
            cell.set_text_props(color="white", fontproperties=bold)
        elif r == 4:
            cell.set_facecolor(gyro_c)
        elif r == 5:
            cell.set_facecolor("#eef3f7")
        else:
            cell.set_facecolor("white")
        if c == 0 and r > 0:
            cell.get_text().set_ha("left")
            cell.PAD = 0.04

    ax_tab.text(
        0.5,
        0.18,
        "Equal-effort: 1% speed → 3.0 m;  1% heading (3.6°) → 18.9 m.\n"
        "Heading is 6.3× more damaging.  Outage ≈ "
        f"{result['outage_dist_m']:.0f} m.  ISRO: <10% / <100 m per km.",
        transform=ax_tab.transAxes,
        ha="center",
        va="top",
        fontsize=8,
        color="#333333",
    )

    fig.subplots_adjust(left=0.055, right=0.98, top=0.86, bottom=0.08, wspace=0.12)
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    return out


def main() -> Path:
    dest = build_onepager()
    print(f"wrote {dest}")
    return dest


if __name__ == "__main__":
    main()
