"""F12: the metric the field is missing — branch-decision accuracy.

Everyone reports drift %. The user experiences "did I take the right ramp."
A wrong-ramp trace can still look like a few-percent drift if the ramps
run parallel; branch accuracy is 0.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib.pyplot as plt
import numpy as np

from kinematics import DEG, dead_reckon, drift_pct
from util import save_json, save_plot

NAME = "exp12_branch_metric"


def _path(v: float, headings: np.ndarray, dt: float):
    w = np.diff(headings, prepend=headings[0]) / dt
    # first diff of a step is a spike; use the heading series directly
    x = np.empty_like(headings)
    y = np.empty_like(headings)
    x[0] = 0.0
    y[0] = 0.0
    for i in range(1, headings.size):
        x[i] = x[i - 1] + v * np.cos(headings[i - 1]) * dt
        y[i] = y[i - 1] + v * np.sin(headings[i - 1]) * dt
    return x, y


def run(seed: int = 26168) -> dict:
    v = 12.0
    dt = 0.02
    # Long approach, tight fork: Euclidean drift can pass ISRO's 10% while the ramp is wrong.
    n_a = int(250 / v / dt)
    n_r = int(90 / v / dt)
    fork = 8.0 * DEG
    h0 = np.zeros(n_a)
    h_true = np.concatenate([h0, np.full(n_r, fork)])
    h_wrong = np.concatenate([h0, np.full(n_r, -fork)])
    # A "good-looking" car-style estimate: takes the WRONG ramp because
    # heading was scaled by cos(lean) through the last turn, but Euclidean
    # error at 180 m of ramp is only the fork opening.
    xt, yt = _path(v, h_true, dt)
    xw, yw = _path(v, h_wrong, dt)
    dist = float(np.sum(np.hypot(np.diff(xt), np.diff(yt))))
    err_wrong = float(np.hypot(xw[-1] - xt[-1], yw[-1] - yt[-1]))
    drift_wrong = drift_pct(err_wrong, dist)
    branch_true = 1.0
    branch_wrong = 0.0

    # Sweep fork angle: Euclidean drift of the wrong ramp vs branch accuracy.
    forks = np.linspace(4.0, 40.0, 19)
    drift_s = []
    for f in forks:
        ht = np.concatenate([h0, np.full(n_r, f * DEG)])
        hw = np.concatenate([h0, np.full(n_r, -f * DEG)])
        a, b = _path(v, ht, dt)
        c, d = _path(v, hw, dt)
        dist_f = float(np.sum(np.hypot(np.diff(a), np.diff(b))))
        drift_s.append(drift_pct(float(np.hypot(c[-1] - a[-1], d[-1] - b[-1])), dist_f))

    fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.4))
    ax = axes[0]
    ax.plot(yt, xt, color="#2e7d32", lw=2.2, label="true ramp")
    ax.plot(yw, xw, color="#c45911", lw=2.2, label="wrong ramp (still 'a few % drift')")
    ax.plot(0, 0, "ko")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("east (m)")
    ax.set_ylabel("north (m)")
    ax.set_title(f"wrong ramp  ·  drift {drift_wrong:.1f}%  ·  branch acc 0%")
    ax.legend(loc="upper left")
    ax = axes[1]
    ax.plot(forks, drift_s, color="#1f4e79", lw=2.0, label="wrong-ramp Euclidean drift %")
    ax.axhline(10, color="#888", ls="--", lw=0.8, label="ISRO 10% drift budget")
    ax.set_xlabel("fork half-angle (deg)")
    ax.set_ylabel("drift (%)")
    ax.set_title("F12  ·  drift % can pass while the ramp is wrong")
    ax.legend()
    save_plot(fig, NAME)

    payload = {
        "finding": "F12",
        "name": NAME,
        "wrong_ramp_drift_pct": drift_wrong,
        "wrong_ramp_err_m": err_wrong,
        "distance_m": dist,
        "branch_accuracy_true": branch_true,
        "branch_accuracy_wrong": branch_wrong,
        "fork_half_deg": 8.0,
        "note": "Report branch-decision accuracy. Drift % is not what the rider feels at a ramp.",
        "seed": seed,
    }
    save_json(NAME, payload)
    return payload


if __name__ == "__main__":
    out = run()
    print(
        f"F12  wrong-ramp drift {out['wrong_ramp_drift_pct']:.1f}%  "
        f"branch acc {out['branch_accuracy_wrong']:.0%}  (true {out['branch_accuracy_true']:.0%})"
    )
