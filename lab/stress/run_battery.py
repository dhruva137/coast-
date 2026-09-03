"""Run the hard real-data stress battery on every available IO-VNBD S-*.csv.

Writes:
  lab/stress/results/report.json
  lab/stress/results/summary.md
  lab/stress/results/figures/*.png

PASS criteria (cars, honest):
  During a 60 s outage near ~15 m/s, final error should be *competitive*
  with a speed-hold + gyro DR. We document actual numbers; we do NOT claim
  PASS if the numbers miss ISRO bars (<10% drift, <100 m / km).

Adversarial two-wheeler claim test:
  Overlay coordinated lean turns on real IO-VNBD IMU noise — car_style
  must blow up; idr_lean must hold. That is the novel claim, not cars.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np

_STRESS = Path(__file__).resolve().parent
_LAB = _STRESS.parent
_ROOT = _LAB.parent
for _p in (_STRESS, _LAB / "eval", _LAB / "baselines"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from load_iovnbd import (  # noqa: E402
    SEED,
    find_smartphone_csvs,
    load_smartphone_csv,
)
from map_aid import apply_map_aid  # noqa: E402
from metrics import (  # noqa: E402
    ate,
    drift_pct,
    jsonable,
    lla_to_enu,
    path_length,
    position_errors,
)
from outage_replay import (  # noqa: E402
    dead_reckon_car_style,
    dead_reckon_idr_lean,
    lean_aware_yaw_rates,
    run_outage_replay,
    score_outage,
    yaw_rate_from_lean,
)

RESULTS = _STRESS / "results"
FIGS = RESULTS / "figures"
OUTAGE_LENGTHS = (20, 40, 60, 90)
G = 9.80665

# ISRO / proposal bars (documented; not invented as passes).
ISRO_DRIFT_PCT = 10.0
ISRO_M_PER_KM = 100.0  # <100 m error per 1 km at 60 km/h


def _segment_for_outage(
    data: dict[str, Any],
    outage_start: int,
    *,
    seed_s: float = 30.0,
    deny_s: float = 90.0,
    margin_s: float = 5.0,
) -> tuple[dict[str, Any], int]:
    """Slice so outage begins at ``outage_start`` after a seed window.

    Returns ``(segment, start_idx_in_segment)`` where ``start_idx_in_segment``
    is the index at which forced deny begins.
    """
    n = data["n"]
    hz = max(1.0, float(data["hz_est"]))
    seed_n = int(seed_s * hz)
    deny_n = int((deny_s + margin_s) * hz)
    i0 = max(0, outage_start - seed_n)
    i1 = min(n, outage_start + deny_n)
    if i1 - i0 < seed_n + 20:
        raise ValueError("not enough samples around outage site")
    out = {
        k: (v[i0:i1].copy() if isinstance(v, np.ndarray) else v)
        for k, v in data.items()
    }
    out["n"] = int(i1 - i0)
    out["path"] = data["path"]
    out["name"] = data["name"]
    out["file_bytes"] = data["file_bytes"]
    out["hz_est"] = data["hz_est"]
    out["header_map"] = data["header_map"]
    out["t_s"] = out["t_s"] - out["t_s"][0]
    start_idx = int(outage_start - i0)
    return out, start_idx


def _mid_route_index(data: dict[str, Any]) -> int:
    return int(data["n"] // 2)


def _high_speed_index(data: dict[str, Any], win_s: float = 60.0) -> int:
    """Index at the start of the highest mean-speed window of length win_s."""
    spd = np.asarray(data["speed_mps"], dtype=np.float64)
    spd = np.where(np.isfinite(spd), spd, 0.0)
    hz = max(1.0, float(data["hz_est"]))
    w = max(10, int(win_s * hz))
    if spd.size <= w:
        return int(np.argmax(spd))
    c = np.cumsum(np.insert(spd, 0, 0.0))
    roll = (c[w:] - c[:-w]) / w
    k = int(np.argmax(roll))
    return k


def _pass_fail_car(scores: dict[str, float], deny_s: float, speed0: float) -> dict[str, Any]:
    """Honest gate for car outages. Competitive ≠ inventing a pass."""
    final = float(scores["final_error_m"])
    drift = float(scores["drift_pct"])
    dist = float(scores["distance_m"])
    expect_m = max(dist, speed0 * deny_s)
    m_per_km = (final / expect_m * 1000.0) if expect_m > 1.0 else float("inf")
    competitive = bool(
        np.isfinite(final)
        and final < max(150.0, 0.5 * expect_m)
        and drift < 50.0
    )
    isro = bool(drift < ISRO_DRIFT_PCT and m_per_km < ISRO_M_PER_KM)
    return {
        "competitive": competitive,
        "isro_bar": isro,
        "m_per_km": float(m_per_km),
        "verdict": (
            "PASS_ISRO" if isro else ("PASS_COMPETITIVE" if competitive else "FAIL")
        ),
    }


def _plot_outage(result: dict[str, Any], title: str, out_path: Path) -> None:
    gt = result["gt_out"]
    fig, ax = plt.subplots(figsize=(7.2, 6.4))
    ax.plot(gt[:, 0], gt[:, 1], color="#222", lw=2.0, label="GNSS GT (held-out)")
    colors = {"car_style": "#c45911", "idr_lean": "#1f4e79", "inekf_basic": "#548235"}
    for name, xy in result["est"].items():
        ax.plot(xy[:, 0], xy[:, 1], color=colors.get(name, "#666"), lw=1.3, label=name)
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_xlabel("east (m)")
    ax.set_ylabel("north (m)")
    ax.set_title(title)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def run_file_battery(data: dict[str, Any]) -> dict[str, Any]:
    """Outage lengths at mid-route and high-speed for one CSV."""
    trials: list[dict[str, Any]] = []

    sites = {
        "mid_route": _mid_route_index(data),
        "high_speed": _high_speed_index(data),
    }
    for site_name, center in sites.items():
        for deny in OUTAGE_LENGTHS:
            try:
                seg, start_idx = _segment_for_outage(
                    data, center, seed_s=30.0, deny_s=float(deny)
                )
                r = run_outage_replay(
                    seg, t0_s=30.0, deny_s=float(deny), start_idx=start_idx, seed=SEED
                )
            except ValueError as exc:
                trials.append(
                    {
                        "site": site_name,
                        "deny_s": deny,
                        "error": str(exc),
                        "verdict": "SKIP",
                    }
                )
                continue
            row: dict[str, Any] = {
                "site": site_name,
                "deny_s": float(r["deny_s"]),
                "requested_deny_s": deny,
                "speed0_mps": r["speed0_mps"],
                "phi_mean_deg": r["phi_mean_deg"],
                "car_vs_lean_final_ratio": r["car_vs_lean_final_ratio"],
                "scores": r["scores"],
                "gates": {
                    m: _pass_fail_car(sc, float(r["deny_s"]), r["speed0_mps"])
                    for m, sc in r["scores"].items()
                },
            }
            # Map aid on car_style outage estimate using pre-outage GNSS corridor.
            i0, i1 = r["i0"], r["i1"]
            conf = ~seg["outage"]
            conf[i0:i1] = False  # do not leak outage GT into the map
            try:
                aided = apply_map_aid(
                    r["est"]["car_style"],
                    seg["lat"],
                    seg["lon"],
                    conf_mask=conf,
                    origin_lat=float(seg["lat"][0]),
                    origin_lon=float(seg["lon"][0]),
                )
                map_scores = score_outage(aided["projected"], r["gt_out"])
                row["map_aid_car_style"] = {
                    "scores": map_scores,
                    "snap_frac": aided["snap_frac"],
                    "mean_abs_cross_track_m": aided["mean_abs_cross_track_m"],
                    "map": aided["map"],
                }
            except Exception as exc:  # noqa: BLE001 — report, don't hide
                row["map_aid_car_style"] = {"error": str(exc)}

            trials.append(row)

            if deny == 60 and site_name in ("mid_route", "high_speed"):
                fig_name = f"{data['name']}_{site_name}_deny{deny}.png"
                _plot_outage(
                    r,
                    f"{data['name']}  {site_name}  deny={deny}s  v0={r['speed0_mps']:.1f} m/s",
                    FIGS / fig_name,
                )
                row["figure"] = str(FIGS / fig_name)

    return {
        "csv": data["path"],
        "name": data["name"],
        "file_bytes": data["file_bytes"],
        "n": data["n"],
        "hz_est": data["hz_est"],
        "header_map": {k: str(v) for k, v in data["header_map"].items()},
        "trials": trials,
    }


def _imu_noise_stats(data: dict[str, Any]) -> dict[str, float]:
    """Empirical high-pass RMS of real IMU (proxy for phone noise floor)."""
    gx, gy, gz = data["gx"], data["gy"], data["gz"]
    ax, ay, az = data["ax"], data["ay"], data["az"]
    # Detrend with simple moving difference.
    def rms_hp(x: np.ndarray) -> float:
        x = np.asarray(x, dtype=np.float64)
        d = np.diff(x)
        d = d[np.isfinite(d)]
        return float(np.sqrt(np.mean(d ** 2))) if d.size else 0.0

    return {
        "gx_rms": rms_hp(gx),
        "gy_rms": rms_hp(gy),
        "gz_rms": rms_hp(gz),
        "ax_rms": rms_hp(ax),
        "ay_rms": rms_hp(ay),
        "az_rms": rms_hp(az),
    }


def run_adversarial_tw(
    data: dict[str, Any],
    *,
    seed: int = SEED,
    lean_deg: float = 26.0,
    speed_mps: float = 12.0,
    n_turns: int = 3,
    straight_m: float = 40.0,
) -> dict[str, Any]:
    """Inject coordinated lean kinematics; keep real IO-VNBD IMU noise.

    Ground-truth path from true ψ̇. Car-style uses ω_z = ψ̇ cos φ (plus noise)
    and must drift; lean-aware recovers ψ̇ via F2+F5.
    """
    rng = np.random.default_rng(int(seed))
    stats = _imu_noise_stats(data)
    hz = 10.0
    dt = 1.0 / hz
    phi_mag = math.radians(float(lean_deg))
    v = float(speed_mps)
    psi_dot = (G * math.tan(phi_mag)) / v
    turn_s = abs(math.pi / 2.0 / psi_dot)  # 90° turn
    straight_s = straight_m / v

    segments: list[tuple[str, float, float]] = []
    for _k in range(n_turns):
        segments.append(("straight", straight_s, 0.0))
        # SAME-DIRECTION leans so car-style cos(φ) error compounds (F3).
        segments.append(("turn", turn_s, phi_mag))
    segments.append(("straight", straight_s, 0.0))

    ts: list[float] = [0.0]
    phis: list[float] = [0.0]
    psids: list[float] = [0.0]
    for kind, dur, phi in segments:
        n = max(1, int(round(dur / dt)))
        for _ in range(n):
            ts.append(ts[-1] + dt)
            if kind == "turn":
                phis.append(phi)
                psids.append(psi_dot * math.copysign(1.0, phi) if abs(phi) > 1e-9 else 0.0)
            else:
                phis.append(0.0)
                psids.append(0.0)
    t = np.asarray(ts, dtype=np.float64)
    phi = np.asarray(phis, dtype=np.float64)
    psi_dot_arr = np.asarray(psids, dtype=np.float64)
    n = t.size

    # F1 body rates + real noise scale.
    wx = np.gradient(phi, dt)
    wy = psi_dot_arr * np.sin(phi)
    wz = psi_dot_arr * np.cos(phi)
    # Scale noise to empirical RMS (clamped to sane phone range).
    noise_g = float(np.clip(np.mean([stats["gx_rms"], stats["gy_rms"], stats["gz_rms"]]), 0.01, 0.15))
    noise_a = float(np.clip(np.mean([stats["ax_rms"], stats["ay_rms"], stats["az_rms"]]), 0.05, 1.0))
    gx = wx + rng.normal(0.0, noise_g, n)
    gy = wy + rng.normal(0.0, noise_g, n)
    gz = wz + rng.normal(0.0, noise_g, n)
    speed = np.full(n, v, dtype=np.float64)

    # True path.
    x_gt = np.zeros(n)
    y_gt = np.zeros(n)
    yaw_gt = np.zeros(n)
    for i in range(1, n):
        yaw_gt[i] = float(
            ((yaw_gt[i - 1] + psi_dot_arr[i - 1] * dt + math.pi) % (2 * math.pi)) - math.pi
        )
        x_gt[i] = x_gt[i - 1] + v * math.sin(yaw_gt[i - 1]) * dt
        y_gt[i] = y_gt[i - 1] + v * math.cos(yaw_gt[i - 1]) * dt

    xc, yc, _ = dead_reckon_car_style(t, speed, gz, x0=0.0, y0=0.0, yaw0=0.0)
    xl, yl, _, phi_hat = dead_reckon_idr_lean(
        t, speed, gx, gy, gz, x0=0.0, y0=0.0, yaw0=0.0
    )
    gt_xy = np.column_stack([x_gt, y_gt])
    sc_car = score_outage(np.column_stack([xc, yc]), gt_xy)
    sc_lean = score_outage(np.column_stack([xl, yl]), gt_xy)

    # Claim gate: lean must beat car by a clear margin on this injection.
    claim_ok = bool(
        sc_lean["drift_pct"] < 15.0
        and sc_car["drift_pct"] > sc_lean["drift_pct"] * 2.0
        and sc_car["final_error_m"] > sc_lean["final_error_m"] * 2.0
    )

    fig, ax = plt.subplots(figsize=(7.2, 6.4))
    ax.plot(x_gt, y_gt, color="#222", lw=2.2, label="truth (lean turns)")
    ax.plot(xc, yc, color="#c45911", lw=1.4, label=f"car_style  drift={sc_car['drift_pct']:.1f}%")
    ax.plot(xl, yl, color="#1f4e79", lw=1.4, label=f"idr_lean  drift={sc_lean['drift_pct']:.1f}%")
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_title(f"Adversarial TW  φ={lean_deg:.0f}°  noise from {data['name']}")
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig_path = FIGS / f"adversarial_tw_{data['name']}.png"
    fig.savefig(fig_path, dpi=120)
    plt.close(fig)

    return {
        "source_csv": data["path"],
        "source_name": data["name"],
        "evidence_class": "INJECTED_LEAN",
        "yaw_mapping": "vehicle_yaw_rate = -GYROSCOPE Pitch",
        "field_proof": False,
        "lean_deg": lean_deg,
        "speed_mps": v,
        "noise_gyro_rms": noise_g,
        "noise_accel_rms": noise_a,
        "imu_stats_from_csv": stats,
        "car_style": sc_car,
        "idr_lean": sc_lean,
        "phi_hat_rmse_deg": float(
            np.sqrt(np.mean((np.rad2deg(phi_hat - phi)) ** 2))
        ),
        "claim_pass": claim_ok,
        "verdict": "PASS_CLAIM" if claim_ok else "FAIL_CLAIM",
        "figure": str(fig_path),
        "note": (
            "Injected coordinated lean on top of real IO-VNBD noise scales. "
            "This is the two-wheeler claim test — not a car result."
        ),
    }


def _summarize_md(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# SIH26168 real-data stress battery")
    lines.append("")
    lines.append(f"Seed: `{report['seed']}`  ·  Generated deterministically.")
    lines.append("")
    lines.append("## CSVs used (real, >1 MB)")
    lines.append("")
    lines.append("| file | bytes | n | hz |")
    lines.append("|---|---:|---:|---:|")
    for f in report["files"]:
        lines.append(
            f"| `{f['name']}` | {f['file_bytes']:,} | {f['n']} | {f['hz_est']:.2f} |"
        )
    lines.append("")
    lines.append("## Car outage pass/fail (honest)")
    lines.append("")
    lines.append(
        "IO-VNBD is **cars** — lean-aware must **not** magically crush car-style. "
        "ISRO bars: drift <10%, <100 m/km. Competitive = not exploding."
    )
    lines.append("")
    lines.append(
        "| csv | site | deny_s | v0 | method | final_m | ate_m | drift% | m/km | verdict |"
    )
    lines.append("|---|---|---:|---:|---|---:|---:|---:|---:|---|")
    for f in report["files"]:
        for tr in f["trials"]:
            if tr.get("verdict") == "SKIP" or "scores" not in tr:
                lines.append(
                    f"| {f['name']} | {tr.get('site')} | {tr.get('deny_s')} |  |  |  |  |  |  | SKIP |"
                )
                continue
            for method, sc in tr["scores"].items():
                gate = tr["gates"][method]
                lines.append(
                    f"| {f['name']} | {tr['site']} | {tr['deny_s']:.0f} | "
                    f"{tr['speed0_mps']:.1f} | {method} | "
                    f"{sc['final_error_m']:.1f} | {sc['ate_m']:.1f} | "
                    f"{sc['drift_pct']:.1f} | {gate['m_per_km']:.0f} | "
                    f"**{gate['verdict']}** |"
                )
    lines.append("")
    lines.append("## Car sanity: lean ≈ car on cars")
    lines.append("")
    lines.append("| csv | site | deny_s | final_lean / final_car | phi_mean_deg |")
    lines.append("|---|---|---:|---:|---:|")
    for f in report["files"]:
        for tr in f["trials"]:
            if "car_vs_lean_final_ratio" not in tr:
                continue
            lines.append(
                f"| {f['name']} | {tr['site']} | {tr['deny_s']:.0f} | "
                f"{tr['car_vs_lean_final_ratio']:.3f} | {tr['phi_mean_deg']:.2f} |"
            )
    lines.append("")
    adv = report["adversarial_tw"]
    lines.append("## Adversarial two-wheeler (INJECTED_LEAN claim test)")
    lines.append("")
    lines.append(
        f"Noise from `{adv['source_name']}` · lean={adv['lean_deg']}° · "
        f"v={adv['speed_mps']} m/s · verdict=**{adv['verdict']}**"
    )
    lines.append("")
    lines.append("| method | final_m | ate_m | drift% |")
    lines.append("|---|---:|---:|---:|")
    lines.append(
        f"| car_style | {adv['car_style']['final_error_m']:.1f} | "
        f"{adv['car_style']['ate_m']:.1f} | {adv['car_style']['drift_pct']:.1f} |"
    )
    lines.append(
        f"| idr_lean | {adv['idr_lean']['final_error_m']:.1f} | "
        f"{adv['idr_lean']['ate_m']:.1f} | {adv['idr_lean']['drift_pct']:.1f} |"
    )
    lines.append("")
    lines.append(f"Figure: `{adv['figure']}`")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    for n in report.get("notes", []):
        lines.append(f"- {n}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)

    csvs = find_smartphone_csvs()
    if not csvs:
        raise SystemExit(
            "FAIL LOUDLY: no real S-*.csv >1 MB under data/raw/IO-VNBD. "
            "Pull Git LFS blobs first."
        )

    print(f"Found {len(csvs)} real smartphone CSVs:")
    files_out: list[dict[str, Any]] = []
    notes: list[str] = []
    for p in csvs:
        print(f"  loading {p.name} ({p.stat().st_size:,} bytes) …")
        data = load_smartphone_csv(p)
        print(
            f"    n={data['n']} hz~{data['hz_est']:.2f} "
            f"cols={list(data['header_map'].keys())}"
        )
        fb = run_file_battery(data)
        files_out.append(fb)
        # Sanity note on car lean ratio for 60 s mid-route.
        for tr in fb["trials"]:
            if tr.get("site") == "mid_route" and tr.get("requested_deny_s") == 60:
                ratio = tr.get("car_vs_lean_final_ratio")
                if ratio is not None and np.isfinite(ratio) and (ratio < 0.5 or ratio > 2.0):
                    notes.append(
                        f"WARN {p.name}: lean/car final ratio={ratio:.2f} on cars "
                        f"(expected ~1). Investigate."
                    )
                else:
                    notes.append(
                        f"OK {p.name}: lean~car on cars "
                        f"(ratio={ratio:.3f}, phi~{tr.get('phi_mean_deg', float('nan')):.2f} deg)."
                    )

    # Adversarial TW using noise from the first CSV.
    data0 = load_smartphone_csv(csvs[0])
    print(f"Running adversarial two-wheeler injection from {data0['name']} …")
    adv = run_adversarial_tw(data0, seed=SEED)
    notes.append(
        f"Adversarial TW: car drift={adv['car_style']['drift_pct']:.1f}% vs "
        f"lean drift={adv['idr_lean']['drift_pct']:.1f}% → {adv['verdict']}"
    )

    report = {
        "seed": SEED,
        "mapping": {
            "vehicle_yaw_rate": "-GYROSCOPE Pitch",
            "loader_expression": "gz = -gyro_pitch_raw",
        },
        "outage_lengths_s": list(OUTAGE_LENGTHS),
        "isro_bars": {"drift_pct": ISRO_DRIFT_PCT, "m_per_km": ISRO_M_PER_KM},
        "files": files_out,
        "adversarial_tw": adv,
        "notes": notes,
        "csv_paths": [
            {"path": str(p), "bytes": p.stat().st_size, "name": p.name} for p in csvs
        ],
    }

    # Drop bulky arrays before JSON (est/gt already not in files_out trials).
    report_path = RESULTS / "report.json"
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(jsonable(report), f, indent=2)
    summary = _summarize_md(report)
    summary_path = RESULTS / "summary.md"
    summary_path.write_text(summary, encoding="utf-8")

    print(f"\nWrote {report_path}")
    print(f"Wrote {summary_path}")
    print(f"Adversarial: {adv['verdict']}")
    # Print compact pass/fail for 60 s high-speed car_style.
    print("\n=== 60s outage snapshot (car_style) ===")
    for f in files_out:
        for tr in f["trials"]:
            if tr.get("requested_deny_s") == 60 and "scores" in tr:
                sc = tr["scores"]["car_style"]
                gate = tr["gates"]["car_style"]
                print(
                    f"  {f['name']:10s} {tr['site']:12s} "
                    f"final={sc['final_error_m']:7.1f} m  "
                    f"drift={sc['drift_pct']:5.1f}%  {gate['verdict']}"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
