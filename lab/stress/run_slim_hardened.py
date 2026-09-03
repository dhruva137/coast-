#!/usr/bin/env python3
"""Slim hardened battery — one CSV, 60s mid/late only. Finishes in <2 min."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

_STRESS = Path(__file__).resolve().parent
sys.path.insert(0, str(_STRESS))

from hardened_outage import run_hardened_on_csv, verdict  # noqa: E402
from load_iovnbd import find_smartphone_csvs, load_smartphone_csv  # noqa: E402
from map_aid import build_map_from_gnss  # noqa: E402

RESULTS = _STRESS / "results"
RESULTS.mkdir(parents=True, exist_ok=True)


def downsample_map_build(lat, lon, origin_lat, origin_lon, stride: int = 20):
    """Build route map from every Nth GNSS sample (~2 s at 10 Hz)."""
    idx = np.arange(0, lat.size, stride)
    return build_map_from_gnss(
        lat[idx], lon[idx],
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        densify_m=25.0,
    )


def main() -> int:
    csvs = find_smartphone_csvs()
    # Prefer smallest real file for speed.
    csvs = sorted(csvs, key=lambda p: p.stat().st_size)
    if not csvs:
        print("no real CSVs")
        return 2
    # Use two: smallest + largest for coverage
    targets = [csvs[0]]
    if len(csvs) > 1:
        targets.append(csvs[-1])

    rows = []
    for csv in targets:
        data = load_smartphone_csv(csv)
        n = data["n"]
        sites = {
            "mid_route": max(900, n // 2),
            "late_route": max(900, int(n * 0.65)),
        }
        print(f"=== {csv.name} n={n} bytes={data['file_bytes']} ===", flush=True)
        for site, idx in sites.items():
            for deny in (40.0, 60.0):
                print(f"  {site} deny={deny}s idx={idx} ...", flush=True)
                r = run_hardened_on_csv(csv, deny_s=deny, start_idx=idx)
                for method, sc in r["scores"].items():
                    # Skip mapblind spam in summary focus
                    if "mapblind" in method:
                        continue
                    v = verdict(sc, deny_s=deny)
                    row = {
                        "csv": csv.name,
                        "site": site,
                        "deny_s": deny,
                        "v0": round(r["speed0_mps"], 2),
                        "bias_dps": round(r["gyro_bias_z_dps"], 4),
                        "method": method,
                        "final_m": round(sc["final_error_m"], 2),
                        "drift_pct": round(sc["drift_pct"], 2),
                        "m_per_km": round(sc["m_per_km"], 1),
                        "verdict": v,
                    }
                    rows.append(row)
                    if method in ("car_bias", "idr_bias", "car_bias_map", "idr_bias_map"):
                        print(
                            f"    {method:16s} final={sc['final_error_m']:7.1f}m "
                            f"drift={sc['drift_pct']:6.1f}% {v}",
                            flush=True,
                        )

    # Adversarial TW quick
    from run_hardened_battery import adversarial_tw

    adv = adversarial_tw(targets[0])
    print("ADVERSARIAL", adv, flush=True)

    focus = [r for r in rows if r["deny_s"] == 60 and "map" in r["method"]]
    passes = sum(1 for r in focus if r["verdict"].startswith("PASS"))
    report = {
        "rows": rows,
        "adversarial_tw": adv,
        "focus_60s_map_pass": passes,
        "focus_60s_map_n": len(focus),
    }
    (RESULTS / "hardened_slim_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    md = ["# Slim hardened stress (real IO-VNBD)", ""]
    md.append(f"Map 60s PASS={passes}/{len(focus)}")
    md.append("")
    md.append("| csv | site | method | final_m | drift% | m/km | verdict |")
    md.append("|---|---|---|---:|---:|---:|---|")
    for r in rows:
        if r["deny_s"] == 60 and r["method"] in ("car_bias", "idr_bias", "car_bias_map", "idr_bias_map"):
            md.append(
                f"| {r['csv']} | {r['site']} | `{r['method']}` | {r['final_m']} | "
                f"{r['drift_pct']} | {r['m_per_km']} | **{r['verdict']}** |"
            )
    md.append("")
    md.append(
        f"Adversarial TW: car={adv['car']['drift_pct']:.1f}% lean={adv['lean']['drift_pct']:.1f}% → **{adv['verdict']}**"
    )
    (RESULTS / "hardened_slim_summary.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
