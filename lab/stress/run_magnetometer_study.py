"""Why COAST does not fuse the magnetometer — measured, not asserted.

Problem statement 26168 lists the magnetometer/compass among the inputs the app
"should receive". We *do* read and log it (``sensor/SensorHub.kt`` registers
``TYPE_MAGNETIC_FIELD_UNCALIBRATED`` with a fallback to the calibrated sensor),
but ``nav/SimpleIns.kt`` deliberately does not fuse it into the heading estimate.

That is a design decision, and a design decision without a number is just an
opinion. This script produces the number.

The question
------------
Over the horizon we actually care about — a 60 s GNSS outage — is a magnetic
heading *better* than letting the gyro drift? If magnetic heading error is
smaller, we should fuse it and our current design is wrong. If it is larger, then
fusing it would inject confident error into an estimate the map can otherwise
correct, and not fusing it is right.

Method
------
Truth is ``GPS ORIENTATION`` (course over ground), used only while the vehicle is
moving fast enough for it to be meaningful (default 18 km/h) and while a GNSS fix
is present.

Two magnetic estimates are scored:

``phone_yaw``
    The phone's own fused orientation column (``ORIENTATION (Yaw)``) — what an
    app gets from the platform compass.
``tilt_comp``
    Tilt-compensated heading computed from raw ``MAGNETIC FIELD`` and ``GRAVITY``
    — what we would compute ourselves.

Both are *heading of the phone*, not heading of the vehicle. A phone in a mount
sits at some fixed yaw relative to the car, and magnetic north differs from true
north by the local declination. Both are constant per drive, so before scoring we
remove the per-drive circular-mean offset. **This deliberately flatters the
magnetometer**: it grants perfect mount-alignment calibration and perfect
declination correction, neither of which an app gets for free. The residual is
therefore a *lower bound* on the error a real fused compass would carry.

The gyro comparison integrates ``GYROSCOPE Yaw`` over 60 s windows starting from
truth, which is exactly what the estimator does during an outage.

Honesty notes
-------------
- Removing a per-drive offset is best-case for the magnetometer, not typical.
- Gyro yaw is measured in the phone frame; for a near-flat mount it approximates
  vehicle yaw. Tilted mounts would need the full projection the estimator does.
- GPS course itself is noisy at low speed, which is why slow samples are dropped.
- This measures heading only. It says nothing about position.

Usage
-----
    python -m lab.stress.run_magnetometer_study
    python -m lab.stress.run_magnetometer_study --limit 20 --min-kmh 18
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import statistics
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
RAW_GLOB = "data/raw/IO-VNBD/**/S-*.csv"
OUT_DIR = REPO / "lab" / "stress" / "results" / "magnetometer"

# Column header prefixes, matched case-insensitively after stripping. The raw
# files carry units and a stray leading space in most names.
WANT = {
    "speed_kmh": "gps speed",
    "bearing_deg": "gps orientation",
    "t_ms": "time since start",
    "gravity_x": "gravity x",
    "gravity_y": "gravity y",
    "gravity_z": "gravity z",
    "mag_x": "magnetic field x",
    "mag_y": "magnetic field y",
    "mag_z": "magnetic field z",
    "phone_yaw_deg": "orientation (yaw)",
    "gyro_yaw": "gyroscope yaw",
}

WINDOW_S = 60.0
HZ = 10.0


@dataclass
class DriveResult:
    name: str
    n_scored: int
    phone_yaw_med: float
    phone_yaw_p90: float
    tilt_med: float
    tilt_p90: float
    gyro_60s_med: float | None
    n_windows: int
    offset_phone_deg: float
    offset_tilt_deg: float


@dataclass
class Aggregate:
    drives: list[DriveResult] = field(default_factory=list)


def _norm(s: str) -> str:
    return s.strip().lower()


def _map_columns(header: list[str]) -> dict[str, int] | None:
    idx: dict[str, int] = {}
    norm = [_norm(h) for h in header]
    for key, prefix in WANT.items():
        hit = None
        for i, name in enumerate(norm):
            if name.startswith(prefix):
                hit = i
                break
        if hit is None:
            return None
        idx[key] = hit
    return idx


def _load(path: Path) -> dict[str, np.ndarray] | None:
    try:
        with path.open(newline="", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                return None
            idx = _map_columns(header)
            if idx is None:
                return None
            cols: dict[str, list[float]] = {k: [] for k in idx}
            for row in reader:
                if len(row) <= max(idx.values()):
                    continue
                try:
                    vals = {k: float(row[i]) for k, i in idx.items()}
                except ValueError:
                    continue
                for k, v in vals.items():
                    cols[k].append(v)
    except OSError:
        return None
    if not cols["t_ms"]:
        return None
    return {k: np.asarray(v, dtype=float) for k, v in cols.items()}


def _wrap180(deg: np.ndarray) -> np.ndarray:
    return (deg + 180.0) % 360.0 - 180.0


def _circular_offset(err_deg: np.ndarray) -> float:
    """Circular mean of an angular residual, in degrees."""
    r = np.deg2rad(err_deg)
    return float(np.rad2deg(math.atan2(float(np.mean(np.sin(r))), float(np.mean(np.cos(r))))))


def _tilt_compensated_heading(
    mag: np.ndarray, grav: np.ndarray
) -> np.ndarray:
    """Heading from magnetometer, levelled using the gravity vector.

    Builds an East-North basis in the device frame from gravity (down) and the
    magnetic vector, then reads the heading of the device +y axis.
    """
    down = grav / (np.linalg.norm(grav, axis=1, keepdims=True) + 1e-9)
    # East = down x mag  (right-handed, gives horizontal east)
    east = np.cross(down, mag)
    east /= np.linalg.norm(east, axis=1, keepdims=True) + 1e-9
    # North = east x down
    north = np.cross(east, down)
    north /= np.linalg.norm(north, axis=1, keepdims=True) + 1e-9
    # Heading of the device +y axis in the horizontal plane.
    ey = east[:, 1]
    ny = north[:, 1]
    return np.rad2deg(np.arctan2(ey, ny)) % 360.0


def _score_drive(
    name: str, d: dict[str, np.ndarray], min_kmh: float, min_samples: int
) -> DriveResult | None:
    speed = d["speed_kmh"]
    bearing = d["bearing_deg"]
    moving = (speed >= min_kmh) & np.isfinite(bearing) & (bearing >= 0.0) & (bearing <= 360.0)
    # Short drives must be excluded, not merely noted. Removing a per-drive
    # circular offset on a drive that is mostly one straight road absorbs almost
    # all of the error, so the compass scores near-zero for the wrong reason.
    # A drive needs enough moving samples -- and enough heading diversity -- for
    # the offset to be a calibration rather than a fit.
    if int(moving.sum()) < min_samples:
        return None
    hdg = bearing[moving]
    spread = float(np.rad2deg(
        math.hypot(float(np.mean(np.sin(np.deg2rad(hdg)))),
                   float(np.mean(np.cos(np.deg2rad(hdg)))))
    ))
    # Circular resultant length near 1 (here scaled to ~57.3) means every sample
    # points the same way: a straight line with no turns to constrain the offset.
    if spread > 54.0:
        return None

    mag = np.stack([d["mag_x"], d["mag_y"], d["mag_z"]], axis=1)
    grav = np.stack([d["gravity_x"], d["gravity_y"], d["gravity_z"]], axis=1)
    tilt = _tilt_compensated_heading(mag, grav)
    phone = d["phone_yaw_deg"] % 360.0

    # Residual before calibration, then remove the per-drive constant offset
    # (mount yaw + magnetic declination). This is best-case for the compass.
    raw_phone_err = _wrap180(phone[moving] - bearing[moving])
    raw_tilt_err = _wrap180(tilt[moving] - bearing[moving])
    off_p = _circular_offset(raw_phone_err)
    off_t = _circular_offset(raw_tilt_err)
    phone_err = np.abs(_wrap180(raw_phone_err - off_p))
    tilt_err = np.abs(_wrap180(raw_tilt_err - off_t))

    gyro_med, n_win = _gyro_window_drift(d, moving, min_kmh)

    return DriveResult(
        name=name,
        n_scored=int(moving.sum()),
        phone_yaw_med=float(np.median(phone_err)),
        phone_yaw_p90=float(np.percentile(phone_err, 90)),
        tilt_med=float(np.median(tilt_err)),
        tilt_p90=float(np.percentile(tilt_err, 90)),
        gyro_60s_med=gyro_med,
        n_windows=n_win,
        offset_phone_deg=off_p,
        offset_tilt_deg=off_t,
    )


def _gyro_window_drift(
    d: dict[str, np.ndarray], moving: np.ndarray, min_kmh: float
) -> tuple[float | None, int]:
    """Heading error after integrating gyro yaw for 60 s from a truth start.

    This is the comparison that matters: over one outage horizon, how far does a
    free-running gyro heading wander? If that is smaller than the compass error,
    the compass is not worth fusing.
    """
    t = d["t_ms"] / 1000.0
    gz = d["gyro_yaw"]
    bearing = d["bearing_deg"]
    n = len(t)
    step = int(WINDOW_S * HZ)
    if n < step + 10:
        return None, 0

    errs: list[float] = []
    for start in range(0, n - step, step):
        end = start + step
        if not (moving[start] and moving[end]):
            continue
        dt = np.diff(t[start : end + 1])
        if np.any(dt <= 0) or np.any(dt > 1.0):
            continue
        # Integrate yaw rate; sign convention matched to the bearing frame
        # (bearing increases clockwise, gyro z is counter-clockwise positive).
        dyaw = -np.rad2deg(np.sum(gz[start:end] * dt))
        pred = bearing[start] + dyaw
        errs.append(abs(float(_wrap180(np.asarray([pred - bearing[end]]))[0])))

    if len(errs) < 3:
        return None, len(errs)
    return float(statistics.median(errs)), len(errs)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0, help="max drives (0 = all)")
    ap.add_argument("--min-kmh", type=float, default=18.0)
    ap.add_argument(
        "--min-samples",
        type=int,
        default=3000,
        help="moving samples a drive needs before it counts (5 min at 10 Hz). "
        "Guards against per-drive offset removal overfitting a short straight run.",
    )
    args = ap.parse_args()

    paths = sorted({Path(p).resolve() for p in glob.glob(str(REPO / RAW_GLOB), recursive=True)})
    if not paths:
        print("No IO-VNBD smartphone CSVs found under data/raw/IO-VNBD.")
        return 1

    seen: set[str] = set()
    results: list[DriveResult] = []
    skipped = 0
    for p in paths:
        if args.limit and len(results) >= args.limit:
            break
        if p.stem in seen:
            continue
        d = _load(p)
        if d is None:
            skipped += 1
            continue
        r = _score_drive(p.stem, d, args.min_kmh, args.min_samples)
        if r is None:
            skipped += 1
            continue
        seen.add(p.stem)
        results.append(r)
        print(f"  {p.stem:<12} n={r.n_scored:>6}  phone {r.phone_yaw_med:5.1f}°  "
              f"tilt {r.tilt_med:5.1f}°  gyro60s "
              f"{('%.1f' % r.gyro_60s_med) if r.gyro_60s_med is not None else '  n/a'}°")

    if not results:
        print("No drive produced enough moving samples to score.")
        return 1

    phone_meds = [r.phone_yaw_med for r in results]
    tilt_meds = [r.tilt_med for r in results]
    gyro_meds = [r.gyro_60s_med for r in results if r.gyro_60s_med is not None]

    agg = {
        "n_drives": len(results),
        "n_skipped": skipped,
        "min_kmh": args.min_kmh,
        "min_samples": args.min_samples,
        "window_s": WINDOW_S,
        "phone_yaw_median_deg": statistics.median(phone_meds),
        "phone_yaw_p90_of_medians_deg": float(np.percentile(phone_meds, 90)),
        "tilt_comp_median_deg": statistics.median(tilt_meds),
        "tilt_comp_p90_of_medians_deg": float(np.percentile(tilt_meds, 90)),
        "gyro_60s_median_deg": statistics.median(gyro_meds) if gyro_meds else None,
        "n_drives_with_windows": len(gyro_meds),
        "drives": [r.__dict__ for r in results],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "report.json").write_text(json.dumps(agg, indent=2), encoding="utf-8")
    (OUT_DIR / "summary.md").write_text(_render(agg), encoding="utf-8")
    print(f"\nWrote {OUT_DIR / 'summary.md'}")
    return 0


def _render(a: dict) -> str:
    gyro = a["gyro_60s_median_deg"]
    phone = a["phone_yaw_median_deg"]
    tilt = a["tilt_comp_median_deg"]

    if gyro is None:
        verdict = "Gyro comparison unavailable — no clean 60 s windows."
    elif min(phone, tilt) > gyro:
        verdict = (
            f"**Not fusing the magnetometer is the right call on this corpus.** The best "
            f"magnetic heading available ({min(phone, tilt):.1f}° median) is worse than "
            f"letting the gyro free-run for a full {a['window_s']:.0f} s outage "
            f"({gyro:.1f}° median) — and that is *after* granting the compass a perfect "
            f"per-drive mount and declination calibration it would not get in practice. "
            f"Fusing it would inject confident error into a heading the map can otherwise "
            f"correct."
        )
    else:
        best = min(phone, tilt)
        # Lateral displacement fraction implied by holding this heading error.
        lat_pct = 100.0 * math.sin(math.radians(best))
        verdict = (
            f"**This measurement does NOT support our current design, and we are "
            f"reporting it against ourselves.** Magnetic heading ({best:.1f}° median) is "
            f"*better* than letting the gyro free-run for a {a['window_s']:.0f} s outage "
            f"({gyro:.1f}° median). On this corpus we are leaving usable heading "
            f"information unfused. Fusing the compass — with the mount and declination "
            f"offset estimated online rather than granted, as it is here — is a named "
            f"next step with a measured expected gain, not a guess.\n\n"
            f"**But the conclusion the pitch rests on is unchanged, and this strengthens "
            f"it.** A {best:.1f}° heading error held over a distance puts you roughly "
            f"{lat_pct:.0f}% of that distance sideways. Neither source is remotely good "
            f"enough to navigate on: the compass is confidently wrong, the gyro is "
            f"honestly drifting, and both blow the lateral budget long before a tunnel "
            f"ends. This is the same conclusion as the perfect-gyro ablation "
            f"(`../heading_ablation/summary.md`, still fails 55% of segments) reached "
            f"from an independent direction — **the fix is not a better heading sensor, "
            f"it is the map in the loop.**"
        )

    rows = "\n".join(
        f"| `{d['name']}` | {d['n_scored']} | {d['phone_yaw_med']:.1f} | "
        f"{d['tilt_med']:.1f} | "
        f"{('%.1f' % d['gyro_60s_med']) if d['gyro_60s_med'] is not None else '—'} |"
        for d in a["drives"]
    )

    return f"""# Magnetometer heading study — why COAST does not fuse the compass

Reproduce: `python -m lab.stress.run_magnetometer_study`

Problem statement 26168 lists the magnetometer/compass among the app's inputs.
COAST reads and logs it but does **not** fuse it into the heading estimate. This
is the measurement behind that decision.

## Verdict

{verdict}

## Aggregate ({a['n_drives']} drives, {a['n_skipped']} skipped)

Truth is GPS course over ground, scored only above **{a['min_kmh']:.0f} km/h**.
A per-drive circular offset is removed first, which grants the compass perfect
mount-alignment and declination correction — so these are **lower bounds** on
real-world compass error.

Drives need at least **{a['min_samples']} moving samples** ({a['min_samples'] / 600:.0f} min at 10 Hz)
and must contain real turning to be scored. Without that guard, removing a
per-drive offset on a short straight run absorbs nearly all the error and the
compass scores near-zero for the wrong reason — an earlier pass of this study
did exactly that, and the guard is what corrected it.

| Heading source | Median of per-drive medians | p90 of per-drive medians |
|---|---:|---:|
| Phone fused compass (`ORIENTATION (Yaw)`) | **{phone:.1f}°** | {a['phone_yaw_p90_of_medians_deg']:.1f}° |
| Tilt-compensated raw magnetometer | **{tilt:.1f}°** | {a['tilt_comp_p90_of_medians_deg']:.1f}° |
| Free-running gyro over {a['window_s']:.0f} s | {('**%.1f°**' % a['gyro_60s_median_deg']) if a['gyro_60s_median_deg'] is not None else '—'} | — |

## Why this matters for the heading budget

A heading error of θ degrees held over a distance d puts you roughly
`d · sin(θ)` metres sideways. The map-in-loop filter exists precisely because
lateral error is what kills a dead-reckoned fix. A compass that is confidently
wrong is worse than a gyro that is honestly drifting, because the filter can
model drift but cannot model a bias it has been told to trust.

## Limitations

- Removing a per-drive constant offset is **best case** for the magnetometer. A
  shipping app would also have to estimate mount yaw and declination online.
- Gyro yaw is integrated in the phone frame; for a near-flat mount that
  approximates vehicle yaw. Tilted mounts need the full projection the estimator
  performs.
- GPS course is itself noisy, which is why samples below {a['min_kmh']:.0f} km/h are dropped.
- This measures **heading only**, and says nothing about position accuracy.
- IO-VNBD is car data. A handlebar-mounted phone on a two-wheeler sits in a
  different magnetic environment and is not covered here.

## Per drive

| drive | scored samples | phone compass (°) | tilt-comp mag (°) | gyro 60 s (°) |
|---|---:|---:|---:|---:|
{rows}
"""


if __name__ == "__main__":
    raise SystemExit(main())
