#!/usr/bin/env python3
"""Hardened real-data battery: bias + map. Writes results/hardened_*.json|md."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

_STRESS = Path(__file__).resolve().parent
if str(_STRESS) not in sys.path:
    sys.path.insert(0, str(_STRESS))

from hardened_outage import run_hardened_on_csv, verdict  # noqa: E402
from load_iovnbd import find_smartphone_csvs  # noqa: E402
from outage_replay import lean_aware_yaw_rates  # noqa: E402

try:
    from car_style import integrate_heading_speed
except ImportError:
    from baselines.car_style import integrate_heading_speed  # type: ignore

RESULTS = _STRESS / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
SEED = 26168
DENIES = (20.0, 40.0, 60.0)


def _site_indices(data_n: int, hz: float = 10.0) -> dict[str, int]:
    # early (~2 min), mid, and ~70% into the log
    return {
        "early_route": max(int(120 * hz), 300),
        "mid_route": max(int(90 * hz), data_n // 2),
        "late_route": max(int(90 * hz), int(data_n * 0.7)),
    }


def adversarial_tw(noise_csv: Path) -> dict:
    """Same-direction 26° lean injection with corrected real phone channels."""
    from load_iovnbd import load_smartphone_csv

    d = load_smartphone_csv(noise_csv)
    rng = np.random.default_rng(SEED)
    n = 800
    dt = 0.1
    v = 12.0
    phi = np.deg2rad(26.0)
    psi = 9.80665 * np.tan(phi) / v
    t = np.arange(n) * dt
    # Same-direction turns forever (F3 geometry).
    gy = psi * np.sin(phi) + 0.02 * rng.normal(size=n)
    gz = psi * np.cos(phi) + 0.02 * rng.normal(size=n)
    # Inject real noise envelope
    k = min(n, d["gz"].size)
    gy[:k] += 0.3 * (d["gy"][:k] - np.mean(d["gy"][:k]))
    gz[:k] += 0.3 * (d["gz"][:k] - np.mean(d["gz"][:k]))
    speed = np.full(n, v)
    gx = np.zeros(n)
    psi_lean, _ = lean_aware_yaw_rates(gy, gz, speed, gx)
    dts = np.full(n, dt)
    # GT: true psi
    xg, yg, _ = integrate_heading_speed(dts, speed, np.full(n, psi), x0=0, y0=0, yaw0=0)
    xc, yc, _ = integrate_heading_speed(dts, speed, gz, x0=0, y0=0, yaw0=0)
    xl, yl, _ = integrate_heading_speed(dts, speed, psi_lean, x0=0, y0=0, yaw0=0)
    gt = np.column_stack([xg, yg])
    dist = v * t[-1]

    def sc(xy):
        err = float(np.linalg.norm(xy[-1] - gt[-1]))
        return {"final_m": err, "drift_pct": 100.0 * err / dist}

    car = sc(np.column_stack([xc, yc]))
    lean = sc(np.column_stack([xl, yl]))
    ok = lean["drift_pct"] < car["drift_pct"] and lean["drift_pct"] < 10.0
    return {
        "car": car,
        "lean": lean,
        "verdict": "PASS_CLAIM" if ok else "FAIL_CLAIM",
        "noise_from": noise_csv.name,
        "evidence_class": "INJECTED_LEAN",
        "yaw_mapping": "vehicle_yaw_rate = -GYROSCOPE Pitch",
        "noise_extraction": (
            "0.3 * demeaned corrected IO-VNBD gy/gz channel samples; "
            "kinematics and lean are injected"
        ),
        "field_proof": False,
    }


def main() -> int:
    csvs = find_smartphone_csvs()
    if not csvs:
        print("FAIL: no real IO-VNBD S-*.csv (>1MB)")
        return 2

    from load_iovnbd import load_smartphone_csv

    rows = []
    notes = []
    for csv in csvs:
        data = load_smartphone_csv(csv)
        n = data["n"]
        sites = _site_indices(n, data["hz_est"] or 10.0)
        for site, idx in sites.items():
            for deny in DENIES:
                try:
                    r = run_hardened_on_csv(csv, deny_s=deny, start_idx=idx)
                except Exception as exc:  # noqa: BLE001
                    notes.append(f"ERR {csv.name} {site} {deny}: {exc}")
                    continue
                for method, sc in r["scores"].items():
                    v = verdict(sc, deny_s=deny)
                    rows.append(
                        {
                            "csv": csv.name,
                            "site": site,
                            "deny_s": deny,
                            "v0": round(r["speed0_mps"], 2),
                            "bias_dps": round(r["gyro_bias_z_dps"], 4),
                            "method": method,
                            "final_m": round(sc["final_error_m"], 2),
                            "ate_m": round(sc["ate_m"], 2),
                            "drift_pct": round(sc["drift_pct"], 2),
                            "m_per_km": round(sc["m_per_km"], 1),
                            "verdict": v,
                        }
                    )
                notes.append(
                    f"OK {csv.name} {site} {deny}s bias={r['gyro_bias_z_dps']:.4f}°/s "
                    f"map_route={r['map'].get('route_enabled')}"
                )

    adv = adversarial_tw(csvs[0])

    # Car sanity: lean ≈ car on cars (idr_bias vs car_bias finals).
    sanity_rows = []
    by_key: dict[tuple, dict] = {}
    for r in rows:
        key = (r["csv"], r["site"], r["deny_s"])
        by_key.setdefault(key, {})[r["method"]] = r
    for key, methods in by_key.items():
        car = methods.get("car_bias")
        lean = methods.get("idr_bias")
        if not car or not lean:
            continue
        cf = max(car["final_m"], 1e-6)
        ratio = lean["final_m"] / cf
        sanity_rows.append(
            {
                "csv": key[0],
                "site": key[1],
                "deny_s": key[2],
                "ratio": round(ratio, 3),
                "ok": 0.85 <= ratio <= 1.15,
            }
        )
    sanity_ok = bool(sanity_rows) and all(s["ok"] for s in sanity_rows)

    # Focus table: 60s + map / bias methods
    focus = [
        r
        for r in rows
        if r["deny_s"] == 60.0
        and (
            r["method"].endswith("_map")
            or r["method"] in ("car_bias", "idr_bias", "car_bias_map", "idr_bias_map")
        )
    ]
    passes = sum(1 for r in focus if r["verdict"].startswith("PASS"))
    fails = sum(1 for r in focus if r["verdict"] == "FAIL")
    map_competitive = [
        r
        for r in rows
        if r["deny_s"] == 60.0
        and r["method"].endswith("_map")
        and not r["method"].endswith("_mapblind")
        and not r["method"].endswith("_mapproj")
        and r["verdict"].startswith("PASS")
    ]
    map_competitive_scenarios = sorted(
        {(r["csv"], r["site"]) for r in map_competitive}
    )

    report = {
        "seed": SEED,
        "csvs": [{"name": c.name, "bytes": c.stat().st_size} for c in csvs],
        "n_rows": len(rows),
        "focus_60s_pass": passes,
        "focus_60s_fail": fails,
        "map_aided_60s_pass_competitive_methods": len(map_competitive),
        "map_aided_60s_pass_competitive_scenarios": len(map_competitive_scenarios),
        "map_aided_60s_pass_scenarios": [
            {"csv": csv, "site": site}
            for csv, site in map_competitive_scenarios
        ],
        "mapping": {
            "vehicle_yaw_rate": "-GYROSCOPE Pitch",
            "loader_expression": "gz = -gyro_pitch_raw",
        },
        "map_prior_provenance": {
            "route_mode": (
                "in-dataset known-route geometry built from the full GNSS polyline, "
                "including the evaluated interval; no live GNSS is used during replay"
            ),
            "field_independent": False,
            "note": (
                "This emulates an externally known road corridor but is not an "
                "independently sourced OSM/fleet map proof."
            ),
        },
        "car_lean_sanity": {"ok": sanity_ok, "rows": sanity_rows},
        "rows": rows,
        "adversarial_tw": adv,
        "notes": notes,
    }
    (RESULTS / "hardened_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Hardened real-data stress (bias + map)",
        "",
        f"CSVs: {', '.join(c.name for c in csvs)}",
        f"Focus (60s outages): PASS={passes} FAIL={fails}",
        (
            "Map-aided 60s PASS_*: "
            f"{len(map_competitive)} methods across "
            f"{len(map_competitive_scenarios)} independent scenario"
            f"{'s' if len(map_competitive_scenarios) != 1 else ''}"
        ),
        f"Car lean~car sanity: {'OK' if sanity_ok else 'FAIL'}",
        "",
        "## 60 s outages (selected methods)",
        "",
        "| csv | site | method | final_m | drift% | m/km | verdict |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for r in focus:
        if r["method"] in (
            "car_bias",
            "idr_bias",
            "car_bias_map",
            "idr_bias_map",
            "inekf_bias_map",
        ):
            lines.append(
                f"| {r['csv']} | {r['site']} | `{r['method']}` | {r['final_m']} | {r['drift_pct']} | {r['m_per_km']} | **{r['verdict']}** |"
            )
    lines += [
        "",
        "## Adversarial two-wheeler",
        (
            f"- **INJECTED_LEAN (not field proof):** car drift="
            f"{adv['car']['drift_pct']:.1f}%  lean drift="
            f"{adv['lean']['drift_pct']:.1f}% → **{adv['verdict']}**"
        ),
        "",
        "## Interpretation",
        (
            "- `*_map` = in-dataset known-route geometry + gyro-bias cal + "
            "forward snap + heading→tangent blend. It includes the evaluated "
            "interval's route geometry and is not independent OSM/fleet-map proof."
        ),
        "- Mid/late sites often still FAIL when free-DR leaves the corridor (honest). Early stable segments can be PASS_COMPETITIVE.",
        "- Raw open-loop without map will fail on phone gyros; that is physics (F8), not a softener.",
        "",
    ]
    (RESULTS / "hardened_summary.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("wrote", RESULTS / "hardened_report.json")
    return 0 if adv["verdict"] == "PASS_CLAIM" else 1


if __name__ == "__main__":
    raise SystemExit(main())
