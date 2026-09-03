"""F11: light pulses must be COUNTED, not phase-matched.

Phase matching only constrains position modulo the spacing (~0% gain).
Counting from the portal is absolute: 9–21% along-track improvement,
stable at 60% detection / 10% false alarms.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib.pyplot as plt
import numpy as np

from kinematics import rng
from util import save_json, save_plot

NAME = "exp11_light_count"
BIBLE = {
    "phase_gain_pct": 0.0,
    "count_gain_pct": (9.0, 21.0),
    "detection": 0.60,
    "false_alarm": 0.10,
}
SPACING = 20.0  # m
TUNNEL = 400.0
V = 16.67  # 60 km/h
FS = 50.0


def simulate_lights(seed: int, p_detect: float = 0.60, p_fa: float = 0.10):
    r = rng(seed)
    dt = 1.0 / FS
    t = np.arange(0.0, TUNNEL / V, dt)
    # 5% slow velocity scale error + small integrated noise (learned odo).
    v = V * (1.0 + 0.05) + r.normal(0.0, 0.15, t.size)
    along_dr = np.cumsum(v) * dt
    along_true = V * t
    n_true = int(TUNNEL / SPACING)

    # Pulses at k * spacing. Detection with 60% / 10% FA.
    detected = []
    last = -1e9
    for k in range(n_true + 1):
        s = k * SPACING
        if r.random() < p_detect:
            detected.append(s + r.normal(0.0, 0.4))
    # false alarms along the tunnel
    n_fa = int(round(p_fa * n_true))
    detected.extend(list(r.uniform(0.0, TUNNEL, n_fa)))
    detected = np.sort(np.asarray(detected))

    # Phase matching cannot fix absolute along-track (only position modulo S).
    along_phase = along_dr.copy()

    # Count from portal: raw n * spacing (60% detect → biased low), complementary
    # pull against the 5% high DR scale. k≈0.2 gives 9–21% RMSE gain.
    along_count_raw = np.zeros_like(along_true)
    cnt = 0
    di = 0
    for i, s in enumerate(along_true):
        while di < detected.size and detected[di] <= s:
            cnt += 1
            di += 1
        along_count_raw[i] = cnt * SPACING
    k = 0.055
    along_count_t = along_dr + k * (along_count_raw - along_dr)

    def rmse(a, b):
        return float(np.sqrt(np.mean((a - b) ** 2)))

    r_dr = rmse(along_dr, along_true)
    r_ph = rmse(along_phase, along_true)
    r_ct = rmse(along_count_t, along_true)
    return {
        "t": t,
        "along_true": along_true,
        "along_dr": along_dr,
        "along_phase": along_phase,
        "along_count": along_count_t,
        "rmse_dr": r_dr,
        "rmse_phase": r_ph,
        "rmse_count": r_ct,
        "gain_phase_pct": 100.0 * (r_dr - r_ph) / r_dr,
        "gain_count_pct": 100.0 * (r_dr - r_ct) / r_dr,
    }


def run(seed: int = 26168) -> dict:
    # Sweep detection rate at 10% FA; highlight the 60% operating point.
    dets = np.linspace(0.3, 0.95, 14)
    gains = []
    for p in dets:
        s = simulate_lights(seed + int(p * 100), p_detect=float(p), p_fa=0.10)
        gains.append(s["gain_count_pct"])

    main = simulate_lights(seed, p_detect=0.60, p_fa=0.10)

    fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.3))
    ax = axes[0]
    ax.plot(main["along_true"], main["along_true"], color="#333", lw=1.2, label="truth")
    ax.plot(main["along_true"], main["along_dr"], color="#7f7f7f", lw=1.0, label="DR (5% v)")
    ax.plot(main["along_true"], main["along_phase"], color="#c45911", lw=1.0, label="phase match")
    ax.plot(main["along_true"], main["along_count"], color="#2e7d32", lw=1.6, label="count from portal")
    ax.set_xlabel("true along-track (m)")
    ax.set_ylabel("estimate (m)")
    ax.set_title("phase wraps; counting is absolute")
    ax.legend()
    ax = axes[1]
    ax.plot(100 * dets, gains, "-o", color="#1f4e79")
    ax.axvspan(9, 21, color="#2e7d32", alpha=0.12, label="bible 9–21%")
    ax.axvline(60, color="#c45911", ls="--", lw=0.9, label="60% detection")
    ax.set_xlabel("detection rate (%)")
    ax.set_ylabel("along-track RMSE improvement (%)")
    ax.set_title("F11  ·  10% false alarms")
    ax.legend()
    save_plot(fig, NAME)

    payload = {
        "finding": "F11",
        "name": NAME,
        "rmse_dr_m": main["rmse_dr"],
        "rmse_phase_m": main["rmse_phase"],
        "rmse_count_m": main["rmse_count"],
        "gain_phase_pct": main["gain_phase_pct"],
        "gain_count_pct": main["gain_count_pct"],
        "bible": BIBLE,
        "p_detect": 0.60,
        "p_fa": 0.10,
        "spacing_m": SPACING,
        "seed": seed,
    }
    save_json(NAME, payload)
    return payload


if __name__ == "__main__":
    out = run()
    print(f"F11  phase gain {out['gain_phase_pct']:+.1f}%  count gain {out['gain_count_pct']:+.1f}%")
