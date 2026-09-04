"""Run closed-loop AVNet methods on real IO-VNBD and write a finals table.

Usage (repo root)::

    python lab/stress/run_avnet_closed_loop.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

_STRESS = Path(__file__).resolve().parent
_LAB = _STRESS.parent
sys.path.insert(0, str(_STRESS))
sys.path.insert(0, str(_LAB))

from hardened_outage import run_hardened_outage, verdict  # noqa: E402
from load_iovnbd import find_smartphone_csvs, load_smartphone_csv  # noqa: E402

OUT = _STRESS / "results" / "avnet_closed_loop"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    csvs = find_smartphone_csvs()
    # Prefer the four known-good materialised files
    prefer = ["S-S1.csv", "S-S2.csv", "S-S4.csv", "S-M.csv"]
    ranked = sorted(
        csvs,
        key=lambda p: (prefer.index(p.name) if p.name in prefer else 99, p.name),
    )[:4]
    if not ranked:
        print("FAIL: no real IO-VNBD CSVs")
        return 1

    rows: list[dict] = []
    for path in ranked:
        data = load_smartphone_csv(path)
        # Mid-route 60 s (same family as hardened battery)
        t = data["t_s"]
        mid = float(t[0] + 0.45 * (t[-1] - t[0]))
        i0 = int(np.searchsorted(t, mid))
        try:
            r = run_hardened_outage(data, deny_s=60.0, start_idx=i0, t0_s=30.0)
        except Exception as exc:  # noqa: BLE001
            rows.append({"file": path.name, "error": str(exc)})
            continue
        for method, sc in r["scores"].items():
            v = verdict(sc, deny_s=r["deny_s"])
            rows.append(
                {
                    "file": path.name,
                    "method": method,
                    "final_error_m": round(sc["final_error_m"], 2),
                    "drift_pct": round(sc["drift_pct"], 2),
                    "m_per_km": round(sc["m_per_km"], 2),
                    "distance_m": round(sc["distance_m"], 2),
                    "speed0_mps": round(r["speed0_mps"], 2),
                    "verdict": v,
                }
            )
            print(
                f"{path.name:8s} {method:16s} final={sc['final_error_m']:7.1f} m  "
                f"drift={sc['drift_pct']:6.1f}%  {v}"
            )

    out_json = OUT / "report.json"
    out_json.write_text(json.dumps({"rows": rows}, indent=2), encoding="utf-8")

    # Markdown summary focused on AVNet vs car_bias
    lines = [
        "# AVNet closed-loop on real IO-VNBD (60 s mid-route)",
        "",
        "Methods `avnet_speed` / `avnet_full` (+ `_map`) use trained `avnet_tiny.pt`.",
        "`hold_arclength` / `avnet_arclength` = known-route product mode (label separately).",
        "This is the first wiring of maximize weights into ISRO-style scoring.",
        "",
        "| File | Method | Final m | Drift % | m/km | v0 | Verdict |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        if "error" in row:
            lines.append(f"| {row['file']} | ERROR | — | — | — | — | {row['error']} |")
            continue
        lines.append(
            f"| {row['file']} | `{row['method']}` | {row['final_error_m']} | "
            f"{row['drift_pct']} | {row['m_per_km']} | {row['speed0_mps']} | **{row['verdict']}** |"
        )
    av = [r for r in rows if r.get("method", "").startswith("avnet")]
    arc = [r for r in rows if "arclength" in str(r.get("method", ""))]
    isro = sum(1 for r in av if r.get("verdict") == "PASS_ISRO")
    isro_arc = sum(1 for r in arc if r.get("verdict") == "PASS_ISRO")
    comp = sum(1 for r in av if str(r.get("verdict", "")).startswith("PASS"))
    lines += [
        "",
        f"AVNet-family rows: {len(av)} · PASS_* : {comp} · PASS_ISRO: {isro}",
        f"Arclength-family: {len(arc)} · PASS_ISRO: {isro_arc}",
        "",
        "**Honesty:** known-route map / arclength uses in-dataset polyline (product prior). "
        "PASS_ISRO only if drift <10% and <100 m/km. Free-DR is the hard bar.",
    ]
    (OUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nwrote {out_json}")
    print(f"wrote {OUT / 'summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
