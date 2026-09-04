"""Leave-file-out: train AVNet excluding eval CSV, then score closed-loop.

Paper-grade protocol — no train/eval leakage on the held-out drive.

Usage (repo root)::

    python lab/stress/run_leave_file_out.py --epochs 20 --device auto
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

_STRESS = Path(__file__).resolve().parent
_LAB = _STRESS.parent
_ROOT = _LAB.parent
sys.path.insert(0, str(_STRESS))
sys.path.insert(0, str(_LAB))
sys.path.insert(0, str(_LAB / "models"))

from hardened_outage import run_hardened_outage, verdict  # noqa: E402
from load_iovnbd import find_smartphone_csvs, load_smartphone_csv  # noqa: E402
from train_avnet import train  # noqa: E402

OUT = _STRESS / "results" / "leave_file_out"
WEIGHTS_ROOT = _LAB / "models" / "weights" / "lfo"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Leave-file-out AVNet closed-loop")
    p.add_argument("--epochs", type=int, default=20)
    p.add_argument("--device", type=str, default="auto")
    p.add_argument("--n-windows", type=int, default=0, help="0 = all windows from train files")
    p.add_argument("--skip-train", action="store_true", help="Reuse existing LFO weights")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    prefer = ["S-S1.csv", "S-S2.csv", "S-S4.csv", "S-M.csv"]
    csvs = find_smartphone_csvs()
    ranked = sorted(
        csvs,
        key=lambda p: (prefer.index(p.name) if p.name in prefer else 99, p.name),
    )[:4]
    if not ranked:
        print("FAIL: no real IO-VNBD CSVs")
        return 1

    rows: list[dict] = []
    train_meta: list[dict] = []

    for path in ranked:
        hold = path.name
        wdir = WEIGHTS_ROOT / hold.replace(".csv", "")
        ckpt = wdir / "avnet_tiny.pt"
        if not args.skip_train or not ckpt.is_file():
            print(f"\n=== TRAIN exclude={hold} -> {wdir} ===")
            n_win = args.n_windows if args.n_windows > 0 else 10**9
            metrics = train(
                epochs=args.epochs,
                batch_size=128,
                n_windows=n_win,
                seed=7,
                device_name=args.device,
                source="io-vnbd",
                exclude_names={hold},
                weights_dir=wdir,
            )
            train_meta.append(
                {
                    "exclude": hold,
                    "rmse_speed_mps": metrics.get("rmse_speed_mps"),
                    "rmse_yaw_rate_dps": metrics.get("rmse_yaw_rate_dps"),
                    "n_train": metrics.get("n_train"),
                    "ckpt": str(ckpt),
                }
            )
        else:
            print(f"\n=== SKIP TRAIN (reuse {ckpt}) ===")
            train_meta.append({"exclude": hold, "ckpt": str(ckpt), "reused": True})

        data = load_smartphone_csv(path)
        t = data["t_s"]
        mid = float(t[0] + 0.45 * (t[-1] - t[0]))
        i0 = int(np.searchsorted(t, mid))
        print(f"=== EVAL {hold} with LFO weights ===")
        try:
            r = run_hardened_outage(
                data, deny_s=60.0, start_idx=i0, t0_s=30.0, avnet_weights=ckpt
            )
        except Exception as exc:  # noqa: BLE001
            rows.append({"file": hold, "error": str(exc)})
            continue
        for method, sc in r["scores"].items():
            v = verdict(sc, deny_s=r["deny_s"])
            row = {
                "file": hold,
                "method": method,
                "final_error_m": round(sc["final_error_m"], 2),
                "drift_pct": round(sc["drift_pct"], 2),
                "m_per_km": round(sc["m_per_km"], 2),
                "distance_m": round(sc["distance_m"], 2),
                "speed0_mps": round(r["speed0_mps"], 2),
                "verdict": v,
                "protocol": "leave_file_out",
            }
            rows.append(row)
            if method.startswith("avnet") or "arclength" in method:
                print(
                    f"{hold:8s} {method:18s} final={sc['final_error_m']:7.1f} m  "
                    f"drift={sc['drift_pct']:6.1f}%  {v}"
                )

    out_json = OUT / "report.json"
    out_json.write_text(
        json.dumps({"train": train_meta, "rows": rows}, indent=2),
        encoding="utf-8",
    )

    focus = [
        "car_bias",
        "avnet_speed",
        "avnet_full",
        "avnet_speed_map",
        "hold_arclength",
        "avnet_arclength",
    ]
    lines = [
        "# Leave-file-out closed-loop (60 s mid-route)",
        "",
        "Each eval CSV was **excluded** from AVNet training. Arc-length rows are",
        "known-route product mode (cross-track killed); free-DR rows are the hard bar.",
        "",
        "| File | Method | Final m | Drift % | m/km | Verdict |",
        "|---|---|---:|---:|---:|---|",
    ]
    for row in rows:
        if "error" in row:
            lines.append(f"| {row['file']} | ERROR | — | — | — | {row['error']} |")
            continue
        if row["method"] not in focus and not row["method"].startswith("avnet"):
            continue
        if row["method"] not in focus:
            continue
        lines.append(
            f"| {row['file']} | `{row['method']}` | {row['final_error_m']} | "
            f"{row['drift_pct']} | {row['m_per_km']} | **{row['verdict']}** |"
        )
    av = [r for r in rows if str(r.get("method", "")).startswith("avnet")]
    arc = [r for r in rows if "arclength" in str(r.get("method", ""))]
    isro_av = sum(1 for r in av if r.get("verdict") == "PASS_ISRO")
    isro_arc = sum(1 for r in arc if r.get("verdict") == "PASS_ISRO")
    lines += [
        "",
        f"AVNet-family: {len(av)} rows · PASS_ISRO={isro_av}",
        f"Arclength-family: {len(arc)} rows · PASS_ISRO={isro_arc}",
        "",
        "**Honesty:** leave-file-out prevents train leakage. "
        "`*_arclength` assumes a known corridor graph (fleet/OSM) — label separately.",
    ]
    (OUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nwrote {out_json}")
    print(f"wrote {OUT / 'summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
