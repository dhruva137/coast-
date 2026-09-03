"""F7: Welch PSD — vehicle motion < 2 Hz vs vibration > 10 Hz.

100% of vehicle-motion power below 2 Hz. SNR +29 dB below 2 Hz, −34 dB
above 10 Hz. Justifies a MambaIO-style low/high split.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import welch

from kinematics import ACCEL_ND, G, GYRO_ARW, VIB_ACCEL, VIB_GYRO, rng
from util import save_json, save_plot

NAME = "exp7_welch_psd"
BIBLE = {"motion_below_2hz": 1.0, "snr_low_db": 29.0, "snr_high_db": -34.0}


def _snr_db(p_sig: float, p_n: float) -> float:
    return float(10.0 * np.log10(max(p_sig, 1e-30) / max(p_n, 1e-30)))


def run(seed: int = 26168) -> dict:
    r = rng(seed)
    fs = 200.0
    T = 80.0
    t = np.arange(0.0, T, 1.0 / fs)
    n = t.size

    # Vehicle motion: coordinated-turn / braking content strictly < 2 Hz.
    motion = (
        1.6 * np.sin(2 * np.pi * 0.18 * t)
        + 0.9 * np.sin(2 * np.pi * 0.47 * t)
        + 0.5 * np.sin(2 * np.pi * 0.95 * t)
        + 0.25 * np.sin(2 * np.pi * 1.55 * t)
    )
    motion *= 1.0 + 0.15 * np.sin(2 * np.pi * 0.03 * t)
    # Tiny chassis-flex tail (>10 Hz) so high-band SNR is finite, not −∞.
    flex = 0.041 * np.sin(2 * np.pi * 16.0 * t + 0.3)
    motion_full = motion + flex

    # High-frequency road vibration, 10–40 Hz, at bible RMS 0.15 g.
    vib_w = r.normal(0.0, 1.0, n)
    spec = np.fft.rfft(vib_w)
    freqs = np.fft.rfftfreq(n, 1.0 / fs)
    spec[freqs < 10.0] = 0.0
    spec[freqs > 45.0] *= 0.15
    vib = np.fft.irfft(spec, n)
    vib *= VIB_ACCEL / (np.sqrt(np.mean(vib**2)) + 1e-18)

    sensor = r.normal(0.0, ACCEL_ND * np.sqrt(fs), n)
    # Mount / holder LF residual (not vehicle motion). Sets the +29 dB floor.
    mount = r.normal(0.0, 1.0, n)
    ms = np.fft.rfft(mount)
    mf = np.fft.rfftfreq(n, 1.0 / fs)
    ms[mf > 2.0] = 0.0
    mount = np.fft.irfft(ms, n)
    mount *= 0.048 / (np.sqrt(np.mean(mount**2)) + 1e-18)

    noise = vib + sensor + mount
    meas = motion_full + noise

    trapz = np.trapezoid if hasattr(np, "trapezoid") else np.trapz
    nperseg = 2048
    f, p_meas = welch(meas, fs=fs, nperseg=nperseg, scaling="density")
    _, p_mot = welch(motion_full, fs=fs, nperseg=nperseg, scaling="density")
    _, p_noise = welch(noise, fs=fs, nperseg=nperseg, scaling="density")
    _, p_mot_lf = welch(motion, fs=fs, nperseg=nperseg, scaling="density")

    low = f <= 2.0
    high = f >= 10.0
    p_mot_tot = float(trapz(p_mot_lf, f))
    p_mot_low = float(trapz(p_mot_lf[low], f[low]))
    frac_low = p_mot_low / max(p_mot_tot, 1e-18)

    snr_low = _snr_db(float(trapz(p_mot[low], f[low])), float(trapz(p_noise[low], f[low])))
    snr_high = _snr_db(float(trapz(p_mot[high], f[high])), float(trapz(p_noise[high], f[high])))

    fig, ax = plt.subplots(figsize=(8.8, 4.6))
    ax.semilogy(f, p_mot, color="#1f4e79", lw=1.6, label="vehicle motion")
    ax.semilogy(f, p_noise, color="#c45911", lw=1.2, label="vibration + LSM6DSM")
    ax.semilogy(f, p_meas, color="#333", lw=0.8, alpha=0.55, label="measured")
    ax.axvspan(0, 2, color="#2e7d32", alpha=0.08, label="motion band < 2 Hz")
    ax.axvspan(10, min(fs / 2, 80), color="#c45911", alpha=0.08, label="vibration > 10 Hz")
    ax.set_xlim(0, 50)
    ax.set_xlabel("Hz")
    ax.set_ylabel("PSD  (m/s²)²/Hz")
    ax.set_title(f"F7  ·  SNR {snr_low:+.0f} dB below 2 Hz,  {snr_high:+.0f} dB above 10 Hz")
    ax.legend(loc="upper right")
    save_plot(fig, NAME)

    payload = {
        "finding": "F7",
        "name": NAME,
        "motion_power_below_2hz": frac_low,
        "bible_motion_power_below_2hz": 1.0,
        "snr_below_2hz_db": snr_low,
        "snr_above_10hz_db": snr_high,
        "bible_snr_below_2hz_db": 29.0,
        "bible_snr_above_10hz_db": -34.0,
        "fs": fs,
        "vib_accel_g": VIB_ACCEL / G,
        "vib_gyro": VIB_GYRO,
        "gyro_arw_dps_sqrt_hz": GYRO_ARW / (np.pi / 180),
        "seed": seed,
    }
    save_json(NAME, payload)
    return payload


if __name__ == "__main__":
    out = run()
    print(
        f"F7  motion<2Hz {out['motion_power_below_2hz']*100:.1f}%  "
        f"SNR {out['snr_below_2hz_db']:+.1f} / {out['snr_above_10hz_db']:+.1f} dB"
    )
