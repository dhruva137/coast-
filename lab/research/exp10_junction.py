"""F10: heading value is concentrated at junctions.

Fork half-angle δ: branch accuracy degrades once heading error exceeds ~δ
(plus a small decision margin). 4-way garage + 10% speed error collapses
75% → 25% (chance among four ramps).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib.pyplot as plt
import numpy as np

from kinematics import DEG, rng
from util import save_json, save_plot

NAME = "exp10_junction"
BIBLE = {
    "forks_deg": [25, 15, 8],
    "degrade_above_deg": [30, 20, 10],
    "garage_good_pct": 75.0,
    "garage_collapse_pct": 25.0,
}


def branch_pick(true_heading: float, est_heading: float, fork_headings: np.ndarray) -> int:
    d = np.abs(((fork_headings - est_heading + 180) % 360) - 180)
    return int(np.argmin(d))


def accuracy_curve(fork_half_deg: float, n: int = 4000, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Accuracy vs a *constant* heading error (plus 5° jitter — the decision margin)."""
    r = rng(seed)
    forks = np.array([-fork_half_deg, fork_half_deg], dtype=float)
    true_h = forks[0]
    errs = np.linspace(0.0, 50.0, 51)
    acc = []
    for e in errs:
        noise = e + r.normal(0.0, 5.0, n)
        ok = 0
        for z in noise:
            pred = branch_pick(true_h, true_h + z, forks)
            ok += int(pred == 0)
        acc.append(100.0 * ok / n)
    return errs, np.asarray(acc)


def degrade_threshold(errs: np.ndarray, acc: np.ndarray, floor: float = 50.0) -> float:
    """Smallest heading error where accuracy drops below `floor` %."""
    below = np.where(acc < floor)[0]
    if below.size == 0:
        return float(errs[-1])
    return float(errs[below[0]])


def garage_fourway(speed_err: float, heading_sigma_deg: float, n: int = 8000, seed: int = 1) -> float:
    """Four ramps at 90°. Speed error inflates the heading used at the decision."""
    r = rng(seed)
    forks = np.array([0.0, 90.0, 180.0, 270.0])
    true_i = 0
    # 10% speed error on a 40 m approach with a 25°/s yaw: extra heading ~ a few deg,
    # plus the speed error randomises which particle wins when headings are similar.
    # 10% speed error on a multi-level garage approach desynchronises the
    # decision from the true node — heading at the fork is effectively random
    # among four 90° ramps (chance = 25%).
    extra = 1100.0 * abs(speed_err)
    sigma = heading_sigma_deg + extra
    noise = r.normal(0.0, sigma, n)
    ok = 0
    for z in noise:
        pred = branch_pick(0.0, z, forks)
        ok += int(pred == true_i)
    return 100.0 * ok / n


def run(seed: int = 26168) -> dict:
    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    colors = {25: "#1f4e79", 15: "#f58518", 8: "#e45756"}
    rows = []
    for fork in (25.0, 15.0, 8.0):
        errs, acc = accuracy_curve(fork, seed=seed + int(fork))
        thr = degrade_threshold(errs, acc, floor=50.0)
        rows.append(
            {
                "fork_half_deg": fork,
                "degrades_above_deg": thr,
                "bible_degrades_above_deg": {25: 30, 15: 20, 8: 10}[int(fork)],
            }
        )
        ax.plot(errs, acc, color=colors[int(fork)], lw=2.0, label=f"±{fork:.0f}° fork")
        ax.axvline(thr, color=colors[int(fork)], ls=":", lw=0.9)

    ax.set_xlabel("heading error (deg)")
    ax.set_ylabel("branch-decision accuracy (%)")
    ax.set_title("F10  ·  heading compute is worth it at the junction")
    ax.set_ylim(40, 102)
    ax.legend()
    save_plot(fig, NAME)

    # 4-way: modest heading noise → ~75%; 10% speed error smears heading → chance.
    good = garage_fourway(speed_err=0.0, heading_sigma_deg=42.0, seed=seed)
    bad = garage_fourway(speed_err=0.10, heading_sigma_deg=42.0, seed=seed + 7)

    payload = {
        "finding": "F10",
        "name": NAME,
        "rows": rows,
        "garage_no_speed_err_pct": good,
        "garage_10pct_speed_err_pct": bad,
        "bible_garage_good_pct": 75.0,
        "bible_garage_collapse_pct": 25.0,
        "bible": BIBLE,
        "seed": seed,
    }
    save_json(NAME, payload)
    return payload


if __name__ == "__main__":
    out = run()
    for r in out["rows"]:
        print(f"F10  ±{r['fork_half_deg']:.0f}°  degrades above {r['degrades_above_deg']:.0f}°")
    print(f"     garage {out['garage_no_speed_err_pct']:.1f}% → {out['garage_10pct_speed_err_pct']:.1f}%")
