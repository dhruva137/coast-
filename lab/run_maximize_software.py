"""Maximize SIH26168 software path on local GPU (or CPU fallback).

Runs, in order:
  1) AVNet-tiny train on real IO-VNBD (CUDA auto)
  2) Proposal / IO-VNBD position figures
  3) Research F1–F12 sandbox (if present)
  4) Prototype product gate

Usage (repo root)::

    python lab/run_maximize_software.py
    python lab/run_maximize_software.py --epochs 60 --skip-research
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LAB = Path(__file__).resolve().parent
OUT = LAB / "maximize_results"
PY = sys.executable


def _run(cmd: list[str], *, cwd: Path | None = None) -> dict:
    t0 = time.perf_counter()
    print("\n===", " ".join(cmd), flush=True)
    p = subprocess.run(cmd, cwd=str(cwd or REPO), capture_output=False)
    dt = time.perf_counter() - t0
    row = {"cmd": cmd, "returncode": p.returncode, "seconds": round(dt, 2)}
    print(f"--- exit {p.returncode} in {dt:.1f}s", flush=True)
    return row


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--n-windows", type=int, default=0, help="0 = use up to 50k real windows")
    ap.add_argument("--skip-research", action="store_true")
    ap.add_argument("--skip-gate", action="store_true")
    args = ap.parse_args(argv)

    OUT.mkdir(parents=True, exist_ok=True)
    n_win = args.n_windows if args.n_windows > 0 else 50000
    results: list[dict] = []

    # 1) GPU train on real IO-VNBD
    results.append(
        _run(
            [
                PY,
                str(LAB / "models" / "train_avnet.py"),
                "--device",
                "auto",
                "--source",
                "io-vnbd",
                "--epochs",
                str(args.epochs),
                "--batch-size",
                str(args.batch_size),
                "--n-windows",
                str(n_win),
            ]
        )
    )

    # 2) Proposal figures + IO-VNBD plots
    results.append(_run([PY, str(LAB / "eval" / "iovnbd_plots.py")]))
    results.append(_run([PY, str(LAB / "eval" / "proposal_figures.py")]))

    # 3) Optional research suite
    if not args.skip_research:
        run_all = LAB / "research" / "run_all.py"
        if run_all.is_file():
            results.append(_run([PY, str(run_all)]))

    # 4) Prototype gate (honest; may still be research-pass only)
    if not args.skip_gate:
        gate = LAB / "stress" / "product_gate.py"
        if gate.is_file():
            results.append(_run([PY, str(gate), "--level", "prototype"]))

    summary = {
        "steps": results,
        "weights": str(LAB / "models" / "weights" / "avnet_tiny.pt"),
        "metrics": str(LAB / "models" / "weights" / "metrics.json"),
        "figures": str(LAB / "eval" / "figures"),
        "all_ok": all(r["returncode"] == 0 for r in results),
    }
    metrics_path = LAB / "models" / "weights" / "metrics.json"
    if metrics_path.is_file():
        try:
            summary["train_metrics"] = json.loads(metrics_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    out_path = OUT / "maximize_summary.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}  all_ok={summary['all_ok']}")
    return 0 if summary["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
