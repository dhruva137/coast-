"""
SIH26168 evaluation harness.

    python lab/eval/harness.py
    python lab/eval/harness.py --data data/synthetic
    python lab/eval/harness.py --no-plot

Reads CSV logs from ``data/synthetic/`` when that folder has files;
otherwise builds a deterministic in-memory leaning two-wheeler log
and scores the **car-style** integrator (ψ̇ = ω_z) against truth.
Writes ``lab/eval/last_report.json`` and, unless ``--no-plot``, the
three figures under ``lab/eval/figures/``.

Accepted CSV columns (any subset; aliases listed in ``COL``):

    t / t_s / t_ns
    x / east ,  y / north   or   lat , lon
    x_gt / east_gt , y_gt / north_gt
    yaw / yaw_est , yaw_gt
    lean / lean_est , lean_gt
    speed , gy , gz
    edge_pred / pred , edge_gt / truth / edge_id

A directory may also split the log::

    truth.csv  est.csv  imu.csv  gnss.csv  branches.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

_EVAL = Path(__file__).resolve().parent
_LAB = _EVAL.parent
_ROOT = _LAB.parent
_BASE = _LAB / "baselines"
for _p in (_EVAL, _BASE, _LAB):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from car_style import (  # noqa: E402
    SEED,
    car_style_yaw_rate,
    dt_from_t,
    integrate_heading_speed,
)
from metrics import (  # noqa: E402
    KITTI_LENGTHS_M,
    G,
    jsonable,
    lla_to_enu,
    summarize,
)
from plots import write_figures  # noqa: E402

REPORT_PATH = _EVAL / "last_report.json"
DEFAULT_DATA = _ROOT / "data" / "synthetic"

COL = {
    "t": ("t", "t_s", "time", "seconds"),
    "t_ns": ("t_ns", "timestamp_ns"),
    "x": ("x", "east", "e", "x_est", "east_est"),
    "y": ("y", "north", "n", "y_est", "north_est"),
    "x_gt": ("x_gt", "east_gt", "gt_x", "gt_east"),
    "y_gt": ("y_gt", "north_gt", "gt_y", "gt_north"),
    "lat": ("lat", "latitude"),
    "lon": ("lon", "longitude", "lng"),
    "lat_gt": ("lat_gt", "gt_lat"),
    "lon_gt": ("lon_gt", "gt_lon"),
    "yaw": ("yaw", "yaw_est", "heading", "psi"),
    "yaw_gt": ("yaw_gt", "gt_yaw", "heading_gt"),
    "lean": ("lean", "lean_est", "phi", "roll"),
    "lean_gt": ("lean_gt", "gt_lean", "phi_gt"),
    "speed": ("speed", "v", "speed_mps"),
    "gy": ("gy", "omega_y", "wy"),
    "gz": ("gz", "omega_z", "wz"),
    "gx": ("gx", "omega_x", "wx"),
    "ax": ("ax",),
    "ay": ("ay",),
    "az": ("az",),
    "edge_pred": ("edge_pred", "pred", "predicted", "branch_pred"),
    "edge_gt": ("edge_gt", "truth", "edge_id", "branch_truth"),
}


def _norm_header(name: str) -> str:
    return name.strip().lstrip("\ufeff").lower()


def _col(header: list[str], *keys: str) -> int | None:
    h = [_norm_header(c) for c in header]
    aliases: list[str] = []
    for k in keys:
        aliases.extend(COL.get(k, (k,)))
    for a in aliases:
        if a in h:
            return h.index(a)
    return None


def _read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        return [], []
    return rows[0], rows[1:]


def _fcol(rows: list[list[str]], idx: int | None) -> np.ndarray | None:
    if idx is None:
        return None
    out = np.empty(len(rows), dtype=np.float64)
    for i, row in enumerate(rows):
        try:
            out[i] = float(row[idx])
        except (IndexError, ValueError):
            out[i] = np.nan
    return out


def _scol(rows: list[list[str]], idx: int | None) -> list[str] | None:
    if idx is None:
        return None
    out: list[str] = []
    for row in rows:
        try:
            out.append(row[idx].strip())
        except IndexError:
            out.append("")
    return out


def _xy_from_table(header: list[str], rows: list[list[str]], gt: bool = False) -> np.ndarray | None:
    if gt:
        ix, iy = _col(header, "x_gt"), _col(header, "y_gt")
        ila, ilo = _col(header, "lat_gt"), _col(header, "lon_gt")
    else:
        ix, iy = _col(header, "x"), _col(header, "y")
        ila, ilo = _col(header, "lat"), _col(header, "lon")
        # A truth-only file uses x,y as GT; caller decides.
    if ix is not None and iy is not None:
        return np.column_stack([_fcol(rows, ix), _fcol(rows, iy)])
    if ila is not None and ilo is not None:
        return lla_to_enu(_fcol(rows, ila), _fcol(rows, ilo))
    return None


def _time_from_table(header: list[str], rows: list[list[str]]) -> np.ndarray:
    it = _col(header, "t")
    if it is not None:
        return _fcol(rows, it)
    ins = _col(header, "t_ns")
    if ins is not None:
        return _fcol(rows, ins) / 1e9
    return np.arange(len(rows), dtype=np.float64)


def load_csv_run(path: Path) -> dict | None:
    """
    Load one CSV or a directory of CSVs into the harness run dict.
    Returns None if nothing usable is found.
    """
    path = Path(path)
    files: list[Path] = []
    if path.is_file() and path.suffix.lower() == ".csv":
        files = [path]
    elif path.is_dir():
        files = sorted(path.glob("*.csv"))
    if not files:
        return None

    by_name = {p.stem.lower(): p for p in files}

    def take(*stems: str) -> tuple[list[str], list[list[str]]] | None:
        for s in stems:
            if s in by_name:
                return _read_csv(by_name[s])
        return None

    truth = take("truth", "gt", "ground_truth")
    est = take("est", "ours", "estimate", "pred")
    imu = take("imu")
    branches_file = take("branches", "junctions")
    # Fall back to the first CSV as a combined table.
    combined = _read_csv(files[0])

    src = truth or combined
    if src is None or not src[1]:
        return None
    th, trows = src
    t = _time_from_table(th, trows)
    gt_xy = _xy_from_table(th, trows, gt=True)
    if gt_xy is None:
        gt_xy = _xy_from_table(th, trows, gt=False)

    est_xy = None
    yaw_est = None
    if est is not None:
        eh, erows = est
        est_xy = _xy_from_table(eh, erows, gt=False)
        iy = _col(eh, "yaw")
        yaw_est = _fcol(erows, iy) if iy is not None else None
    if est_xy is None:
        est_xy = _xy_from_table(th, trows, gt=False)
        # If the same columns were already used as GT and there is no
        # dedicated estimate, try to rebuild car-style from IMU + speed.
        if imu is not None and _col(th, "x_gt") is None:
            ih, irows = imu
            gz = _fcol(irows, _col(ih, "gz"))
            speed = _fcol(trows, _col(th, "speed"))
            if speed is None:
                gh = take("gnss")
                if gh is not None:
                    speed = _fcol(gh[1], _col(gh[0], "speed"))
            if gz is not None and speed is not None:
                n = min(len(gz), len(speed), len(t))
                x0 = float(gt_xy[0, 0]) if gt_xy is not None and len(gt_xy) else 0.0
                y0 = float(gt_xy[0, 1]) if gt_xy is not None and len(gt_xy) else 0.0
                iy0 = _col(th, "yaw_gt") or _col(th, "yaw")
                yaw0 = float(_fcol(trows, iy0)[0]) if iy0 is not None else 0.0
                xe, ye, yeaw = integrate_heading_speed(
                    dt_from_t(t[:n]),
                    speed[:n],
                    car_style_yaw_rate(gz[:n]),
                    x0=x0,
                    y0=y0,
                    yaw0=yaw0,
                )
                est_xy = np.column_stack([xe, ye])
                yaw_est = yeaw

    if gt_xy is None and est_xy is None:
        return None
    if gt_xy is None:
        gt_xy = est_xy
    if est_xy is None:
        est_xy = gt_xy

    yaw_gt = _fcol(trows, _col(th, "yaw_gt") or _col(th, "yaw"))
    if yaw_est is None:
        yaw_est = _fcol(trows, _col(th, "yaw"))
    lean_est = _fcol(trows, _col(th, "lean"))
    lean_gt = _fcol(trows, _col(th, "lean_gt"))
    pred = _scol(trows, _col(th, "edge_pred"))
    truth_e = _scol(trows, _col(th, "edge_gt"))
    if branches_file is not None:
        bh, brows = branches_file
        pred = _scol(brows, _col(bh, "edge_pred") or _col(bh, "pred"))
        truth_e = _scol(brows, _col(bh, "edge_gt") or _col(bh, "truth"))

    return {
        "source": f"csv:{path}",
        "method": "log",
        "t": t,
        "gt_xy": gt_xy,
        "est_xy": est_xy,
        "yaw_gt": yaw_gt,
        "yaw_est": yaw_est,
        "lean_est": lean_est,
        "lean_gt": lean_gt,
        "branches": (pred, truth_e) if pred is not None and truth_e is not None else None,
        "seed": None,
    }


def generate_synthetic_run(
    *,
    seed: int = SEED,
    hz: float = 20.0,
    speed: float = 8.0,
    radius_m: float = 16.0,
    straight_m: float = 90.0,
    laps: int = 4,
) -> dict:
    """
    Tiny in-memory stadium: straight / coordinated-turn / straight / turn.

    Ground truth uses the true heading rate. The estimate is car-style
    (ψ̇ = ω_z) on the identical ``(dt, speed, gz)``. Branch labels are
    emitted at each apex: a 20° heading error flips the edge.
    """
    rng = np.random.default_rng(int(seed))
    dt = 1.0 / float(hz)
    v = float(speed)
    psi_dot = v / float(radius_m)
    phi = float(np.arctan2(v * psi_dot, G))
    turn_time = (np.pi * float(radius_m)) / v  # 180° stadium cap
    straight_time = float(straight_m) / v

    # Build a piecewise schedule: 0 = straight, +1 / −1 = turn direction.
    segs: list[tuple[float, float]] = []
    for _ in range(int(laps)):
        segs.append((straight_time, 0.0))
        segs.append((turn_time, 1.0))
        segs.append((straight_time, 0.0))
        segs.append((turn_time, -1.0))

    t0 = 0.0
    x = 0.0
    y = 0.0
    yaw = 0.0
    edge_i = 0
    t_list: list[float] = []
    x_list: list[float] = []
    y_list: list[float] = []
    yaw_list: list[float] = []
    gy_list: list[float] = []
    gz_list: list[float] = []
    lean_list: list[float] = []
    edge_gt: list[str] = []
    kind_list: list[int] = []

    for dur, turn in segs:
        n = max(1, int(round(dur / dt)))
        edge_i += 1
        eid = f"e{edge_i:02d}"
        for _k in range(n):
            signed = turn * psi_dot
            lean = phi if turn != 0.0 else 0.0
            gy = signed * np.sin(lean)
            gz = signed * np.cos(lean) if turn != 0.0 else 0.0
            t_list.append(t0)
            x_list.append(x)
            y_list.append(y)
            yaw_list.append(yaw)
            gy_list.append(float(gy))
            gz_list.append(float(gz))
            lean_list.append(float(lean))
            edge_gt.append(eid)
            kind_list.append(int(np.sign(turn)))
            x = x + v * np.sin(yaw) * dt
            y = y + v * np.cos(yaw) * dt
            yaw = float((yaw + signed * dt + np.pi) % (2.0 * np.pi) - np.pi)
            t0 += dt

    t = np.asarray(t_list, dtype=np.float64)
    gt_xy = np.column_stack(
        [np.asarray(x_list, dtype=np.float64), np.asarray(y_list, dtype=np.float64)]
    )
    yaw_gt = np.asarray(yaw_list, dtype=np.float64)
    speed_arr = np.full(len(t), v, dtype=np.float64)
    gy = np.asarray(gy_list, dtype=np.float64)
    gz = np.asarray(gz_list, dtype=np.float64)
    lean_gt = np.asarray(lean_list, dtype=np.float64)

    xe, ye, yaw_est = integrate_heading_speed(
        dt_from_t(t),
        speed_arr,
        car_style_yaw_rate(gz),
        x0=float(gt_xy[0, 0]),
        y0=float(gt_xy[0, 1]),
        yaw0=float(yaw_gt[0]),
    )
    est_xy = np.column_stack([xe, ye])

    # [F12] score only turn exits (the junctions). 10 deg heading error = miss.
    pred: list[str] = []
    truth_b: list[str] = []
    kinds = np.asarray(kind_list, dtype=np.int64)
    edges = np.asarray(edge_gt)
    for eid in dict.fromkeys(edge_gt):
        idx = np.flatnonzero(edges == eid)
        end = int(idx[-1])
        if kinds[end] == 0:
            continue
        heading_err = abs(float((yaw_est[end] - yaw_gt[end] + np.pi) % (2 * np.pi) - np.pi))
        truth_b.append(eid)
        pred.append(eid if heading_err < np.deg2rad(10.0) else f"{eid}_miss")

    # Lean-module probe: oracle + 0.6 deg Gaussian (seeded). Not a solver claim.
    lean_est = lean_gt + rng.normal(0.0, np.deg2rad(0.6), size=lean_gt.shape)

    return {
        "source": "synthetic-in-memory",
        "method": "car_style",
        "t": t,
        "gt_xy": gt_xy,
        "est_xy": est_xy,
        "yaw_gt": yaw_gt,
        "yaw_est": yaw_est,
        "lean_est": lean_est,
        "lean_gt": lean_gt,
        "branches": (pred, truth_b),
        "seed": int(seed),
        "note": (
            "in-memory stadium; estimate is car-style psi_dot=gz on the same IMU. "
            "lean_est is oracle+0.6 deg noise to exercise Lean RMSE, not a solver claim"
        ),
        "gy": gy,
        "gz": gz,
        "speed": speed_arr,
    }


def _fmt(value: object, spec: str = ".4f") -> str:
    if value is None:
        return "n/a"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not np.isfinite(v):
        return "n/a"
    return format(v, spec)


def print_table(report: dict) -> None:
    src = report.get("source", "?")
    seed = report.get("seed")
    method = report.get("method", "estimate")
    print()
    print("=" * 68)
    print(" SIH26168 evaluation  (bible 5.9 metrics)")
    extra = f"  seed={seed}" if seed is not None else ""
    print(f" source={src}  method={method}{extra}")
    print("=" * 68)
    print(f" {'metric':<34} {'value':>18}")
    print("-" * 68)
    rows = [
        ("Loop closure |p_end-p_start|", f"{_fmt(report['loop_closure_m'], '.4f')} m"),
        ("Distance travelled", f"{_fmt(report['distance_m'], '.2f')} m"),
        ("Drift %  (ISRO < 10%)", f"{_fmt(report['drift_pct'], '.3f')} %"),
        ("ATE RMSE", f"{_fmt(report['ate_m'], '.4f')} m"),
        ("RTE KITTI mean (m)", f"{_fmt(report['rte_m'], '.4f')} m"),
        ("RTE KITTI mean (%)", f"{_fmt(report.get('rte_pct'), '.3f')} %"),
    ]
    rte = report.get("rte") or {}
    trans = rte.get("trans_m") or {}
    pcts = rte.get("trans_pct") or {}
    nw = rte.get("n_windows") or {}
    for L in rte.get("lengths_m", list(KITTI_LENGTHS_M)):
        nwin = nw.get(L, nw.get(float(L), 0))
        rows.append(
            (
                f"RTE {int(L)} m  (n={nwin})",
                f"{_fmt(trans.get(L, trans.get(float(L))), '.4f')} m  "
                f"({_fmt(pcts.get(L, pcts.get(float(L))), '.2f')}%)",
            )
        )
    cdf = report.get("error_cdf") or {}
    for key in ("p50", "p75", "p90", "p95", "p99"):
        if key in cdf:
            rows.append((f"Error CDF {key}", f"{_fmt(cdf[key], '.4f')} m"))
    ba = report.get("branch_accuracy", 0.0)
    rows.append(("Branch-decision acc. [F12]", f"{_fmt(100.0 * float(ba), '.2f')} %"))
    rows.append(("Lean RMSE", f"{_fmt(report.get('lean_rmse_deg'), '.3f')} deg"))
    rows.append(("On-device latency", f"{_fmt(report.get('latency_ms'), '.2f')} ms"))
    rows.append(("On-device rate", f"{_fmt(report.get('latency_hz'), '.2f')} Hz"))
    for name, val in rows:
        print(f" {name:<34} {val:>18}")
    print("=" * 68)
    lat = report.get("latency") or {}
    if lat.get("note"):
        print(f" latency note: {lat['note']}")
    if report.get("note"):
        print(f" note: {report['note']}")
    print()


def build_report(run: dict) -> dict:
    lean = None
    if run.get("lean_est") is not None and run.get("lean_gt") is not None:
        lean = (run["lean_est"], run["lean_gt"])
    summary = summarize(
        run["est_xy"],
        run["gt_xy"],
        marker=run["gt_xy"][0] if len(run["gt_xy"]) else None,
        yaw_est=run.get("yaw_est"),
        yaw_gt=run.get("yaw_gt"),
        branches=run.get("branches"),
        lean=lean,
        sample_ms=run.get("sample_ms"),
    )
    errors = summary.pop("errors_m")
    report = {
        "source": run.get("source"),
        "method": run.get("method"),
        "seed": run.get("seed"),
        "note": run.get("note"),
        **summary,
        "n_samples": int(len(run["t"])),
    }
    report["_errors_m"] = errors
    return report


def write_report(report: dict, path: Path = REPORT_PATH) -> Path:
    dumped = {k: v for k, v in report.items() if k != "_errors_m"}
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(dumped), indent=2), encoding="utf-8")
    return path


def resolve_run(data: Path | None, seed: int) -> dict:
    candidates: list[Path] = []
    if data is not None:
        candidates.append(Path(data))
    candidates.append(DEFAULT_DATA)
    for c in candidates:
        if c.exists():
            loaded = load_csv_run(c)
            if loaded is not None:
                return loaded
    return generate_synthetic_run(seed=seed)


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    p = argparse.ArgumentParser(description="SIH26168 bible 5.9 evaluation harness")
    p.add_argument("--data", type=Path, default=None, help="CSV file or data/synthetic dir")
    p.add_argument("--seed", type=int, default=SEED)
    p.add_argument("--no-plot", action="store_true")
    args = p.parse_args(argv)

    run = resolve_run(args.data, args.seed)
    report = build_report(run)
    print_table(report)
    out = write_report(report)
    print(f" wrote {out}")

    if not args.no_plot:
        figs = write_figures(
            run["gt_xy"],
            run["est_xy"],
            run["t"],
            est_label=str(run.get("method", "estimate")),
        )
        for name, fp in figs.items():
            print(f" wrote {fp}")
        report["figures"] = figs
        write_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
