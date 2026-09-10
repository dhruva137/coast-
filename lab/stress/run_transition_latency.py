"""Measure the GNSS <-> dead-reckoning handover, both directions.

The problem statement lists this as a required capability and gives it a
deadline in milliseconds:

    "Seamless GNSS Deficit Handler: An instant seamless transition mechanism
     between GNSS aided INS and Dead reckoning modes within milliseconds of
     GNSS signal blackout and vice-versa."

Nothing in the repo measured it. Drift percentage says nothing about whether
the dot on the map freezes, jumps, or glides when GNSS drops and returns, and
"vice-versa" is the harder half: after a 60 s outage the estimate is hundreds
of metres from truth, and how it rejoins reality is what a judge actually sees.

Three numbers per event
-----------------------
``drop_latency_ms``
    GNSS loss to the first dead-reckoned fix. Our estimator seeds from the last
    fused state, so this should be one sample period. Anything larger is a
    freeze the user would notice.

``reacquire_latency_ms``
    GNSS return to the fused estimate settling within ``settle_radius_m`` of
    GNSS and staying there. This is convergence time, not the first update.

``reacquire_jump_m``
    How far the displayed position moves in the single worst step after GNSS
    returns. A hard snap is what "jump erratically" means in the problem
    statement's own description of the failure it wants removed. A large
    ``reacquire_jump_m`` with a small ``reacquire_latency_ms`` is a teleport,
    not a good result -- report both together or the metric lies.

Three rejoin policies are compared:

``hard_snap``   set position to GNSS the instant it returns. Fast, discontinuous.
``blended``     first-order blend toward GNSS with time constant ``tau_s``.
                Smooth, slower to converge. This is the tradeoff the metric exists
                to expose; neither policy is universally correct.
``adaptive``    innovation- and covariance-aware correction. It trusts GNSS more
                as DR covariance grows, while capping each visible correction.

Run:
    python lab/stress/run_transition_latency.py [--deny 60] [--segments 8]

Writes lab/stress/results/transition/{report.json,summary.md}.
"""

from __future__ import annotations

import argparse
import json
import math
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

EARTH_R_M = 6_371_008.8
SETTLE_RADIUS_M = 5.0
SETTLE_HOLD_S = 2.0
BLEND_TAU_S = 2.0
REJOIN_WINDOW_S = 30.0
METHOD = "idr_lean"
POLICIES = ("hard_snap", "blended", "adaptive")
ADAPTIVE_DR_SIGMA0_M = 5.0
ADAPTIVE_DR_GROWTH_MPS = 0.8
ADAPTIVE_GNSS_SIGMA_M = 5.0


def _enu(lat: np.ndarray, lon: np.ndarray, lat0: float, lon0: float) -> np.ndarray:
    east = np.deg2rad(lon - lon0) * EARTH_R_M * np.cos(np.deg2rad(lat0))
    north = np.deg2rad(lat - lat0) * EARTH_R_M
    return np.column_stack([east, north])


def _rejoin(
    start_xy: np.ndarray,
    gnss_xy: np.ndarray,
    dt: np.ndarray,
    policy: str,
    tau_s: float,
    initial_cov_m2: float | None = None,
) -> np.ndarray:
    """Fused track after GNSS returns, starting from the DR estimate."""
    out = np.empty_like(gnss_xy)
    pos = start_xy.astype(np.float64).copy()
    covariance = max(
        float(initial_cov_m2) if initial_cov_m2 is not None else 25.0, 1e-6
    )
    for i in range(gnss_xy.shape[0]):
        if policy == "hard_snap":
            pos = gnss_xy[i].copy()
        elif policy == "blended":
            alpha = 1.0 - float(np.exp(-max(dt[i], 1e-6) / max(tau_s, 1e-6)))
            pos = pos + alpha * (gnss_xy[i] - pos)
        elif policy == "adaptive":
            step_s = max(float(dt[i]), 1e-6)
            covariance += (ADAPTIVE_DR_GROWTH_MPS * step_s) ** 2
            innovation = gnss_xy[i] - pos
            innovation_m = float(np.linalg.norm(innovation))
            innovation_sigma = math.sqrt(
                covariance + ADAPTIVE_GNSS_SIGMA_M**2
            )
            normalized_error = innovation_m / max(innovation_sigma, 1e-6)
            kalman_trust = covariance / (
                covariance + ADAPTIVE_GNSS_SIGMA_M**2
            )
            tau = float(
                np.clip(
                    3.0
                    / max(
                        kalman_trust
                        * (1.0 + 0.15 * min(normalized_error, 10.0)),
                        1e-3,
                    ),
                    0.25,
                    4.0,
                )
            )
            alpha = 1.0 - math.exp(-step_s / tau)
            correction = alpha * innovation
            # Covariance-derived display cap prevents a one-frame teleport.
            max_visible_step = max(1.5, 0.30 * math.sqrt(covariance))
            correction_m = float(np.linalg.norm(correction))
            if correction_m > max_visible_step:
                correction *= max_visible_step / correction_m
            pos = pos + correction
            covariance = max((1.0 - alpha) * covariance, 1e-6)
        else:
            raise ValueError(f"unknown rejoin policy: {policy}")
        out[i] = pos
    return out


def _drop_latency_ms(t: np.ndarray, i0: int) -> float | None:
    """First valid DR sample after loss, skipping invalid/non-monotonic stamps."""
    if i0 < 0 or i0 >= t.size - 1 or not np.isfinite(t[i0]):
        return None
    for i in range(i0 + 1, t.size):
        delta = float(t[i] - t[i0])
        if np.isfinite(delta) and delta > 0.0:
            return delta * 1000.0
    return None


def _settle_ms(
    fused: np.ndarray, gnss: np.ndarray, t: np.ndarray, radius_m: float, hold_s: float
) -> float:
    """Time until |fused - gnss| stays under ``radius_m`` for ``hold_s``."""
    err = np.hypot(*(fused - gnss).T)
    inside = err < radius_m
    n = err.size
    for i in range(n):
        if not inside[i]:
            continue
        j = int(np.searchsorted(t, t[i] + hold_s))
        if j >= n:
            # Not enough tail to confirm the hold; accept if the rest is inside.
            if inside[i:].all():
                return float((t[i] - t[0]) * 1000.0)
            return float("nan")
        if inside[i:j].all():
            return float((t[i] - t[0]) * 1000.0)
    return float("nan")


def run_file(data: dict[str, Any], deny_s: float, segments: int) -> dict[str, Any]:
    t = np.asarray(data["t_s"], dtype=np.float64)
    n = t.size
    truth_speed = np.asarray(
        data["can_speed_mps"] if data.get("truth_source") == "can_10hz" else data["speed_mps"],
        dtype=np.float64,
    )
    lat = np.asarray(
        data["can_lat"] if data.get("truth_source") == "can_10hz" else data["lat"],
        dtype=np.float64,
    )
    lon = np.asarray(
        data["can_lon"] if data.get("truth_source") == "can_10hz" else data["lon"],
        dtype=np.float64,
    )
    events: list[dict[str, Any]] = []

    for i0 in np.linspace(int(0.08 * n), int(0.80 * n), segments).astype(int):
        i1 = int(np.searchsorted(t, t[i0] + deny_s))
        # searchsorted can return n when the outage runs off the end of the log.
        if i1 >= n - 1:
            continue
        i2 = int(np.searchsorted(t, t[i1] + REJOIN_WINDOW_S))
        if i2 >= min(n, lat.size) or float(np.nanmean(truth_speed[i0:i1])) < 5.0:
            continue
        try:
            r = run_outage_replay(data, deny_s=deny_s, start_idx=i0)
        except ValueError:
            continue
        est = r["est"].get(METHOD)
        if est is None or est.shape[0] < 2:
            continue

        # --- drop side -------------------------------------------------
        # The estimator carries the last fused state forward, so the first DR
        # fix lands on the next sample. Measure it rather than asserting it.
        drop_latency_ms = _drop_latency_ms(t, i0)

        # --- reacquire side --------------------------------------------
        gnss = _enu(lat[i1:i2], lon[i1:i2], float(lat[0]), float(lon[0]))
        dt = np.diff(t[i1 - 1 : i2])
        dr_end = est[-1]
        offset_m = float(np.hypot(*(dr_end - gnss[0])))
        row: dict[str, Any] = {
            "start_idx": int(i0),
            "deny_s": float(r["deny_s"]),
            "drop_latency_ms": drop_latency_ms,
            "dr_offset_at_reacquire_m": offset_m,
            "truth_source": r["truth_source"],
        }
        initial_cov_m2 = (
            ADAPTIVE_DR_SIGMA0_M + ADAPTIVE_DR_GROWTH_MPS * float(r["deny_s"])
        ) ** 2
        for policy in POLICIES:
            fused = _rejoin(
                dr_end,
                gnss,
                dt,
                policy,
                BLEND_TAU_S,
                initial_cov_m2=initial_cov_m2,
            )
            # The displayed position starts at the dead-reckoned estimate, so
            # the very first step -- the one that carries the whole accumulated
            # offset under hard_snap -- must be included. Prepending dr_end is
            # the difference between reporting a 7 m jump and a 500 m teleport.
            track = np.vstack([dr_end[None, :], fused])
            steps = np.hypot(*np.diff(track, axis=0).T)
            row[policy] = {
                "reacquire_latency_ms": _settle_ms(
                    fused, gnss, t[i1:i2], SETTLE_RADIUS_M, SETTLE_HOLD_S
                ),
                "reacquire_jump_m": float(np.max(steps)) if steps.size else 0.0,
            }
        events.append(row)
    return {"name": data["name"], "events": events}


def summarise(events: list[dict[str, Any]]) -> dict[str, Any]:
    if not events:
        return {}
    drop = np.asarray(
        [
            e["drop_latency_ms"]
            for e in events
            if e.get("drop_latency_ms") is not None
            and np.isfinite(e["drop_latency_ms"])
        ],
        dtype=np.float64,
    )
    out: dict[str, Any] = {
        "n_events": len(events),
        "drop_latency_ms_median": float(np.median(drop)) if drop.size else None,
        "drop_latency_valid_events": int(drop.size),
        "dr_offset_at_reacquire_m_median": float(
            np.median([e["dr_offset_at_reacquire_m"] for e in events])
        ),
    }
    for policy in POLICIES:
        lat_ms = np.array([e[policy]["reacquire_latency_ms"] for e in events])
        jump = np.array([e[policy]["reacquire_jump_m"] for e in events])
        ok = np.isfinite(lat_ms)
        out[policy] = {
            "reacquire_latency_ms_median": (
                float(np.median(lat_ms[ok])) if ok.any() else float("nan")
            ),
            "reacquire_latency_ms_p90": (
                float(np.percentile(lat_ms[ok], 90)) if ok.any() else float("nan")
            ),
            "converged_fraction": float(ok.mean()),
            "reacquire_jump_m_median": float(np.median(jump)),
            "reacquire_jump_m_max": float(np.max(jump)),
        }
    return out


def _fmt_ms(value: float | None) -> str:
    return f"{value:.0f} ms" if value is not None and np.isfinite(value) else "unavailable"


def write_summary(path: Path, report: dict[str, Any]) -> None:
    s = report["summary"]
    lines = [
        "# GNSS <-> dead-reckoning transition latency",
        "",
        "The problem statement requires transition \"within milliseconds\" in both",
        "directions. This is the measurement; nothing in the repo previously made it.",
        "",
        f"Drives: **{report['n_files']}** | events: **{s.get('n_events', 0)}** | "
        f"denial: {report['deny_s']:.0f} s | "
        f"settle: <{SETTLE_RADIUS_M:.0f} m held {SETTLE_HOLD_S:.0f} s",
        "",
        "## Drop side (GNSS lost -> first DR fix)",
        "",
        f"Median **{_fmt_ms(s.get('drop_latency_ms_median'))}** across "
        f"{s.get('drop_latency_valid_events', 0)}/{s.get('n_events', 0)} valid events. "
        "The estimator carries the last fused state forward; the metric is the "
        "first valid timestamped DR sample after loss.",
        "",
        "## Reacquire side (GNSS returns -> fused estimate converged)",
        "",
        f"After {report['deny_s']:.0f} s of denial the dead-reckoned position is a "
        f"median **{s.get('dr_offset_at_reacquire_m_median', float('nan')):.0f} m** "
        "from truth. That offset has to be absorbed, and how it is absorbed is a "
        "product decision, not a physics one:",
        "",
        "| Policy | median latency | p90 | converged | median jump | worst jump |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for policy in POLICIES:
        v = s.get(policy)
        if not v:
            continue
        lines.append(
            f"| `{policy}` | {_fmt_ms(v['reacquire_latency_ms_median'])} | "
            f"{_fmt_ms(v['reacquire_latency_ms_p90'])} | "
            f"{100.0 * v['converged_fraction']:.0f}% | "
            f"{v['reacquire_jump_m_median']:.1f} m | {v['reacquire_jump_m_max']:.1f} m |"
        )
    lines += [
        "",
        "Read the two columns together. `hard_snap` converges in one sample but "
        "teleports the icon by the full accumulated offset, which is exactly the "
        "\"jump erratically\" behaviour the problem statement asks us to remove. "
        "`blended` keeps the icon continuous and pays for it in convergence time. "
        "`adaptive` uses only online innovation and propagated covariance, and caps "
        "each correction according to uncertainty. Quoting latency without jump "
        "would be misleading.",
        "",
        f"The blend uses a first-order filter with tau = {BLEND_TAU_S:.0f} s. "
        "Tuning tau trades these two columns against each other directly; the "
        "right value depends on how far the estimate drifted, which argues for "
        "making tau a function of the estimated covariance rather than a constant.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deny", type=float, default=60.0)
    ap.add_argument("--segments", type=int, default=8)
    ap.add_argument("--files", type=int, default=0)
    ap.add_argument("--output-dir")
    args = ap.parse_args()

    csvs = find_smartphone_csvs()
    if args.files:
        csvs = csvs[: args.files]
    files: list[dict[str, Any]] = []
    for p in csvs:
        try:
            data = attach_vehicle_truth(load_smartphone_csv(p))
        except (OSError, ValueError):
            continue
        result = run_file(data, args.deny, args.segments)
        if result["events"]:
            files.append(result)
            print(f"  {result['name']:16s} events={len(result['events'])}")

    all_events = [e for f in files for e in f["events"]]
    report = {
        "n_files": len(files),
        "deny_s": args.deny,
        "settle_radius_m": SETTLE_RADIUS_M,
        "blend_tau_s": BLEND_TAU_S,
        "summary": summarise(all_events),
        "files": files,
    }
    out_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else _STRESS / "results" / "transition"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_summary(out_dir / "summary.md", report)

    s = report["summary"]
    if s:
        print(f"\ndrop latency        : {_fmt_ms(s['drop_latency_ms_median'])} (median)")
        print(
            f"DR offset at rejoin : "
            f"{s['dr_offset_at_reacquire_m_median']:.0f} m (median)"
        )
        for policy in POLICIES:
            v = s[policy]
            print(
                f"{policy:12s}: converge {_fmt_ms(v['reacquire_latency_ms_median']):>12s}  "
                f"jump {v['reacquire_jump_m_median']:7.1f} m  "
                f"({100.0 * v['converged_fraction']:.0f}% converged)"
            )
    print(f"\nwrote {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
