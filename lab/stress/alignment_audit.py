#!/usr/bin/env python3
"""Rigorous IO-VNBD phone gyro/GPS time and axis alignment audit.

The estimator uses only phone IMU and GPS. Outage labels/ground truth are never
read. GPS rates are formed only from actual GPS changes (not repeated holds).
Every score uses all eligible turning samples in a file.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np

STRESS = Path(__file__).resolve().parent
ROOT = STRESS.parents[1]
RESULTS = STRESS / "results" / "alignment"
FIGURES = RESULTS / "figures"
if str(STRESS) not in sys.path:
    sys.path.insert(0, str(STRESS))

from load_iovnbd import find_smartphone_csvs, load_smartphone_csv  # noqa: E402

AXES = ("gyro_roll_raw", "gyro_pitch_raw", "gyro_yaw_raw")
LAG_MIN_S = -30.0
LAG_MAX_S = 30.0
LAG_STEP_S = 0.1
MIN_SPEED_MPS = 3.0
MIN_TURN_RATE_RAD_S = math.radians(0.5)
MAX_COURSE_RATE_RAD_S = math.radians(90.0)
MIN_SCORE_SAMPLES = 12


def _finite_corr(a: np.ndarray, b: np.ndarray) -> float:
    mask = np.isfinite(a) & np.isfinite(b)
    if int(mask.sum()) < MIN_SCORE_SAMPLES:
        return float("nan")
    x = np.asarray(a[mask], dtype=np.float64)
    y = np.asarray(b[mask], dtype=np.float64)
    # Limit isolated derivative/GPS spikes without selecting a preferred window.
    x = np.clip(x, *np.quantile(x, [0.02, 0.98]))
    y = np.clip(y, *np.quantile(y, [0.02, 0.98]))
    x -= np.mean(x)
    y -= np.mean(y)
    den = float(np.linalg.norm(x) * np.linalg.norm(y))
    return float(np.dot(x, y) / den) if den > 1e-12 else float("nan")


def _angle_delta_rad(a: np.ndarray) -> np.ndarray:
    return (np.diff(a) + math.pi) % (2.0 * math.pi) - math.pi


def _changed(values: np.ndarray, tol: float) -> np.ndarray:
    out = np.ones(values.size, dtype=bool)
    if values.size > 1:
        out[1:] = np.abs(np.diff(values)) > tol
    return out


def _speed_at(t: np.ndarray, speed: np.ndarray, query_t: np.ndarray) -> np.ndarray:
    finite = np.isfinite(t) & np.isfinite(speed)
    if int(finite.sum()) < 2:
        return np.full(query_t.size, np.nan)
    return np.interp(query_t, t[finite], speed[finite])


def _rate_series(
    t_mid: np.ndarray,
    rate: np.ndarray,
    start: np.ndarray,
    end: np.ndarray,
    speed: np.ndarray,
    source: str,
) -> dict[str, Any]:
    valid = (
        np.isfinite(t_mid)
        & np.isfinite(rate)
        & np.isfinite(speed)
        & (end > start)
        & (speed >= MIN_SPEED_MPS)
        & (np.abs(rate) <= MAX_COURSE_RATE_RAD_S)
    )
    if not np.any(valid):
        return {
            "source": source,
            "t": np.array([]),
            "rate": np.array([]),
            "start": np.array([]),
            "end": np.array([]),
            "speed": np.array([]),
            "turn": np.array([], dtype=bool),
        }
    r = rate[valid]
    dynamic_threshold = float(np.quantile(np.abs(r), 0.35)) if r.size else 0.0
    threshold = max(MIN_TURN_RATE_RAD_S, dynamic_threshold)
    return {
        "source": source,
        "t": t_mid[valid],
        "rate": r,
        "start": start[valid],
        "end": end[valid],
        "speed": speed[valid],
        "turn": np.abs(r) >= threshold,
        "turn_threshold_rad_s": threshold,
    }


def orientation_course_rate(data: dict[str, Any]) -> dict[str, Any]:
    """Course rate from GPS ORIENTATION changes only."""
    t = np.asarray(data["t_s"])
    bearing = np.asarray(data["bearing_deg"])
    finite = np.isfinite(t) & np.isfinite(bearing)
    idx0 = np.where(finite)[0]
    if idx0.size < 3:
        return _rate_series(*(np.array([]) for _ in range(5)), source="gps_orientation")
    b0 = np.deg2rad(bearing[idx0])
    changed = np.ones(idx0.size, dtype=bool)
    changed[1:] = np.abs(_angle_delta_rad(b0)) > math.radians(1e-4)
    idx = idx0[changed]
    if idx.size < 3:
        return _rate_series(*(np.array([]) for _ in range(5)), source="gps_orientation")
    tt = t[idx]
    bb = np.deg2rad(bearing[idx])
    dt = np.diff(tt)
    rate = _angle_delta_rad(bb) / dt
    mid = 0.5 * (tt[1:] + tt[:-1])
    speed = _speed_at(t, np.asarray(data["speed_mps"]), mid)
    valid_dt = (dt >= 0.05) & (dt <= 15.0)
    rate[~valid_dt] = np.nan
    return _rate_series(mid, rate, tt[:-1], tt[1:], speed, "gps_orientation")


def displacement_course_rate(data: dict[str, Any]) -> dict[str, Any]:
    """Course rate from consecutive changed lat/lon fixes."""
    t = np.asarray(data["t_s"])
    lat = np.asarray(data["lat"])
    lon = np.asarray(data["lon"])
    finite = np.isfinite(t) & np.isfinite(lat) & np.isfinite(lon)
    idx0 = np.where(finite)[0]
    if idx0.size < 4:
        return _rate_series(*(np.array([]) for _ in range(5)), source="latlon_displacement")
    changed = _changed(lat[idx0], 1e-10) | _changed(lon[idx0], 1e-10)
    idx = idx0[changed]
    if idx.size < 4:
        return _rate_series(*(np.array([]) for _ in range(5)), source="latlon_displacement")
    tt = t[idx]
    la = np.deg2rad(lat[idx])
    lo = np.deg2rad(lon[idx])
    north = np.diff(la) * 6_371_000.0
    east = np.diff(lo) * 6_371_000.0 * np.cos(0.5 * (la[1:] + la[:-1]))
    distance = np.hypot(east, north)
    seg_dt = np.diff(tt)
    course = np.arctan2(east, north)
    course_t = 0.5 * (tt[1:] + tt[:-1])
    # Reject nearly stationary displacement headings and implausibly long gaps.
    good_seg = (distance >= 2.0) & (seg_dt >= 0.1) & (seg_dt <= 15.0)
    pair_good = good_seg[1:] & good_seg[:-1]
    dt = np.diff(course_t)
    rate = _angle_delta_rad(course) / dt
    rate[~pair_good | (dt <= 0.05) | (dt > 15.0)] = np.nan
    mid = 0.5 * (course_t[1:] + course_t[:-1])
    speed = _speed_at(t, np.asarray(data["speed_mps"]), mid)
    # Each derivative spans the centres of two adjacent GPS displacement legs.
    return _rate_series(
        mid,
        rate,
        course_t[:-1],
        course_t[1:],
        speed,
        "latlon_displacement",
    )


def _integral(t: np.ndarray, x: np.ndarray) -> np.ndarray:
    out = np.zeros(t.size, dtype=np.float64)
    if t.size > 1:
        dt = np.diff(t)
        good = (dt > 0.0) & (dt < 2.0)
        increments = np.where(good, 0.5 * (x[1:] + x[:-1]) * dt, 0.0)
        out[1:] = np.cumsum(increments)
    return out


def _window_means(
    t: np.ndarray,
    integral: np.ndarray,
    starts: np.ndarray,
    ends: np.ndarray,
    lag_s: float,
) -> np.ndarray:
    a = starts + lag_s
    b = ends + lag_s
    valid = (a >= t[0]) & (b <= t[-1]) & (b > a)
    out = np.full(a.size, np.nan)
    if np.any(valid):
        ia = np.interp(a[valid], t, integral)
        ib = np.interp(b[valid], t, integral)
        out[valid] = (ib - ia) / (b[valid] - a[valid])
    return out


def score_axis_lags(data: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    t = np.asarray(data["t_s"])
    lags = np.arange(LAG_MIN_S, LAG_MAX_S + 0.5 * LAG_STEP_S, LAG_STEP_S)
    turn = np.asarray(target["turn"], dtype=bool)
    y = np.asarray(target["rate"])[turn]
    starts = np.asarray(target["start"])[turn]
    ends = np.asarray(target["end"])[turn]
    curves: dict[str, np.ndarray] = {}
    best: dict[str, Any] | None = None
    for axis in AXES:
        x = np.asarray(data[axis], dtype=np.float64)
        finite = np.isfinite(x)
        if not np.all(finite):
            x = np.interp(t, t[finite], x[finite]) if int(finite.sum()) >= 2 else np.zeros_like(t)
        integ = _integral(t, x)
        vals = np.full(lags.size, np.nan)
        counts = np.zeros(lags.size, dtype=int)
        for k, lag in enumerate(lags):
            mean_g = _window_means(t, integ, starts, ends, float(lag))
            mask = np.isfinite(mean_g) & np.isfinite(y)
            counts[k] = int(mask.sum())
            vals[k] = _finite_corr(mean_g[mask], y[mask])
        curves[axis] = vals
        if np.any(np.isfinite(vals)):
            k = int(np.nanargmax(np.abs(vals)))
            raw_corr = float(vals[k])
            candidate = {
                "axis": axis,
                "sign": 1 if raw_corr >= 0 else -1,
                "lag_s": float(lags[k]),
                "correlation": abs(raw_corr),
                "signed_correlation": raw_corr,
                "n_turn": int(counts[k]),
            }
            if best is None or candidate["correlation"] > best["correlation"]:
                best = candidate
    if best is None:
        best = {
            "axis": None,
            "sign": 0,
            "lag_s": float("nan"),
            "correlation": float("nan"),
            "signed_correlation": float("nan"),
            "n_turn": 0,
        }
    else:
        integ = _integral(t, np.asarray(data[best["axis"]], dtype=np.float64))
        g = _window_means(t, integ, starts, ends, best["lag_s"]) * best["sign"]
        mask = np.isfinite(g) & np.isfinite(y)
        if int(mask.sum()) >= 2:
            A = np.column_stack([g[mask], np.ones(int(mask.sum()))])
            slope, intercept = np.linalg.lstsq(A, y[mask], rcond=None)[0]
            best["scale_to_rad_s"] = float(slope)
            best["intercept_rad_s"] = float(intercept)
            best["gyro_rate_rad_s"] = g
            best["target_rate_rad_s"] = y
            best["target_t_s"] = np.asarray(target["t"])[turn]
    return {"best": best, "lags": lags, "curves": curves}


def estimate_mount_transform(
    data: dict[str, Any], target: dict[str, Any], lag_s: float
) -> dict[str, Any]:
    """Fit vehicle yaw rate as a fixed linear combination of phone gyro axes.

    Five contiguous folds report out-of-fold correlation, preventing the fitted
    transform from being presented as an in-sample axis-search win.
    """
    turn = np.asarray(target["turn"], dtype=bool)
    y = np.asarray(target["rate"])[turn]
    starts = np.asarray(target["start"])[turn]
    ends = np.asarray(target["end"])[turn]
    t = np.asarray(data["t_s"])
    cols = []
    for axis in AXES:
        cols.append(_window_means(t, _integral(t, np.asarray(data[axis])), starts, ends, lag_s))
    G = np.column_stack(cols) if cols else np.empty((0, 3))
    valid = np.isfinite(y) & np.all(np.isfinite(G), axis=1)
    y = y[valid]
    G = G[valid]
    if y.size < 5 * MIN_SCORE_SAMPLES:
        return {"observable": False, "reason": "fewer than 60 valid turning updates", "n": int(y.size)}
    pred = np.full(y.size, np.nan)
    fold_id = np.arange(y.size) * 5 // y.size
    coefficients = []
    for fold in range(5):
        train = fold_id != fold
        test = ~train
        A = np.column_stack([G[train], np.ones(int(train.sum()))])
        beta = np.linalg.lstsq(A, y[train], rcond=None)[0]
        pred[test] = G[test] @ beta[:3] + beta[3]
        coefficients.append(beta[:3])
    full = np.linalg.lstsq(np.column_stack([G, np.ones(y.size)]), y, rcond=None)[0]
    direction = full[:3]
    norm = float(np.linalg.norm(direction))
    unit = direction / norm if norm > 1e-12 else direction
    cv_corr = _finite_corr(pred, y)
    stable = np.std(np.asarray(coefficients), axis=0)
    return {
        "observable": bool(np.isfinite(cv_corr) and abs(cv_corr) >= 0.7),
        "n": int(y.size),
        "lag_s": float(lag_s),
        "cv_correlation": abs(float(cv_corr)),
        "cv_signed_correlation": float(cv_corr),
        "coefficients": {axis: float(direction[k]) for k, axis in enumerate(AXES)},
        "unit_yaw_axis_phone": {axis: float(unit[k]) for k, axis in enumerate(AXES)},
        "fold_coefficient_std": {axis: float(stable[k]) for k, axis in enumerate(AXES)},
        "intercept_rad_s": float(full[3]),
        "note": "Diagnostic 5-fold contiguous CV; not used by the common-axis gate.",
    }


def inspect_time_scale(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    with path.open("r", newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        header = next(reader)
        time_idx = next(i for i, h in enumerate(header) if "TIME SINCE START" in h.upper())
        raw = []
        for row in reader:
            try:
                raw.append(float(row[time_idx]))
            except (IndexError, ValueError):
                continue
            if len(raw) >= 2000:
                break
    dt = np.diff(np.asarray(raw))
    dt = dt[np.isfinite(dt) & (dt > 0)]
    med = float(np.median(dt)) if dt.size else float("nan")
    candidates = []
    for scale in (1e-6, 1e-3, 1.0):
        hz = 1.0 / (med * scale) if med > 0 else float("nan")
        score = abs(math.log10(hz / 10.0)) if hz > 0 else float("inf")
        candidates.append({"scale_to_seconds": scale, "implied_hz": hz, "distance_from_10hz_log10": score})
    chosen = min(candidates, key=lambda row: row["distance_from_10hz_log10"])
    return {
        "raw_median_delta": med,
        "candidates": candidates,
        "chosen_scale_to_seconds": chosen["scale_to_seconds"],
        "loader_hz_est": float(data["hz_est"]),
        "separate_gps_clock_available": False,
        "note": "One shared TIME SINCE START column exists; residual sensor latency is searched as lag.",
    }


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        bulky = {"gyro_rate_rad_s", "target_rate_rad_s", "target_t_s"}
        return {k: _jsonable(v) for k, v in value.items() if k not in bulky}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def plot_file(name: str, targets: dict[str, dict[str, Any]], scores: dict[str, dict[str, Any]]) -> str:
    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    for col, source in enumerate(("gps_orientation", "latlon_displacement")):
        target = targets[source]
        score = scores[source]
        ax = axes[0, col]
        ax.set_title(f"{name}: {source}")
        best = score["best"]
        if best["axis"] is not None and "gyro_rate_rad_s" in best:
            tt = best["target_t_s"]
            ax.plot(tt, np.rad2deg(best["target_rate_rad_s"]), ".", ms=3, label="GPS course rate")
            ax.plot(tt, np.rad2deg(best["gyro_rate_rad_s"]), ".", ms=3, alpha=0.7, label=f"{best['sign']:+d}{best['axis']} lag={best['lag_s']:.1f}s")
            ax.legend(fontsize=8)
        ax.set_ylabel("turn rate (deg/s)")
        ax.set_xlabel("time (s)")
        lag_ax = axes[1, col]
        for axis in AXES:
            lag_ax.plot(score["lags"], np.abs(score["curves"][axis]), label=f"±{axis}")
        lag_ax.axvline(best["lag_s"], color="k", ls=":", lw=1)
        lag_ax.set_ylim(0, 1.02)
        lag_ax.set_xlabel("gyro lag relative to GPS (s)")
        lag_ax.set_ylabel("|correlation|")
        lag_ax.legend(fontsize=8)
    fig.tight_layout()
    FIGURES.mkdir(parents=True, exist_ok=True)
    path = FIGURES / f"{Path(name).stem}_alignment.png"
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return str(path)


def common_mapping(files: list[dict[str, Any]]) -> dict[str, Any]:
    """Require the same discrete axis/sign to clear 0.7 in multiple files.

    Each file may have its own latency because the logs do not expose separate
    Android sensor and GPS clocks. Both independent GPS-rate derivations must
    agree when each has enough samples.
    """
    candidates = [(axis, sign) for axis in AXES for sign in (-1, 1)]
    rows = []
    for axis, sign in candidates:
        per_file = []
        for f in files:
            source_scores = []
            for source in ("gps_orientation", "latlon_displacement"):
                audit = f["_scores"][source]
                vals = audit["curves"][axis] * sign
                if np.any(np.isfinite(vals)):
                    k = int(np.nanargmax(vals))
                    source_scores.append(float(vals[k]))
            score = min(source_scores) if len(source_scores) == 2 else (source_scores[0] if source_scores else float("nan"))
            per_file.append(score)
        passing = int(sum(np.isfinite(v) and v > 0.7 for v in per_file))
        rows.append({"axis": axis, "sign": sign, "per_file_correlation": per_file, "files_above_0_7": passing})
    rows.sort(
        key=lambda r: (
            r["files_above_0_7"],
            np.nanmedian(r["per_file_correlation"]) if np.any(np.isfinite(r["per_file_correlation"])) else -1,
        ),
        reverse=True,
    )
    best = rows[0]
    exists = best["files_above_0_7"] >= 2
    return {
        "exists": exists,
        "threshold": 0.7,
        "required_files": 2,
        "best_axis": best["axis"],
        "best_sign": best["sign"],
        "files_above_threshold": best["files_above_0_7"],
        "per_file_correlation": {
            files[k]["name"]: best["per_file_correlation"][k] for k in range(len(files))
        },
        "verdict": "DEFENSIBLE_COMMON_MAPPING" if exists else "NO_DEFENSIBLE_COMMON_MAPPING",
        "gate_note": "Uses the weaker of orientation- and displacement-course evidence where both exist.",
        "all_candidates": rows,
    }


def post_mapping_stress_summary() -> dict[str, Any] | None:
    path = STRESS / "results" / "hardened_slim_report.json"
    if not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = [r for r in raw.get("rows", []) if float(r.get("deny_s", 0.0)) == 60.0]
    focus_methods = {"car_bias", "idr_bias", "car_bias_map", "idr_bias_map"}
    focus = [r for r in rows if r.get("method") in focus_methods]
    isro = [r for r in rows if r.get("verdict") == "PASS_ISRO"]
    competitive = [r for r in focus if str(r.get("verdict", "")).startswith("PASS")]
    return {
        "source": str(path),
        "all_60s_rows": len(rows),
        "focus_60s_rows": len(focus),
        "focus_pass_competitive_or_better": len(competitive),
        "pass_isro_rows": len(isro),
        "focus_rows": focus,
        "adversarial_tw": raw.get("adversarial_tw"),
    }


def write_report(report: dict[str, Any]) -> None:
    lines = [
        "# IO-VNBD phone IMU alignment audit",
        "",
        f"Verdict: **{report['verdict']}**",
        "",
        "GPS rates use only true field changes, robust angle differences, speed ≥ "
        f"{MIN_SPEED_MPS:.1f} m/s, and all eligible turns. Lag search: "
        f"{LAG_MIN_S:.0f}…+{LAG_MAX_S:.0f} s at {LAG_STEP_S:.1f} s. "
        "No outage ground truth is loaded.",
        "",
        "## Best discrete axis/sign/lag per CSV",
        "",
        "| CSV | GPS source | axis/sign | lag s | corr | turn updates |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for f in report["files"]:
        for source in ("gps_orientation", "latlon_displacement"):
            b = f[source]["best"]
            axis_sign = "none" if b["axis"] is None else f"{b['sign']:+d}{b['axis']}"
            corr = "n/a" if b["correlation"] is None else f"{b['correlation']:.3f}"
            lag = "n/a" if b["lag_s"] is None else f"{b['lag_s']:.1f}"
            lines.append(f"| {f['name']} | {source} | `{axis_sign}` | {lag} | {corr} | {b['n_turn']} |")
    common = report["common_mapping"]
    lines += [
        "",
        "## Common mapping gate",
        "",
        f"**{common['verdict']}**. Best candidate: `{common['best_sign']:+d}{common['best_axis']}`; "
        f"{common['files_above_threshold']} files exceed correlation 0.7 under the conservative dual-source score.",
        "",
        "Per-file conservative correlations: "
        + ", ".join(f"`{k}`={v:.3f}" if v is not None else f"`{k}`=n/a" for k, v in common["per_file_correlation"].items()),
        "",
        "## Fixed mount transform diagnostics",
        "",
        "| CSV | GPS source | CV corr | unit vehicle-yaw axis in phone [Roll, Pitch, Yaw] | observable |",
        "|---|---|---:|---|---|",
    ]
    for f in report["files"]:
        for source in ("gps_orientation", "latlon_displacement"):
            m = f[source]["mount_transform"]
            if not m.get("observable") and "unit_yaw_axis_phone" not in m:
                lines.append(f"| {f['name']} | {source} | n/a | n/a | no ({m.get('reason')}) |")
                continue
            u = m["unit_yaw_axis_phone"]
            lines.append(
                f"| {f['name']} | {source} | {m['cv_correlation']:.3f} | "
                f"[{u['gyro_roll_raw']:.3f}, {u['gyro_pitch_raw']:.3f}, {u['gyro_yaw_raw']:.3f}] | "
                f"{'yes' if m['observable'] else 'no'} |"
            )
    lines += [
        "",
        "The fitted yaw-axis transform is reported with contiguous five-fold out-of-fold correlation. "
        "Course rate observes only the vehicle vertical axis: rotation about that axis and the full "
        "accelerometer mount are not identifiable. Raw accelerometer Z carries gravity in all four "
        "files, so the gyro labels are likely semantic/app labels rather than physical Android axes. "
        "The fit is diagnostic only and cannot make the product gate pass.",
        "",
        "## Real-data verdict",
        "",
        report["real_data_verdict"],
    ]
    stress = report.get("post_mapping_60s_stress")
    if stress:
        lines += [
            "",
            "## Post-mapping 60 s replay",
            "",
            f"Focused car/lean, map/no-map rows passing competitive-or-better: "
            f"**{stress['focus_pass_competitive_or_better']}/{stress['focus_60s_rows']}**; "
            f"ISRO passes across all 60 s rows: **{stress['pass_isro_rows']}**.",
            "",
            "| CSV | site | method | final m | drift % | verdict |",
            "|---|---|---|---:|---:|---|",
        ]
        for row in stress["focus_rows"]:
            lines.append(
                f"| {row['csv']} | {row['site']} | `{row['method']}` | "
                f"{row['final_m']:.2f} | {row['drift_pct']:.2f} | **{row['verdict']}** |"
            )
    lines += ["", "JSON: `alignment_report.json`", "", "Plots:"]
    lines.extend(f"- `{f['figure']}`" for f in report["files"])
    (RESULTS / "ALIGNMENT_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    paths = find_smartphone_csvs()
    if not paths:
        raise SystemExit("No real S-*.csv >1 MB found; pull Git LFS data.")
    file_reports = []
    for path in paths:
        print(f"Auditing {path.name} ({path.stat().st_size:,} bytes)")
        data = load_smartphone_csv(path)
        targets = {
            "gps_orientation": orientation_course_rate(data),
            "latlon_displacement": displacement_course_rate(data),
        }
        scores = {source: score_axis_lags(data, target) for source, target in targets.items()}
        public_sources = {}
        for source, audit in scores.items():
            lag = audit["best"]["lag_s"]
            mount = estimate_mount_transform(data, targets[source], lag) if np.isfinite(lag) else {"observable": False, "reason": "no lag score"}
            public_sources[source] = {
                "gps_updates_after_gating": int(np.asarray(targets[source]["rate"]).size),
                "turn_updates": int(np.asarray(targets[source]["turn"]).sum()),
                "turn_threshold_deg_s": math.degrees(float(targets[source].get("turn_threshold_rad_s", 0.0))),
                "best": _jsonable(audit["best"]),
                "mount_transform": _jsonable(mount),
            }
        figure = plot_file(path.name, targets, scores)
        file_reports.append(
            {
                "name": path.name,
                "path": str(path),
                "bytes": path.stat().st_size,
                "n": data["n"],
                "time_scale": inspect_time_scale(path, data),
                **public_sources,
                "figure": figure,
                "_scores": scores,
            }
        )
        for source in targets:
            b = scores[source]["best"]
            print(f"  {source:20s} {b['sign']:+d}{b['axis']} lag={b['lag_s']:6.1f}s r={b['correlation']:.3f} n={b['n_turn']}")
    common = common_mapping(file_reports)
    verdict = "PASS_ALIGNMENT" if common["exists"] else "FAIL_ALIGNMENT"
    stress = post_mapping_stress_summary()
    if common["exists"]:
        if stress and stress["pass_isro_rows"] == 0:
            real_data_verdict = (
                "The axis/time alignment gate passes and the loader now maps vehicle yaw to "
                "-GYROSCOPE Pitch. The focused navigation/ISRO gate remains red: mapped 60 s "
                "replay still has zero ISRO passes; only one S-S1 late-route scenario passes the "
                "weaker competitive map-aided criterion, while S-M and the other S-S1 site fail. "
                "The separate weak product_gate.py criterion may pass and must not be read as "
                "ISRO or field readiness."
            )
        else:
            real_data_verdict = (
                "A common discrete phone-yaw mapping exceeds correlation 0.7 on multiple complete "
                "files. Navigation readiness must be decided from the post-mapping stress battery."
            )
    else:
        real_data_verdict = (
            "Product gate remains red: no single gyro axis/sign is independently supported at "
            "correlation >0.7 across multiple complete real files by both GPS-orientation and "
            "lat/lon-displacement course rates. No loader/replay mapping was changed."
        )
    report = {
        "schema_version": 1,
        "protocol": {
            "lag_range_s": [LAG_MIN_S, LAG_MAX_S],
            "lag_step_s": LAG_STEP_S,
            "minimum_speed_mps": MIN_SPEED_MPS,
            "minimum_turn_rate_deg_s": math.degrees(MIN_TURN_RATE_RAD_S),
            "uses_outage_ground_truth": False,
            "selection": "all speed-gated true-GPS-update turning samples per complete file",
        },
        "files": file_reports,
        "common_mapping": common,
        "verdict": verdict,
        "real_data_verdict": real_data_verdict,
        "post_mapping_60s_stress": stress,
    }
    clean = _jsonable(report)
    for f in clean["files"]:
        f.pop("_scores", None)
    (RESULTS / "alignment_report.json").write_text(json.dumps(clean, indent=2), encoding="utf-8")
    write_report(clean)
    print(f"\n{verdict}: {common['verdict']}")
    print(f"Wrote {RESULTS / 'alignment_report.json'}")
    print(f"Wrote {RESULTS / 'ALIGNMENT_REPORT.md'}")
    return 0 if common["exists"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
