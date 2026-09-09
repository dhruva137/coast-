"""Dataset stress harness — free-DR (+ map-in-loop when OSM covers the track).

Block 4 induction: score an independent dataset via a column adapter and write
``lab/stress/results/dataset_stress/<name>/{summary.md,error_cdf.png,report.json}``.

Usage
-----
::

    python lab/stress/run_dataset_stress.py lab/eval/fixtures/dataset_stress_synthetic \\
        --adapter synthetic

    python lab/stress/run_dataset_stress.py data/field/motorcycle_kaggle \\
        --adapter iovnbd

Data logistics
--------------
The pipeline is **local**. Manager downloads one public set, drops it under
``data/field/<name>/``, and this script scores it. Do **not** fork into a
Kaggle notebook (see ``lab/eval/adapters/README.md`` and
``final_demo_pitch/FIELD_DATASETS.md``).

Honesty
-------
Map-in-loop needs an **independent OSM graph** covering the track
(``maps/graphs/iovnbd_midlands.graph.npz`` today). Synthetic fixtures and
out-of-bbox field logs are scored as **free-DR only** — we do not invent a
map-aided number.
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
_LAB = _STRESS.parent
_REPO = _LAB.parent
for _p in (_REPO, _LAB, _LAB / "eval", _LAB / "baselines", _LAB / "nav", _STRESS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from lab.eval.adapters import get_adapter  # noqa: E402
from lab.eval.adapters.base import SessionArrays  # noqa: E402
from lab.eval.metrics import (  # noqa: E402
    ate,
    drift_pct,
    error_cdf,
    jsonable,
    lla_to_enu,
    path_length,
    position_errors,
)
from lab.eval.plots import plot_error_cdf  # noqa: E402

try:
    from car_style import integrate_heading_speed, wrap_pi  # noqa: E402
except ImportError:
    from baselines.car_style import integrate_heading_speed, wrap_pi  # type: ignore  # noqa: E402

EARTH_R_M = 6_371_008.8
ISRO_DRIFT_BAR_PCT = 10.0
DEFAULT_GRAPH = _REPO / "maps" / "graphs" / "iovnbd_midlands.graph.npz"
SEED = 26168


def _bearing_to_yaw_rad(bearing_deg: float) -> float:
    if not np.isfinite(bearing_deg):
        return 0.0
    b = float(bearing_deg)
    if abs(b) > 2.0 * math.pi + 0.5:
        return math.radians(b)
    return b


def _fill_speed(speed: np.ndarray) -> np.ndarray:
    s = np.asarray(speed, dtype=np.float64).copy()
    last = 0.0
    for i in range(s.size):
        if np.isfinite(s[i]) and s[i] >= 0.0:
            last = float(s[i])
        else:
            s[i] = last
    return s


def free_dr_track(session: SessionArrays) -> dict[str, Any]:
    """Heading+speed free-DR: ψ̇ = gz, speed from GPS (held across gaps)."""
    t = session.t_s
    speed = _fill_speed(session.speed)
    # Seed yaw from first finite bearing, else from GNSS chord.
    yaw0 = 0.0
    for b in session.bearing_deg:
        if np.isfinite(b):
            yaw0 = _bearing_to_yaw_rad(float(b))
            break
    else:
        gt = lla_to_enu(session.lat, session.lon)
        if len(gt) >= 2:
            d = gt[min(5, len(gt) - 1)] - gt[0]
            if np.linalg.norm(d) > 0.5:
                yaw0 = float(math.atan2(d[0], d[1]))

    dt = np.zeros_like(t)
    if t.size > 1:
        dt[1:] = np.diff(t)
        dt[dt < 0] = 0.0
        dt[dt > 1.0] = 0.0

    x, y, yaw = integrate_heading_speed(
        dt, speed, session.gz, x0=0.0, y0=0.0, yaw0=yaw0
    )
    est = np.column_stack([x, y])
    gt = lla_to_enu(session.lat, session.lon)
    # Align start: free-DR already at origin; GT also origin at first fix.
    errs = position_errors(est, gt)
    final_m = float(errs[-1]) if errs.size else float("inf")
    dist = path_length(gt)
    return {
        "est_xy": est,
        "gt_xy": gt,
        "yaw": yaw,
        "errors_m": errs,
        "final_m": final_m,
        "ate_m": ate(est, gt),
        "distance_m": dist,
        "drift_pct": drift_pct(final_m, dist),
        "error_cdf": error_cdf(errs),
        "pass_isro_drift": bool(
            np.isfinite(final_m) and dist >= 1.0 and drift_pct(final_m, dist) < ISRO_DRIFT_BAR_PCT
        ),
    }


def _try_load_graph(graph_path: Path):
    if not graph_path.is_file():
        return None, f"OSM graph not found at {graph_path}"
    try:
        from mapmatch import MapGraph  # noqa: WPS433
    except ImportError:
        try:
            from lab.nav.mapmatch import MapGraph  # type: ignore  # noqa: WPS433
        except ImportError as exc:
            return None, f"mapmatch import failed: {exc}"
    try:
        graph = MapGraph.load(graph_path)
    except Exception as exc:  # noqa: BLE001
        return None, f"failed to load OSM graph: {exc}"
    meta = getattr(graph, "meta", {}) or {}
    if meta.get("built_from_drive_data") is True:
        return None, "refusing graph built_from_drive_data=true (not independent OSM)"
    return graph, None


def _in_graph_bbox(session: SessionArrays, graph) -> bool:
    m = getattr(graph, "meta", {}) or {}
    lat = float(np.nanmedian(session.lat))
    lon = float(np.nanmedian(session.lon))
    return (
        float(m.get("bbox_lat_min", -90.0)) <= lat <= float(m.get("bbox_lat_max", 90.0))
        and float(m.get("bbox_lon_min", -180.0)) <= lon <= float(m.get("bbox_lon_max", 180.0))
    )


def _enu_to_lla(xy: np.ndarray, lat0: float, lon0: float) -> tuple[np.ndarray, np.ndarray]:
    lat = lat0 + np.degrees(xy[:, 1] / EARTH_R_M)
    lon = lon0 + np.degrees(xy[:, 0] / (EARTH_R_M * math.cos(math.radians(lat0))))
    return lat, lon


def try_map_in_loop(
    session: SessionArrays,
    free: dict[str, Any],
    graph_path: Path,
) -> dict[str, Any]:
    """Snap free-DR through independent OSM HMM match when coverage allows."""
    graph, err = _try_load_graph(graph_path)
    if graph is None:
        return {
            "ran": False,
            "reason": err or "no graph",
            "honesty": (
                "Map-in-loop skipped — free-DR-only metrics below are the "
                "honest result for this dataset_dir."
            ),
        }
    if not _in_graph_bbox(session, graph):
        return {
            "ran": False,
            "reason": (
                f"track median lat/lon outside OSM graph bbox "
                f"({graph_path.name})"
            ),
            "honesty": (
                "Map-in-loop skipped (no OSM coverage). Reporting free-DR only — "
                "do not invent a map-aided number."
            ),
            "graph": str(graph_path),
        }

    try:
        from mapmatch import match  # noqa: WPS433
    except ImportError:
        from lab.nav.mapmatch import match  # type: ignore  # noqa: WPS433

    est = free["est_xy"]
    lat0 = float(session.lat[np.isfinite(session.lat)][0])
    lon0 = float(session.lon[np.isfinite(session.lon)][0])
    # Decimate to ~1 Hz for matcher.
    step = max(1, int(round(session.hz / 1.0)) if np.isfinite(session.hz) else 10)
    idx = np.arange(0, len(est), step)
    if idx[-1] != len(est) - 1:
        idx = np.append(idx, len(est) - 1)
    lat_dr, lon_dr = _enu_to_lla(est[idx], lat0, lon0)
    try:
        # mapmatch.match(lat, lon, graph) → MatchResult
        matched = match(lat_dr, lon_dr, graph)
    except Exception as exc:  # noqa: BLE001
        return {
            "ran": False,
            "reason": f"mapmatch failed: {exc}",
            "honesty": "Map-in-loop failed at match time; free-DR-only metrics stand.",
            "graph": str(graph_path),
        }

    m_lat = np.asarray(getattr(matched, "lat"), dtype=np.float64)
    m_lon = np.asarray(getattr(matched, "lon"), dtype=np.float64)

    map_xy = lla_to_enu(m_lat, m_lon, lat0, lon0)
    # Upsample matched points back onto free-DR timeline by nearest decimated index.
    full = np.zeros_like(est)
    for j, i in enumerate(idx):
        full[i] = map_xy[min(j, len(map_xy) - 1)]
    # Linear fill between decimated anchors.
    for k in range(len(idx) - 1):
        i0, i1 = int(idx[k]), int(idx[k + 1])
        if i1 <= i0:
            continue
        for i in range(i0 + 1, i1):
            a = (i - i0) / (i1 - i0)
            full[i] = (1 - a) * full[i0] + a * full[i1]

    gt = free["gt_xy"]
    # Align lengths for scoring on decimated + interpolated track.
    errs = position_errors(full, gt)
    final_m = float(errs[-1]) if errs.size else float("inf")
    dist = free["distance_m"]
    return {
        "ran": True,
        "reason": "OSM HMM mapmatch on free-DR track",
        "graph": str(graph_path),
        "est_xy": full,
        "errors_m": errs,
        "final_m": final_m,
        "ate_m": ate(full, gt),
        "drift_pct": drift_pct(final_m, dist),
        "error_cdf": error_cdf(errs),
        "pass_isro_drift": bool(
            np.isfinite(final_m) and dist >= 1.0 and drift_pct(final_m, dist) < ISRO_DRIFT_BAR_PCT
        ),
        "honesty": (
            "Map-in-loop used independent OSM graph "
            f"({graph_path.name}); built_from_drive_data must remain false."
        ),
    }


def score_session(
    session: SessionArrays,
    *,
    graph_path: Path,
) -> dict[str, Any]:
    free = free_dr_track(session)
    mapped = try_map_in_loop(session, free, graph_path)
    row: dict[str, Any] = {
        "name": session.name,
        "source": session.source_path,
        "n": session.n,
        "hz": session.hz,
        "distance_m": free["distance_m"],
        "free_dr": {
            "final_m": free["final_m"],
            "ate_m": free["ate_m"],
            "drift_pct": free["drift_pct"],
            "error_cdf": free["error_cdf"],
            "pass_isro_drift": free["pass_isro_drift"],
        },
        "map_in_loop": {
            k: v
            for k, v in mapped.items()
            if k not in ("est_xy", "errors_m")
        },
        "meta": session.meta,
        # Keep arrays for plotting (stripped before JSON).
        "_free_errors": free["errors_m"],
        "_map_errors": mapped.get("errors_m"),
        "_map_ran": bool(mapped.get("ran")),
    }
    return row


def write_summary(
    out_dir: Path,
    *,
    adapter_name: str,
    dataset_dir: Path,
    rows: list[dict[str, Any]],
    graph_path: Path,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    map_any = any(r.get("_map_ran") for r in rows)
    fixture = any(r.get("meta", {}).get("fixture") for r in rows)

    lines: list[str] = [
        f"# Dataset stress — `{out_dir.name}`",
        "",
        f"- Adapter: `{adapter_name}`",
        f"- Dataset dir: `{dataset_dir}`",
        f"- Sessions scored: **{len(rows)}**",
        f"- Seed: `{SEED}`",
        f"- OSM graph: `{graph_path}`",
        "",
    ]
    if fixture:
        lines += [
            "> **SYNTHETIC / FIXTURE** — not field proof. Manager drops real "
            "data under `data/field/`. Avoid Kaggle notebooks; score locally.",
            "",
        ]
    if not map_any:
        reasons = sorted(
            {
                str(r.get("map_in_loop", {}).get("reason", "n/a"))
                for r in rows
            }
        )
        lines += [
            "## Honesty — free-DR only",
            "",
            "Map-in-loop did **not** run on this dataset (no usable independent "
            "OSM coverage / graph). Metrics below are **free-DR only**. "
            "We are not inventing a map-aided improvement.",
            "",
            "Skip reasons:",
            "",
        ]
        for reason in reasons:
            lines.append(f"- {reason}")
        lines.append("")
    else:
        lines += [
            "## Methods",
            "",
            "- **free-DR** — heading+speed (`ψ̇ = g_z`, GPS speed hold)",
            "- **map-in-loop** — Newson–Krumm HMM against independent OSM graph",
            "",
        ]

    lines += [
        "## Per-session free-DR",
        "",
        "| session | n | dist_m | final_m | ate_m | drift% | CDF p50 | CDF p95 | ISRO <10% |",
        "|---|---:|---:|---:|---:|---:|---:|---:|:---:|",
    ]
    for r in rows:
        fd = r["free_dr"]
        cdf = fd.get("error_cdf") or {}
        lines.append(
            "| {name} | {n} | {dist:.1f} | {fin:.2f} | {ate:.2f} | {dr:.2f} | "
            "{p50:.2f} | {p95:.2f} | {ok} |".format(
                name=r["name"],
                n=r["n"],
                dist=r["distance_m"],
                fin=fd["final_m"],
                ate=fd["ate_m"],
                dr=fd["drift_pct"],
                p50=cdf.get("p50", float("nan")),
                p95=cdf.get("p95", float("nan")),
                ok="PASS" if fd["pass_isro_drift"] else "FAIL",
            )
        )

    if map_any:
        lines += [
            "",
            "## Per-session map-in-loop",
            "",
            "| session | final_m | ate_m | drift% | vs free-DR | ISRO <10% |",
            "|---|---:|---:|---:|---:|:---:|",
        ]
        for r in rows:
            mil = r["map_in_loop"]
            if not r.get("_map_ran"):
                lines.append(f"| {r['name']} | — | — | — | skipped | — |")
                continue
            free_d = r["free_dr"]["drift_pct"]
            map_d = mil["drift_pct"]
            ratio = free_d / map_d if map_d and map_d > 1e-9 else float("nan")
            lines.append(
                "| {name} | {fin:.2f} | {ate:.2f} | {dr:.2f} | {x:.2f}× | {ok} |".format(
                    name=r["name"],
                    fin=mil["final_m"],
                    ate=mil["ate_m"],
                    dr=map_d,
                    x=ratio,
                    ok="PASS" if mil.get("pass_isro_drift") else "FAIL",
                )
            )

    # Aggregate
    drifts = [r["free_dr"]["drift_pct"] for r in rows]
    finals = [r["free_dr"]["final_m"] for r in rows]
    passes = sum(1 for r in rows if r["free_dr"]["pass_isro_drift"])
    lines += [
        "",
        "## Aggregate (free-DR)",
        "",
        f"- median final error: **{float(np.median(finals)):.2f} m**",
        f"- median drift: **{float(np.median(drifts)):.2f} %**",
        f"- pass rate (ISRO drift < {ISRO_DRIFT_BAR_PCT:.0f}%): "
        f"**{passes}/{len(rows)}** ({100.0 * passes / max(len(rows), 1):.0f}%)",
        "",
        "## Figures",
        "",
        "- `error_cdf.png` — empirical CDF of free-DR position error",
        "",
        "## Logistics",
        "",
        "Drop real public datasets under `data/field/<name>/` and re-run with "
        "`--adapter iovnbd` (or a new adapter). See "
        "`lab/eval/adapters/README.md` and `final_demo_pitch/FIELD_DATASETS.md`. "
        "Do not fork scoring into a Kaggle notebook.",
        "",
    ]

    path = out_dir / "summary.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def run(
    dataset_dir: Path,
    *,
    adapter_name: str,
    out_name: str | None = None,
    graph_path: Path = DEFAULT_GRAPH,
) -> dict[str, Any]:
    adapter = get_adapter(adapter_name)
    sessions = adapter.load_all(dataset_dir)
    rows = [score_session(s, graph_path=graph_path) for s in sessions]

    name = out_name or Path(dataset_dir).name
    out_dir = _STRESS / "results" / "dataset_stress" / name
    out_dir.mkdir(parents=True, exist_ok=True)

    # CDF figure: concatenate free-DR errors.
    all_err = np.concatenate(
        [np.asarray(r["_free_errors"], dtype=np.float64) for r in rows]
    )
    cdf_path = out_dir / "error_cdf.png"
    plot_error_cdf(
        all_err,
        cdf_path,
        title=f"Free-DR position-error CDF — {name}",
    )

    summary_path = write_summary(
        out_dir,
        adapter_name=adapter_name,
        dataset_dir=dataset_dir,
        rows=rows,
        graph_path=graph_path,
    )

    report = {
        "adapter": adapter_name,
        "dataset_dir": str(Path(dataset_dir).resolve()),
        "out_dir": str(out_dir.resolve()),
        "graph": str(graph_path),
        "n_sessions": len(rows),
        "map_in_loop_ran": any(r.get("_map_ran") for r in rows),
        "sessions": [
            {k: v for k, v in r.items() if not k.startswith("_")}
            for r in rows
        ],
        "aggregate_free_dr": {
            "median_final_m": float(np.median([r["free_dr"]["final_m"] for r in rows])),
            "median_drift_pct": float(
                np.median([r["free_dr"]["drift_pct"] for r in rows])
            ),
            "pass_rate": sum(1 for r in rows if r["free_dr"]["pass_isro_drift"])
            / max(len(rows), 1),
        },
        "figures": {"error_cdf": str(cdf_path.resolve())},
        "summary_md": str(summary_path.resolve()),
    }
    (out_dir / "report.json").write_text(
        json.dumps(jsonable(report), indent=2), encoding="utf-8"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass

    p = argparse.ArgumentParser(
        description=(
            "Stress free-DR (+ map-in-loop if OSM covers) on a dataset dir "
            "via a column adapter."
        )
    )
    p.add_argument(
        "dataset_dir",
        type=Path,
        help="Directory of CSVs / session folders (manager drops under data/field/)",
    )
    p.add_argument(
        "--adapter",
        required=True,
        help="Adapter name: synthetic | iovnbd",
    )
    p.add_argument(
        "--name",
        default=None,
        help="Results folder name under lab/stress/results/dataset_stress/ "
        "(default: dataset_dir name)",
    )
    p.add_argument(
        "--graph",
        type=Path,
        default=DEFAULT_GRAPH,
        help="Independent OSM graph npz (map-in-loop skipped if missing/OOB)",
    )
    args = p.parse_args(argv)

    if not args.dataset_dir.is_dir():
        print(f"FATAL: dataset_dir not found: {args.dataset_dir}", file=sys.stderr)
        return 1

    try:
        report = run(
            args.dataset_dir,
            adapter_name=args.adapter,
            out_name=args.name,
            graph_path=args.graph,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"FATAL: {exc}", file=sys.stderr)
        return 1

    agg = report["aggregate_free_dr"]
    print("=" * 68)
    print(" COAST dataset stress")
    print("=" * 68)
    print(f" adapter:     {report['adapter']}")
    print(f" dataset:     {report['dataset_dir']}")
    print(f" sessions:    {report['n_sessions']}")
    print(f" map-in-loop: {'yes' if report['map_in_loop_ran'] else 'no (free-DR only)'}")
    print("-" * 68)
    print(f" median final_m:   {agg['median_final_m']:.3f}")
    print(f" median drift_%:   {agg['median_drift_pct']:.3f}")
    print(f" ISRO pass rate:   {100.0 * agg['pass_rate']:.0f}%")
    print("-" * 68)
    print(f" summary: {report['summary_md']}")
    print(f" cdf:     {report['figures']['error_cdf']}")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
