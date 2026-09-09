"""Score a RecordService field session for loop-closure error.

Import a phone-logged session directory (the same layout ``CsvLogger`` /
``RecordService`` write under Android external files) and report loop-closure
metrics so a real scooter/walk log can be scored with one command once it
exists.

Expected session layout
-----------------------
::

    <session_dir>/
      meta.json     required — phone, mount, vehicle, rider, route_id,
                    loop_closure {lat, lon}, notes, imu_hz, leans
      imu.csv       required — frozen bible §5.8 columns:
                    t_ns,ax,ay,az,gx,gy,gz,mx,my,mz,pressure_hpa,lux
      gnss.csv      required — frozen bible §5.8 columns:
                    t_ns,lat,lon,alt,speed,bearing,acc_h,acc_v,n_sats
      est.csv       optional — INS / COAST trail if exported later:
                    t_ns,east,north   OR   t_ns,lat,lon
                    (aliases: x/y, e/n also accepted)

Loop-closure protocol
---------------------
``meta.json.loop_closure`` is the painted return mark (lat/lon). Primary score
when ``est.csv`` is present::

    loop_closure_m = |p_est_end − marker|

Without an estimate trail we still report the GNSS return-to-mark span
(``|p_gnss_end − marker|``) and GNSS start↔end span — useful for quality,
but **not** an INS claim. Drift % uses GNSS path length as distance.

Usage
-----
::

    python -m lab.eval.score_field_log path/to/session_dir
    python -m lab.eval.score_field_log --dry-run
    python lab/eval/score_field_log.py --dry-run

``--dry-run`` scores the committed fixture under
``lab/eval/fixtures/field_session_dry_run/``. That fixture is **synthetic** —
real two-wheeler field logs are still pending
(``lab/stress/results/CURRENT_VERDICT.md`` RED). Do not cite dry-run numbers
as field proof.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

_EVAL = Path(__file__).resolve().parent
_LAB = _EVAL.parent
_REPO = _LAB.parent
for _p in (_EVAL, _LAB / "datasets", _LAB):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from log_schema import GNSS_COLUMNS, IMU_COLUMNS, validate_meta  # noqa: E402
from metrics import (  # noqa: E402
    drift_pct,
    jsonable,
    lla_to_enu,
    loop_closure_error,
    path_length,
)

FIXTURE_DIR = _EVAL / "fixtures" / "field_session_dry_run"
REPORT_NAME = "field_loop_score.json"


def _norm(name: str) -> str:
    return name.strip().lstrip("\ufeff").lower()


def _read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if not rows:
        raise ValueError(f"{path.name} is empty")
    header = [_norm(c) for c in rows[0]]
    body = [r for r in rows[1:] if r and any(c.strip() for c in r)]
    return header, body


def _col(header: list[str], *aliases: str) -> int | None:
    want = {_norm(a) for a in aliases}
    for i, h in enumerate(header):
        if h in want:
            return i
    return None


def _float_col(body: list[list[str]], idx: int) -> np.ndarray:
    out = np.empty(len(body), dtype=np.float64)
    for i, row in enumerate(body):
        try:
            out[i] = float(row[idx]) if idx < len(row) and row[idx] != "" else np.nan
        except ValueError:
            out[i] = np.nan
    return out


def load_session(session_dir: Path) -> dict[str, Any]:
    """Load a RecordService session directory into arrays + validated meta."""
    session_dir = Path(session_dir)
    meta_path = session_dir / "meta.json"
    imu_path = session_dir / "imu.csv"
    gnss_path = session_dir / "gnss.csv"
    est_path = session_dir / "est.csv"

    missing = [p.name for p in (meta_path, imu_path, gnss_path) if not p.is_file()]
    if missing:
        raise FileNotFoundError(
            f"{session_dir} missing required RecordService files: {missing}"
        )

    raw_meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta = validate_meta(raw_meta)

    imu_h, imu_body = _read_csv(imu_path)
    if tuple(imu_h) != tuple(IMU_COLUMNS):
        raise ValueError(
            f"imu.csv columns must be {tuple(IMU_COLUMNS)}, got {tuple(imu_h)}"
        )
    gnss_h, gnss_body = _read_csv(gnss_path)
    if tuple(gnss_h) != tuple(GNSS_COLUMNS):
        raise ValueError(
            f"gnss.csv columns must be {tuple(GNSS_COLUMNS)}, got {tuple(gnss_h)}"
        )

    gnss_lat = _float_col(gnss_body, gnss_h.index("lat"))
    gnss_lon = _float_col(gnss_body, gnss_h.index("lon"))
    mask = np.isfinite(gnss_lat) & np.isfinite(gnss_lon)
    gnss_lat, gnss_lon = gnss_lat[mask], gnss_lon[mask]
    if gnss_lat.size == 0:
        raise ValueError("gnss.csv has no finite lat/lon rows")

    origin_lat = float(gnss_lat[0])
    origin_lon = float(gnss_lon[0])
    gnss_xy = lla_to_enu(gnss_lat, gnss_lon, origin_lat, origin_lon)
    marker_xy = lla_to_enu(
        np.array([meta.loop_closure.lat]),
        np.array([meta.loop_closure.lon]),
        origin_lat,
        origin_lon,
    )[0]

    est_xy: np.ndarray | None = None
    est_source: str | None = None
    if est_path.is_file():
        eh, eb = _read_csv(est_path)
        ix_e = _col(eh, "east", "e", "x", "x_est", "east_est")
        ix_n = _col(eh, "north", "n", "y", "y_est", "north_est")
        ix_lat = _col(eh, "lat", "latitude")
        ix_lon = _col(eh, "lon", "longitude", "lng")
        if ix_e is not None and ix_n is not None:
            e = _float_col(eb, ix_e)
            n = _float_col(eb, ix_n)
            m = np.isfinite(e) & np.isfinite(n)
            est_xy = np.column_stack([e[m], n[m]])
            est_source = "est.csv east/north"
        elif ix_lat is not None and ix_lon is not None:
            la = _float_col(eb, ix_lat)
            lo = _float_col(eb, ix_lon)
            m = np.isfinite(la) & np.isfinite(lo)
            est_xy = lla_to_enu(la[m], lo[m], origin_lat, origin_lon)
            est_source = "est.csv lat/lon"
        else:
            raise ValueError(
                "est.csv needs (east,north) or (lat,lon) columns; "
                f"got {tuple(eh)}"
            )
        if est_xy is None or len(est_xy) == 0:
            raise ValueError("est.csv has no finite positions")

    return {
        "session_dir": str(session_dir.resolve()),
        "meta": meta,
        "imu_rows": len(imu_body),
        "gnss_rows": int(gnss_lat.size),
        "gnss_xy": gnss_xy,
        "marker_xy": marker_xy,
        "est_xy": est_xy,
        "est_source": est_source,
    }


def score_session(session_dir: Path, *, is_fixture: bool = False) -> dict[str, Any]:
    """Compute loop-closure metrics for one session directory."""
    packed = load_session(session_dir)
    meta = packed["meta"]
    gnss_xy = packed["gnss_xy"]
    marker = packed["marker_xy"]
    distance_m = path_length(gnss_xy)

    gnss_end_vs_start = loop_closure_error(positions=gnss_xy)
    gnss_end_vs_marker = loop_closure_error(p_end=gnss_xy[-1], marker=marker)

    est_xy = packed["est_xy"]
    if est_xy is not None:
        primary_m = loop_closure_error(p_end=est_xy[-1], marker=marker)
        primary_kind = "estimate_vs_marker"
        primary_source = packed["est_source"]
    else:
        primary_m = gnss_end_vs_marker
        primary_kind = "gnss_vs_marker_fallback"
        primary_source = (
            "no est.csv — GNSS end vs painted mark only "
            "(not an INS loop-closure claim)"
        )

    report: dict[str, Any] = {
        "session_dir": packed["session_dir"],
        "phone_model": meta.phone_model,
        "vehicle": meta.vehicle,
        "mount_type": meta.mount_type,
        "rider": meta.rider,
        "route_id": meta.route_id,
        "loop_closure_marker": {
            "lat": meta.loop_closure.lat,
            "lon": meta.loop_closure.lon,
        },
        "imu_rows": packed["imu_rows"],
        "gnss_rows": packed["gnss_rows"],
        "distance_m": distance_m,
        "loop_closure_m": primary_m,
        "loop_closure_kind": primary_kind,
        "loop_closure_source": primary_source,
        "drift_pct": drift_pct(primary_m, distance_m),
        "gnss_end_vs_start_m": gnss_end_vs_start,
        "gnss_end_vs_marker_m": gnss_end_vs_marker,
        "has_estimate_trail": est_xy is not None,
        "isro_drift_bar_pct": 10.0,
        "pass_isro_drift": bool(
            np.isfinite(primary_m)
            and distance_m >= 1.0
            and drift_pct(primary_m, distance_m) < 10.0
        ),
    }

    sess_name = Path(session_dir).name.lower()
    if is_fixture or "dry_run" in sess_name:
        report["data_status"] = "PENDING_REAL_FIELD_LOG"
        report["fixture"] = True
        report["honesty"] = (
            "Dry-run on a synthetic RecordService-shaped fixture. "
            "No qualifying real scooter/bicycle field log is in-repo yet "
            "(lab/stress/results/CURRENT_VERDICT.md — RED). "
            "Do not cite these numbers as field proof."
        )
    else:
        report["fixture"] = False
        if meta.vehicle in ("scooter", "motorcycle", "bicycle"):
            report["data_status"] = "FIELD_LOG_PRESENT"
        else:
            report["data_status"] = "FIELD_LOG_PRESENT_NON_TWOWHEELER"
        report["honesty"] = (
            "Scored from the provided session directory. "
            "Two-wheeler claim still needs ≥10 qualifying scooter/bike loops."
        )

    return report


def _print_report(report: dict[str, Any]) -> None:
    print("=" * 68)
    print(" COAST field-log loop-closure score")
    print("=" * 68)
    print(f" session:     {report['session_dir']}")
    print(f" vehicle:     {report['vehicle']}  mount={report['mount_type']}")
    print(f" route/rider: {report['route_id']} / {report['rider']}")
    print(f" data_status: {report['data_status']}")
    print("-" * 68)
    print(f" distance_m:              {report['distance_m']:.3f}")
    print(
        f" loop_closure_m:          {report['loop_closure_m']:.4f}  "
        f"({report['loop_closure_kind']})"
    )
    print(
        f" drift_pct:               {report['drift_pct']:.3f}  "
        f"(ISRO bar < {report['isro_drift_bar_pct']:.0f}%)"
    )
    print(f" gnss_end_vs_start_m:     {report['gnss_end_vs_start_m']:.4f}")
    print(f" gnss_end_vs_marker_m:    {report['gnss_end_vs_marker_m']:.4f}")
    print(f" has_estimate_trail:      {report['has_estimate_trail']}")
    print(f" pass_isro_drift:         {report['pass_isro_drift']}")
    print("-" * 68)
    print(f" note: {report['honesty']}")
    print("=" * 68)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass

    p = argparse.ArgumentParser(
        description="Score a RecordService session for loop-closure error."
    )
    p.add_argument(
        "session_dir",
        nargs="?",
        default=None,
        help="Path to session directory (imu.csv + gnss.csv + meta.json)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help=f"Score the synthetic fixture at {FIXTURE_DIR.relative_to(_REPO)}",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write JSON report here (default: <session>/field_loop_score.json)",
    )
    args = p.parse_args(argv)

    if args.dry_run:
        session = FIXTURE_DIR
        is_fixture = True
    elif args.session_dir:
        session = Path(args.session_dir)
        is_fixture = (
            "dry_run" in session.name.lower()
            or session.resolve() == FIXTURE_DIR.resolve()
        )
    else:
        p.error("pass a session_dir or --dry-run")
        return 2

    if not session.is_dir():
        print(f"FATAL: session directory not found: {session}", file=sys.stderr)
        return 1

    try:
        report = score_session(session, is_fixture=is_fixture)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        return 1

    if args.out is not None:
        out = args.out
    elif is_fixture:
        out = _EVAL / "results" / "field_loop_score_dry_run.json"
        out.parent.mkdir(parents=True, exist_ok=True)
    else:
        out = session / REPORT_NAME
    out.write_text(json.dumps(jsonable(report), indent=2), encoding="utf-8")
    _print_report(report)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
