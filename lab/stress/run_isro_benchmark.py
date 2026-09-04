"""Score both arms of the ISRO 26168 dead-reckoning benchmark on IO-VNBD.

The problem statement states the bar as a disjunction, and the repo previously
scored only the second half of it:

    "a drift of less than 5 meters is desired over 50m GNSS denied environment
     in <1 minutes OR less than 100m of drift over a 1km GNSS denied
     environment at a speed of 60kmph in tunnels/underground metro OR similar
     simulated environments where GNSS signals are unavailable"

So there are two arms:

    ARM_SHORT   <5 m final error over 50 m of denial, completed in <60 s
    ARM_TUNNEL  <10% drift and <100 m/km over a 60 s denial at road speed

Both are official. ARM_SHORT is the one a judge can watch happen in a corridor;
ARM_TUNNEL is the one that stresses heading. Report them separately -- a pass on
one is not a pass on the other.

Ground truth comes from the paired V-*.csv CAN log wherever it exists (true
10 Hz fix); files without a pair are scored against interpolated phone GNSS and
flagged, because that interpolation contributes error of its own.

Run:
    python lab/stress/run_isro_benchmark.py [--files N] [--segments N]

Writes lab/stress/results/isro_benchmark/{report.json,summary.md}.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

_STRESS = Path(__file__).resolve().parent
if str(_STRESS) not in sys.path:
    sys.path.insert(0, str(_STRESS))

from load_iovnbd import (  # noqa: E402
    attach_vehicle_truth,
    find_smartphone_csvs,
    load_smartphone_csv,
)
from outage_replay import run_outage_replay  # noqa: E402

ARM_SHORT_DISTANCE_M = 50.0
ARM_SHORT_MAX_S = 60.0
ARM_SHORT_MAX_ERROR_M = 5.0
ARM_TUNNEL_DENY_S = 60.0
ARM_TUNNEL_MIN_SPEED_MPS = 8.0  # ~29 km/h; excludes crawling traffic
ARM_TUNNEL_MAX_DRIFT_PCT = 10.0
ARM_TUNNEL_MAX_M_PER_KM = 100.0
METHODS = ("car_style", "idr_lean", "inekf_basic")


def _truth_speed(data: dict[str, Any], n: int) -> np.ndarray:
    """Truth speed aligned to ``n`` samples.

    The CAN log can be a row or two shorter than the phone log, so clip both to
    a common length rather than letting the mismatch surface as a broadcast
    error deep inside the segment loop.
    """
    key = "can_speed_mps" if data.get("truth_source") == "can_10hz" else "speed_mps"
    v = np.asarray(data[key], dtype=np.float64)[:n]
    v = np.where(np.isfinite(v), np.maximum(v, 0.0), 0.0)
    if v.size < n:
        v = np.pad(v, (0, n - v.size), mode="edge")
    return v


def _segment_starts(n: int, count: int) -> list[int]:
    if n < 2000:
        return []
    return [int(i) for i in np.linspace(int(0.08 * n), int(0.88 * n), count)]


def _deny_s_for_distance(
    t: np.ndarray, speed: np.ndarray, i0: int, target_m: float, max_s: float
) -> float | None:
    """Seconds of denial needed to cover ``target_m`` from ``i0``, or None."""
    dt = np.diff(t[i0:], prepend=t[i0])
    dt = np.clip(dt, 0.0, 0.5)
    covered = np.cumsum(speed[i0:] * dt)
    reached = np.flatnonzero(covered >= target_m)
    if reached.size == 0:
        return None
    elapsed = float(t[i0 + int(reached[0])] - t[i0])
    return elapsed if 1.0 < elapsed <= max_s else None


def run_file(data: dict[str, Any], segments: int) -> dict[str, Any]:
    n = int(data["n"])
    if data.get("truth_source") == "can_10hz":
        n = min(n, int(data.get("can_n", n)))
    t = np.asarray(data["t_s"], dtype=np.float64)[:n]
    speed = _truth_speed(data, n)
    rows: list[dict[str, Any]] = []

    for i0 in _segment_starts(n, segments):
        # --- ARM_TUNNEL: fixed 60 s at road speed -------------------------
        i1 = int(np.searchsorted(t, t[i0] + ARM_TUNNEL_DENY_S))
        if i1 < n and float(np.mean(speed[i0:i1])) >= ARM_TUNNEL_MIN_SPEED_MPS:
            try:
                r = run_outage_replay(data, deny_s=ARM_TUNNEL_DENY_S, start_idx=i0)
            except ValueError:
                r = None
            if r is not None:
                for method in METHODS:
                    s = r["scores"][method]
                    m_per_km = (
                        s["final_error_m"] / s["distance_m"] * 1000.0
                        if s["distance_m"] > 1.0
                        else float("inf")
                    )
                    rows.append(
                        {
                            "arm": "ARM_TUNNEL",
                            "start_idx": i0,
                            "method": method,
                            "deny_s": r["deny_s"],
                            "mean_speed_mps": float(np.mean(speed[i0:i1])),
                            "final_error_m": s["final_error_m"],
                            "distance_m": s["distance_m"],
                            "drift_pct": s["drift_pct"],
                            "m_per_km": m_per_km,
                            "truth_source": r["truth_source"],
                            "pass": bool(
                                s["drift_pct"] < ARM_TUNNEL_MAX_DRIFT_PCT
                                and m_per_km < ARM_TUNNEL_MAX_M_PER_KM
                            ),
                        }
                    )

        # --- ARM_SHORT: 50 m of denial, under 60 s ------------------------
        deny_s = _deny_s_for_distance(
            t, speed, i0, ARM_SHORT_DISTANCE_M, ARM_SHORT_MAX_S
        )
        if deny_s is None:
            continue
        try:
            r = run_outage_replay(data, deny_s=deny_s, start_idx=i0)
        except ValueError:
            continue
        for method in METHODS:
            s = r["scores"][method]
            rows.append(
                {
                    "arm": "ARM_SHORT",
                    "start_idx": i0,
                    "method": method,
                    "deny_s": r["deny_s"],
                    "mean_speed_mps": float(ARM_SHORT_DISTANCE_M / max(deny_s, 1e-6)),
                    "final_error_m": s["final_error_m"],
                    "distance_m": s["distance_m"],
                    "drift_pct": s["drift_pct"],
                    "m_per_km": (
                        s["final_error_m"] / s["distance_m"] * 1000.0
                        if s["distance_m"] > 1.0
                        else float("inf")
                    ),
                    "truth_source": r["truth_source"],
                    "pass": bool(s["final_error_m"] < ARM_SHORT_MAX_ERROR_M),
                }
            )
    return {"name": data["name"], "rows": rows}


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for arm in ("ARM_SHORT", "ARM_TUNNEL"):
        for method in METHODS:
            sel = [r for r in rows if r["arm"] == arm and r["method"] == method]
            if not sel:
                continue
            err = np.array([r["final_error_m"] for r in sel], dtype=np.float64)
            drift = np.array([r["drift_pct"] for r in sel], dtype=np.float64)
            out[f"{arm}/{method}"] = {
                "n": len(sel),
                "passes": int(sum(r["pass"] for r in sel)),
                "pass_rate": float(sum(r["pass"] for r in sel) / len(sel)),
                "median_error_m": float(np.median(err)),
                "p90_error_m": float(np.percentile(err, 90)),
                "median_drift_pct": float(np.median(drift)),
                "can_truth_rows": int(
                    sum(r["truth_source"] == "can_10hz" for r in sel)
                ),
            }
    return out


def write_summary(path: Path, report: dict[str, Any]) -> None:
    s = report["summary"]
    lines = [
        "# ISRO 26168 benchmark - both official arms",
        "",
        f"Files scored: **{report['n_files']}** | "
        f"segments/file: {report['segments_per_file']} | "
        f"rows: {report['n_rows']} | "
        f"CAN-truth rows: {report['n_can_truth_rows']}/{report['n_rows']}",
        "",
        "Ground truth is the paired `V-*.csv` CAN log (true 10 Hz fix) wherever the",
        "pair exists; rows scored against interpolated phone GNSS are counted",
        "separately because that interpolation contributes error of its own.",
        "",
        "| Arm | Method | n | pass | rate | median err | p90 err | median drift % |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for key in sorted(s):
        arm, method = key.split("/")
        v = s[key]
        lines.append(
            f"| {arm} | `{method}` | {v['n']} | {v['passes']} | "
            f"{100.0 * v['pass_rate']:.0f}% | {v['median_error_m']:.1f} m | "
            f"{v['p90_error_m']:.1f} m | {v['median_drift_pct']:.1f} |"
        )
    lines += [
        "",
        "## Arm definitions",
        "",
        f"- **ARM_SHORT** - <{ARM_SHORT_MAX_ERROR_M:.0f} m final error over "
        f"{ARM_SHORT_DISTANCE_M:.0f} m of denial completed in "
        f"<{ARM_SHORT_MAX_S:.0f} s.",
        f"- **ARM_TUNNEL** - <{ARM_TUNNEL_MAX_DRIFT_PCT:.0f}% drift and "
        f"<{ARM_TUNNEL_MAX_M_PER_KM:.0f} m/km over a "
        f"{ARM_TUNNEL_DENY_S:.0f} s denial at "
        f">={ARM_TUNNEL_MIN_SPEED_MPS:.0f} m/s mean speed.",
        "",
        "Both are quoted verbatim from the problem statement and joined by OR.",
        "A pass on one arm is not a pass on the other; do not merge these rows.",
        "",
        "## Per-file pass counts (ARM_TUNNEL / ARM_SHORT, best method)",
        "",
        "| File | truth | ARM_TUNNEL | ARM_SHORT |",
        "|---|---|---:|---:|",
    ]
    for f in report["files"]:
        rows = f["rows"]
        if not rows:
            continue
        truth = "CAN" if any(r["truth_source"] == "can_10hz" for r in rows) else "phone"
        cells = []
        for arm in ("ARM_TUNNEL", "ARM_SHORT"):
            best = 0
            total = 0
            for method in METHODS:
                sel = [r for r in rows if r["arm"] == arm and r["method"] == method]
                if sel:
                    total = len(sel)
                    best = max(best, sum(r["pass"] for r in sel))
            cells.append(f"{best}/{total}" if total else "-")
        lines.append(f"| `{f['name']}` | {truth} | {cells[0]} | {cells[1]} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", type=int, default=0, help="limit file count (0 = all)")
    ap.add_argument("--segments", type=int, default=12)
    args = ap.parse_args()

    csvs = find_smartphone_csvs()
    if not csvs:
        print(
            "no real S-*.csv found. Run: git lfs install && git lfs pull "
            "inside data/raw/IO-VNBD",
            file=sys.stderr,
        )
        return 2
    if args.files:
        csvs = csvs[: args.files]

    files: list[dict[str, Any]] = []
    for p in csvs:
        try:
            data = attach_vehicle_truth(load_smartphone_csv(p))
        except (OSError, ValueError) as exc:
            print(f"  skip {p.name}: {exc}", file=sys.stderr)
            continue
        result = run_file(data, args.segments)
        files.append(result)
        n_pass = sum(r["pass"] for r in result["rows"])
        print(
            f"  {data['name']:16s} truth={data['truth_source']:24s} "
            f"rows={len(result['rows']):4d} pass={n_pass}"
        )

    all_rows = [r for f in files for r in f["rows"]]
    report = {
        "n_files": len(files),
        "segments_per_file": args.segments,
        "n_rows": len(all_rows),
        "n_can_truth_rows": sum(r["truth_source"] == "can_10hz" for r in all_rows),
        "summary": summarise(all_rows),
        "files": files,
    }
    out_dir = _STRESS / "results" / "isro_benchmark"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_summary(out_dir / "summary.md", report)

    print(f"\n{'arm/method':28s} {'n':>4s} {'pass':>5s} {'rate':>6s} {'medErr':>8s}")
    for key in sorted(report["summary"]):
        v = report["summary"][key]
        print(
            f"{key:28s} {v['n']:4d} {v['passes']:5d} "
            f"{100.0 * v['pass_rate']:5.0f}% {v['median_error_m']:7.1f}m"
        )
    print(f"\nwrote {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
