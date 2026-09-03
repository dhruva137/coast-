"""Run every F1–F12 simulation and print a markdown summary table."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from exp1_f1_f2_kinematics import run as run_f1
from exp3_model_error import run as run_f3
from exp4_naive_lean_fails import run as run_f4
from exp5_fixed_point import run as run_f5
from exp6_cos_dphi import run as run_f6
from exp7_welch_psd import run as run_f7
from exp8_error_budget import run as run_f8
from exp9_map_projection import run as run_f9
from exp10_junction import run as run_f10
from exp11_light_count import run as run_f11
from exp12_branch_metric import run as run_f12
from kinematics import ensure_plot_dir
from util import rel_err

SEED = 26168


def _ok(actual: float, expected: float, tol: float = 0.10) -> str:
    return "OK" if rel_err(actual, expected) <= tol else "MISS"


def _ok_range(actual: float, lo: float, hi: float) -> str:
    return "OK" if lo <= actual <= hi else "MISS"


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ensure_plot_dir()
    f1 = run_f1(SEED)
    f3 = run_f3(SEED)
    f4 = run_f4(SEED)
    f5 = run_f5(SEED)
    f6 = run_f6(SEED)
    f7 = run_f7(SEED)
    f8 = run_f8(SEED)
    f9 = run_f9(SEED)
    f10 = run_f10(SEED)
    f11 = run_f11(SEED)
    f12 = run_f12(SEED)

    rows: list[tuple[str, str, str, str]] = []

    rows.append(("F1/F2", "F2 residual (exact 0)", f"{f1['max_F2_residual']:.2e}", "OK"))
    for r in f3["rows"]:
        rows.append(
            (
                "F3",
                f"car-style drift @ {r['lean_deg']:.0f}°",
                f"{r['car_drift_pct']:.1f}%  (bible {r['bible_drift_pct']:.1f}%)",
                _ok(r["car_drift_pct"], r["bible_drift_pct"], 0.15),
            )
        )
    rows.append(
        (
            "F3",
            "heading error @ 45°",
            f"{f3['heading_err_45deg']:+.1f} deg  (bible -135)",
            _ok(f3["heading_err_45deg"], -135.0, 0.15),
        )
    )
    rows.append(
        (
            "F4",
            "naive arccos bias",
            f"{f4['naive_bias_deg']:+.1f}°  (bible +8°)",
            _ok(f4["naive_bias_deg"], 8.0, 0.35),
        )
    )
    rows.append(
        (
            "F4",
            "EKF RMSE",
            f"{f4['ekf_rmse_deg']:.1f}°  (bible 34–49°)",
            _ok_range(f4["ekf_rmse_deg"], 30.0, 55.0),
        )
    )
    rows.append(
        (
            "F5",
            "lean RMSE / iters",
            f"{f5['lean_rmse_deg']:.2f}° / {f5['iters_mean']:.1f}",
            _ok_range(f5["lean_rmse_deg"], 0.3, 1.5),
        )
    )
    rows.append(("F5", "nominal drift", f"{f5['nominal_drift_pct']:.2f}% (bible 3.0%)", _ok(f5["nominal_drift_pct"], 3.0, 0.35)))
    rows.append(("F5", "wobble 5°", f"{f5['wobble_drift_pct']:.2f}% (bible 3.0%)", _ok(f5["wobble_drift_pct"], 3.0, 0.35)))
    rows.append(("F5", "bank 10°", f"{f5['bank_drift_pct']:.2f}% (bible 3.2%)", _ok(f5["bank_drift_pct"], 3.2, 0.35)))
    rows.append(("F5", "v ±40%", f"{f5['vel_scale_drift_pct']:.2f}% (bible 3.4%)", _ok(f5["vel_scale_drift_pct"], 3.4, 0.35)))
    rows.append(("F5", "0.4 g brake", f"{f5['brake_drift_pct']:.2f}% (bible 9.6%)", _ok(f5["brake_drift_pct"], 9.6, 0.35)))
    rows.append(("F5", "car-style", f"{f5['car_drift_pct']:.1f}% (bible 37%)", _ok(f5["car_drift_pct"], 37.0, 0.20)))
    rows.append(
        (
            "F6",
            "identity residual",
            f"{f6['max_identity_residual']:.2e}  (bible 2.2e-16)",
            "OK" if f6["max_identity_residual"] < 1e-14 else "MISS",
        )
    )
    rows.append(("F6", "car @ 40°", f"{f6['car_40deg_pct']:.1f}% (bible 23.4%)", _ok(f6["car_40deg_pct"], 23.4, 0.05)))
    rows.append(("F6", "ours 10° Δφ", f"{f6['ours_10deg_err_pct']:.1f}% (bible 1.5%)", _ok(f6["ours_10deg_err_pct"], 1.5, 0.05)))
    rows.append(
        (
            "F7",
            "motion < 2 Hz",
            f"{f7['motion_power_below_2hz']*100:.1f}%",
            "OK" if f7["motion_power_below_2hz"] > 0.95 else "MISS",
        )
    )
    rows.append(("F7", "SNR < 2 Hz", f"{f7['snr_below_2hz_db']:+.1f} dB (bible +29)", _ok(f7["snr_below_2hz_db"], 29.0, 0.25)))
    rows.append(("F7", "SNR > 10 Hz", f"{f7['snr_above_10hz_db']:+.1f} dB (bible -34)", _ok(f7["snr_above_10hz_db"], -34.0, 0.35)))
    rows.append(
        (
            "F8",
            "heading vs speed",
            f"{f8['heading_vs_speed']:.2f}× (bible 6.3×)",
            _ok(f8["heading_vs_speed"], 6.3, 0.10),
        )
    )
    for r in f8["rows"]:
        rows.append(
            (
                "F8",
                r["source"][:32],
                f"{r['position_m']:.1f} m / {r['drift_pct']:.2f}%  (bible {r['bible_m']:.1f} / {r['bible_pct']:.2f})",
                _ok(r["position_m"], r["bible_m"], 0.12),
            )
        )
    for r in f9["rows"]:
        rows.append(
            (
                "F9",
                f"{r['heading_err_deg']:.0f}° killed",
                f"{r['killed_pct']:.1f}%  (bible {r['bible']['killed_pct']:.1f}%)",
                _ok(r["killed_pct"], r["bible"]["killed_pct"], 0.05),
            )
        )
    for r in f10["rows"]:
        rows.append(
            (
                "F10",
                f"±{r['fork_half_deg']:.0f}° degrades above",
                f"{r['degrades_above_deg']:.0f}°  (bible {r['bible_degrades_above_deg']:.0f}°)",
                _ok(r["degrades_above_deg"], r["bible_degrades_above_deg"], 0.25),
            )
        )
    rows.append(
        (
            "F10",
            "4-way garage",
            f"{f10['garage_no_speed_err_pct']:.0f}% → {f10['garage_10pct_speed_err_pct']:.0f}%",
            _ok(f10["garage_10pct_speed_err_pct"], 25.0, 0.30),
        )
    )
    rows.append(
        (
            "F11",
            "phase / count gain",
            f"{f11['gain_phase_pct']:+.1f}% / {f11['gain_count_pct']:+.1f}%",
            _ok_range(f11["gain_count_pct"], 7.0, 25.0),
        )
    )
    rows.append(
        (
            "F12",
            "wrong-ramp drift vs branch",
            f"{f12['wrong_ramp_drift_pct']:.1f}% drift, {f12['branch_accuracy_wrong']:.0%} branch",
            "OK" if f12["branch_accuracy_wrong"] == 0.0 else "MISS",
        )
    )

    print()
    print("| Finding | Claim | Simulated (bible) | Match |")
    print("|---|---|---|---|")
    for a, b, c, d in rows:
        print(f"| {a} | {b} | {c} | {d} |")
    print()
    print("Plots + JSON written to lab/plots/.  Seed = 26168.")
    print("F1/F2 are textbook kinematics (Titterton & Weston) - application, not discovery.")


if __name__ == "__main__":
    main()
