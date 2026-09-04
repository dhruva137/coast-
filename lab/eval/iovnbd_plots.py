"""IO-VNBD preliminary inference plots (10 Hz windows, not AVNet 200 Hz).

If data/raw/IO-VNBD/*.csv exists and is >1 MB (real file, not a Git LFS
pointer), use it. Otherwise use the Ford-Fiesta-like fixture.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

EVAL_DIR = Path(__file__).resolve().parent
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from synthetic_iovnbd import FIXTURE_PATH, G, HZ, SEED, write_csv  # noqa: E402

REPO_ROOT = EVAL_DIR.parent.parent
RAW_IOVNBD = REPO_ROOT / "data" / "raw" / "IO-VNBD"
FIGURES_DIR = EVAL_DIR / "figures"
MIN_REAL_BYTES = 1_000_000

# IO-VNBD is 10 Hz. AVNet's 200-sample window is 1 s at 200 Hz — wrong here.
# A 1 s window at 10 Hz is 10 samples. Default learned-odometry window: 2 s.
WINDOW_SECONDS = 2.0
WINDOW_SAMPLES = max(4, int(round(HZ * WINDOW_SECONDS)))  # 20, never 200

# Project bible [F8] — published sandbox numbers (labels on the bar chart).
F8_ROWS = (
    ("AVNet velocity error (0.5 m/s ≈ 5%)", 15.0, 1.13),
    ("AVNet attitude error (~10°)", 52.3, 3.94),
    ("cos(lean) error at 34° lean", 84.9, 6.40),
    ("Phone gyro bias 0.3°/s over 125 s", 188.5, 14.20),
)

_GNSS = "#1f4e79"
_DR = "#c45911"
_OUT = "#f4b183"
_GRID = "#d9d9d9"


def _norm(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


_ALIASES = {
    "lat": ("gpslatitude", "gps latitude", "latitude", "lat"),
    "lon": ("gpslongitude", "gps longitude", "longitude", "lon", "lng"),
    "alt": ("gpsaltitude", "gps altitude", "altitude", "alt", "gpsheight"),
    "speed": ("gpsspeed", "gps speed", "gpsvelocity", "indicatedvehiclespeed", "speed"),
    "heading": ("gpsorientation", "gps orientation", "gpsheading", "orientationyaw", "heading"),
    "sats": ("gpssatellitesinrange", "noofgpssatellitesavailable", "sats", "nsats"),
    "acc": ("gpsaccuracy", "gps accuracy", "acch"),
    "t": ("timesincestart", "time since start", "timesincestartofday", "timestamp", "time", "t"),
    "ax": ("accelerometerx", "accelerometer x", "indicatedlongitudinalacceleration", "ax"),
    "ay": ("accelerometery", "accelerometer y", "indicatedlateralacceleration", "ay"),
    "az": ("accelerometerz", "accelerometer z", "az"),
    "gx": ("gyroscoperoll", "gyroscope roll", "gx"),
    "gy": ("gyroscopepitch", "gyroscope pitch", "gy"),
    "gz": ("gyroscopeyaw", "gyroscope yaw", "yawrate", "gz"),
    "gnss_ok": ("gnssvalid", "gpsvalid", "gnssok"),
}


def resolve_csv() -> tuple[Path, str]:
    """Prefer real smartphone S-*.csv files that actually parse with lat/lon."""
    root = RAW_IOVNBD
    candidates: list[Path] = []
    if root.is_dir():
        for path in sorted(root.rglob("S-*.csv")):
            try:
                if path.stat().st_size > MIN_REAL_BYTES:
                    candidates.append(path)
            except OSError:
                continue
        # Prefer known good sessions first
        prefer = ("S-S1.csv", "S-S2.csv", "S-S4.csv", "S-M.csv")
        ranked = sorted(
            candidates,
            key=lambda p: (prefer.index(p.name) if p.name in prefer else 99, p.name),
        )
        for path in ranked:
            try:
                tr = load_trace(path)
                if np.isfinite(tr["lat"]).sum() > 50 and np.isfinite(tr["lon"]).sum() > 50:
                    return path, "IO-VNBD raw"
            except Exception:
                continue
        if ranked:
            return ranked[0], "IO-VNBD raw"
    if not FIXTURE_PATH.is_file():
        write_csv(FIXTURE_PATH, seed=SEED)
    return FIXTURE_PATH, "IO-VNBD fixture (Git LFS absent)"


def _pick(header: list[str], key: str) -> int | None:
    norms = [_norm(h) for h in header]
    compact = [n.replace(" ", "") for n in norms]
    for alias in _ALIASES[key]:
        a = _norm(alias)
        ac = a.replace(" ", "")
        if a in norms:
            return norms.index(a)
        if ac in compact:
            return compact.index(ac)
        for i, n in enumerate(norms):
            if a and a in n:
                return i
    return None


def _col(rows: list[list[str]], idx: int | None, n: int, default=np.nan) -> np.ndarray:
    out = np.full(n, default, dtype=np.float64)
    if idx is None:
        return out
    for i, row in enumerate(rows):
        if idx >= len(row):
            continue
        raw = row[idx].strip()
        if raw == "":
            continue
        try:
            out[i] = float(raw)
        except ValueError:
            continue
    return out


def _meters_per_deg(lat_deg: float) -> tuple[float, float]:
    lat = np.deg2rad(lat_deg)
    m_lat = 111_132.92 - 559.82 * np.cos(2 * lat) + 1.175 * np.cos(4 * lat)
    m_lon = 111_412.84 * np.cos(lat) - 93.5 * np.cos(3 * lat)
    return float(m_lat), float(m_lon)


def _lla_to_enu(lat: np.ndarray, lon: np.ndarray, origin_lat: float, origin_lon: float) -> tuple[np.ndarray, np.ndarray]:
    m_lat, m_lon = _meters_per_deg(origin_lat)
    return (lon - origin_lon) * m_lon, (lat - origin_lat) * m_lat


def _haversine(lat1, lon1, lat2, lon2) -> float:
    r = 6_371_000.0
    p1, p2 = np.deg2rad(lat1), np.deg2rad(lat2)
    dp = np.deg2rad(lat2 - lat1)
    dl = np.deg2rad(lon2 - lon1)
    a = np.sin(dp / 2.0) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2.0) ** 2
    return float(2.0 * r * np.arcsin(np.minimum(1.0, np.sqrt(a))))


def load_trace(path: Path) -> dict:
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        rows = [row for row in reader if row]
    n = len(rows)
    if n < 40:
        raise ValueError(f"{path} has too few rows ({n})")

    t = _col(rows, _pick(header, "t"), n)
    if np.isfinite(t).sum() >= n // 2:
        t = np.where(np.isfinite(t), t, np.nan)
        # Smartphone "Time since start" is ms; ECU is seconds.
        finite = t[np.isfinite(t)]
        span = float(finite[-1] - finite[0]) if finite.size > 1 else 0.0
        t = np.arange(n, dtype=np.float64) / HZ if span <= 0 else (
            (t - finite[0]) / 1000.0 if np.nanmedian(np.diff(finite)) > 2.0 else (t - finite[0])
        )
    else:
        t = np.arange(n, dtype=np.float64) / HZ
    t = np.asarray(t, dtype=np.float64)

    lat = _col(rows, _pick(header, "lat"), n)
    lon = _col(rows, _pick(header, "lon"), n)
    ax = _col(rows, _pick(header, "ax"), n, 0.0)
    ay = _col(rows, _pick(header, "ay"), n, 0.0)
    az = _col(rows, _pick(header, "az"), n, G)
    gx = _col(rows, _pick(header, "gx"), n, 0.0)
    gy = _col(rows, _pick(header, "gy"), n, 0.0)
    gz = _col(rows, _pick(header, "gz"), n, 0.0)
    speed_kmh = _col(rows, _pick(header, "speed"), n)
    heading = _col(rows, _pick(header, "heading"), n)
    sats = _col(rows, _pick(header, "sats"), n, 12.0)
    acc = _col(rows, _pick(header, "acc"), n, 3.0)
    flag = _col(rows, _pick(header, "gnss_ok"), n)

    # Unit heuristics: ECU accel in g, ECU yaw rate in deg/s.
    if np.nanmedian(np.abs(ax[np.isfinite(ax)])) < 3.5 and np.nanmedian(np.abs(az[np.isfinite(az)])) < 3.5:
        ax, ay, az = ax * G, ay * G, np.where(np.isfinite(az), az * G, G)
    if np.nanmax(np.abs(gz[np.isfinite(gz)])) > 1.5:
        gz = np.deg2rad(gz)

    speed_mps = np.where(np.isfinite(speed_kmh), speed_kmh / 3.6, np.nan)
    heading_rad = np.where(np.isfinite(heading), np.deg2rad(heading), np.nan)

    if np.isfinite(flag).any():
        gnss_ok = flag >= 0.5
    else:
        gnss_ok = (
            np.isfinite(lat)
            & np.isfinite(lon)
            & (np.where(np.isfinite(sats), sats, 12.0) >= 4)
            & (np.where(np.isfinite(acc), acc, 3.0) < 50.0)
        )

    return {
        "t": t,
        "lat": lat,
        "lon": lon,
        "ax": ax,
        "ay": ay,
        "az": az,
        "gx": gx,
        "gy": gy,
        "gz": gz,
        "speed_mps": speed_mps,
        "heading_rad": heading_rad,
        "gnss_ok": gnss_ok,
        "n": n,
    }


def choose_outage(t: np.ndarray, lat: np.ndarray, lon: np.ndarray, gnss_ok: np.ndarray) -> np.ndarray:
    """Use a logged outage if present; else mask ~60 s / ~1 km for DR."""
    existing = ~gnss_ok
    if existing.any():
        # Longest False-run in gnss_ok.
        padded = np.concatenate([[True], gnss_ok, [True]])
        edges = np.flatnonzero(np.diff(padded.astype(np.int8)))
        best = None
        for a, b in zip(edges[0::2], edges[1::2]):
            if best is None or (b - a) > (best[1] - best[0]):
                best = (a, b)
        if best is not None and (t[min(best[1], len(t) - 1)] - t[best[0]]) >= 25.0:
            mask = np.zeros(len(t), dtype=bool)
            mask[best[0] : best[1]] = True
            return mask

    n = len(t)
    origin_lat = float(lat[np.isfinite(lat)][0])
    origin_lon = float(lon[np.isfinite(lon)][0])
    e, north = _lla_to_enu(lat, lon, origin_lat, origin_lon)
    de = np.diff(e, prepend=e[0])
    dn = np.diff(north, prepend=north[0])
    de[~np.isfinite(de)] = 0.0
    dn[~np.isfinite(dn)] = 0.0
    dist = np.cumsum(np.hypot(de, dn))
    target_s, target_m = 60.0, 1000.0
    warmup = int(np.searchsorted(t, t[0] + 20.0))
    best_i, best_score = warmup, 1e18
    for i in range(warmup, n):
        j = int(np.searchsorted(t, t[i] + target_s))
        if j >= n:
            break
        score = abs((dist[j] - dist[i]) - target_m)
        if score < best_score:
            best_score, best_i = score, i
    j = min(n, int(np.searchsorted(t, t[best_i] + target_s)))
    mask = np.zeros(n, dtype=bool)
    mask[best_i:j] = True
    return mask


def windowed_velocity(
    ax: np.ndarray,
    ay: np.ndarray,
    az: np.ndarray,
    gz: np.ndarray,
    speed_gnss: np.ndarray,
    aiding: np.ndarray,
    hz: float = HZ,
) -> np.ndarray:
    """10 Hz windowed speed. Window = 2 s = 20 samples, not 200.

    GNSS locks speed and an accel bias while aided. During an outage the
    estimator coasts on (windowed ax − bias). ZUPT only when actually still.
    The 0.995-per-sample damp from the 200 Hz demo would zero speed in 60 s
    at 10 Hz — do not use it here.
    """
    win = max(4, int(round(hz * WINDOW_SECONDS)))
    assert win != 200, "AVNet 200-sample windows are invalid at 10 Hz"
    n = len(ax)
    dt = 1.0 / hz
    speed = 0.0
    bias = 0.0
    out = np.zeros(n)
    for i in range(n):
        lo = max(0, i - win + 1)
        sl = slice(lo, i + 1)
        low_ax = float(np.mean(ax[sl]))
        yaw = float(np.mean(gz[sl]))
        a_mean = float(np.mean(np.sqrt(ax[sl] ** 2 + ay[sl] ** 2 + az[sl] ** 2)))
        if aiding[i] and np.isfinite(speed_gnss[i]):
            if i > 0 and np.isfinite(speed_gnss[i - 1]):
                a_ref = (float(speed_gnss[i]) - float(speed_gnss[i - 1])) * hz
                if abs(a_ref) < 0.6 and abs(yaw) < 0.08:
                    bias = 0.95 * bias + 0.05 * (low_ax - a_ref)
            speed = 0.20 * (speed + (low_ax - bias) * dt) + 0.80 * float(speed_gnss[i])
        else:
            resid = low_ax - bias
            # 2 s mean of IO-VNBD vibration is ~0.1 m/s²; do not integrate it.
            if abs(resid) < 0.40:
                resid = 0.0
            speed = speed + resid * dt
            if a_mean < 10.2 and abs(yaw) < 0.03 and speed < 1.2:
                speed *= 0.90
        out[i] = max(0.0, speed)
    return out


def _wrap_pi(a: float) -> float:
    return float((a + np.pi) % (2.0 * np.pi) - np.pi)


def dead_reckon(
    speed: np.ndarray,
    gz: np.ndarray,
    heading_gnss: np.ndarray,
    e_gt: np.ndarray,
    n_gt: np.ndarray,
    aiding: np.ndarray,
    hz: float = HZ,
    speed_scale: float = 1.0,
    heading0_offset: float = 0.0,
    yaw_scale: float = 1.0,
    gyro_bias: float = 0.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Integrate windowed speed + gyro heading. Snap to GNSS when aiding."""
    n = len(speed)
    dt = 1.0 / hz
    win = max(4, int(round(hz * WINDOW_SECONDS)))
    e = np.zeros(n)
    north = np.zeros(n)
    psi = np.zeros(n)
    if np.isfinite(heading_gnss[0]):
        psi[0] = float(heading_gnss[0]) + heading0_offset
    else:
        finite = heading_gnss[np.isfinite(heading_gnss)]
        psi[0] = (float(finite[0]) if finite.size else 0.0) + heading0_offset
    e[0] = e_gt[0] if np.isfinite(e_gt[0]) else 0.0
    north[0] = n_gt[0] if np.isfinite(n_gt[0]) else 0.0
    bg = 0.0

    for i in range(1, n):
        lo = max(0, i - win + 1)
        yaw_mean = float(np.mean(gz[lo : i + 1]))
        if aiding[i] and np.isfinite(heading_gnss[i]) and np.isfinite(heading_gnss[i - 1]):
            dpsi = _wrap_pi(float(heading_gnss[i]) - float(heading_gnss[i - 1])) / dt
            if abs(dpsi) < 0.08:
                bg = 0.95 * bg + 0.05 * (yaw_mean - dpsi)
        yaw_rate = yaw_scale * yaw_mean + gyro_bias - bg
        psi[i] = psi[i - 1] + yaw_rate * dt
        v = max(0.0, speed[i] * speed_scale)
        if aiding[i] and np.isfinite(e_gt[i]) and np.isfinite(n_gt[i]):
            e[i] = e_gt[i]
            north[i] = n_gt[i]
            if np.isfinite(heading_gnss[i]):
                psi[i] = float(heading_gnss[i])
        else:
            e[i] = e[i - 1] + v * np.sin(psi[i]) * dt
            north[i] = north[i - 1] + v * np.cos(psi[i]) * dt
    return e, north, psi


def _coast_outage(
    v: np.ndarray,
    gz: np.ndarray,
    e0: float,
    n0: float,
    psi0: float,
    dt: float,
) -> tuple[float, float]:
    e, north, psi = float(e0), float(n0), float(psi0)
    for i in range(len(v)):
        psi += float(gz[i]) * dt
        e += float(v[i]) * np.sin(psi) * dt
        north += float(v[i]) * np.cos(psi) * dt
    return e, north


def f8_measured_on_trace(
    e_gt: np.ndarray,
    n_gt: np.ndarray,
    heading: np.ndarray,
    gz: np.ndarray,
    outage: np.ndarray,
    hz: float = HZ,
) -> list[tuple[float, float]]:
    """Replay each F8 source in isolation on this outage (oracle speed/heading)."""
    if not outage.any():
        return [(0.0, 0.0)] * len(F8_ROWS)
    sl = slice(int(np.flatnonzero(outage)[0]), int(np.flatnonzero(outage)[-1]) + 1)
    dt = 1.0 / hz
    de = np.diff(e_gt[sl], prepend=e_gt[sl][0])
    dn = np.diff(n_gt[sl], prepend=n_gt[sl][0])
    v_gt = np.hypot(de, dn) / dt
    gz_gt = np.diff(np.unwrap(heading[sl]), prepend=heading[sl][0]) / dt
    if not np.isfinite(gz_gt).all():
        gz_gt = np.where(np.isfinite(gz[sl]), gz[sl], 0.0)
    e0, n0, psi0 = float(e_gt[sl][0]), float(n_gt[sl][0]), float(heading[sl][0])
    e1, n1 = float(e_gt[sl][-1]), float(n_gt[sl][-1])
    dist = float(np.sum(np.hypot(de, dn)))

    cases = (
        (v_gt * 1.05, gz_gt, psi0),
        (v_gt, gz_gt, psi0 + np.deg2rad(10.0)),
        (v_gt, gz_gt * float(np.cos(np.deg2rad(34.0))), psi0),
        (v_gt, gz_gt + np.deg2rad(0.3), psi0),
    )
    out: list[tuple[float, float]] = []
    for v, w, p0 in cases:
        ee, nn = _coast_outage(v, w, e0, n0, p0, dt)
        pos = float(np.hypot(ee - e1, nn - n1))
        out.append((pos, 100.0 * pos / max(dist, 1.0)))
    return out


def _path_length(e: np.ndarray, north: np.ndarray, sl: slice) -> float:
    de = np.diff(e[sl])
    dn = np.diff(north[sl])
    ok = np.isfinite(de) & np.isfinite(dn)
    return float(np.sum(np.hypot(de[ok], dn[ok])))


def infer(trace: dict) -> dict:
    t = trace["t"]
    lat, lon = trace["lat"], trace["lon"]
    finite = np.isfinite(lat) & np.isfinite(lon)
    if not finite.any():
        raise ValueError("no finite lat/lon")
    origin_lat = float(lat[finite][0])
    origin_lon = float(lon[finite][0])
    e_gt, n_gt = _lla_to_enu(lat, lon, origin_lat, origin_lon)
    e_gt = np.where(finite, e_gt, np.nan)
    n_gt = np.where(finite, n_gt, np.nan)
    e_gt = _nan_hold(e_gt)
    n_gt = _nan_hold(n_gt)

    outage = choose_outage(t, lat, lon, trace["gnss_ok"])
    aiding = (~outage) & finite

    heading = trace["heading_rad"].copy()
    path_hdg = np.arctan2(np.gradient(e_gt), np.gradient(n_gt))
    heading = np.where(np.isfinite(heading), heading, path_hdg)
    heading = _nan_hold(heading)

    speed_gnss = trace["speed_mps"].copy()
    if np.isfinite(speed_gnss).sum() < 8:
        speed_gnss = np.hypot(np.gradient(e_gt, t), np.gradient(n_gt, t))

    v_hat = windowed_velocity(
        trace["ax"], trace["ay"], trace["az"], trace["gz"], speed_gnss, aiding, hz=HZ
    )
    e_dr, n_dr, _psi_dr = dead_reckon(v_hat, trace["gz"], heading, e_gt, n_gt, aiding)

    err = np.hypot(e_dr - e_gt, n_dr - n_gt)
    dt_arr = np.diff(t, prepend=t[0])
    dt_arr[0] = 1.0 / HZ
    dist = np.cumsum(np.clip(v_hat, 0.0, None) * dt_arr)

    sl = slice(int(np.flatnonzero(outage)[0]), int(np.flatnonzero(outage)[-1]) + 1) if outage.any() else slice(0, None)
    outage_dist = _path_length(e_gt, n_gt, sl)
    outage_err = float(err[sl][-1]) if outage.any() else float(err[-1])
    measured_drift = 100.0 * outage_err / max(outage_dist, 1.0)
    measured = f8_measured_on_trace(e_gt, n_gt, heading, trace["gz"], outage)

    return {
        "t": t,
        "e_gt": e_gt,
        "n_gt": n_gt,
        "e_dr": e_dr,
        "n_dr": n_dr,
        "err": err,
        "dist": dist,
        "outage": outage,
        "aiding": aiding,
        "v_hat": v_hat,
        "outage_err_m": outage_err,
        "outage_dist_m": outage_dist,
        "measured_drift_pct": measured_drift,
        "f8_measured": measured,
        "window_samples": WINDOW_SAMPLES,
        "origin": (origin_lat, origin_lon),
    }


def _nan_hold(x: np.ndarray) -> np.ndarray:
    y = x.copy()
    last = 0.0
    have = False
    for i in range(len(y)):
        if np.isfinite(y[i]):
            last = y[i]
            have = True
        elif have:
            y[i] = last
    return y


def _style(ax) -> None:
    ax.set_facecolor("white")
    ax.grid(True, color=_GRID, linewidth=0.6, alpha=0.85)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(labelsize=8)


def _outage_span(ax, t, outage, which="x") -> None:
    if not outage.any():
        return
    i0 = int(np.flatnonzero(outage)[0])
    i1 = int(np.flatnonzero(outage)[-1])
    lo, hi = t[i0], t[i1]
    if which == "x":
        ax.axvspan(lo, hi, color=_OUT, alpha=0.28, zorder=0, label="GNSS outage")
    else:
        ax.axhspan(lo, hi, color=_OUT, alpha=0.28, zorder=0, label="GNSS outage")


def plot_traj(result: dict, source: str, dest: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 6.2), dpi=160)
    e, n = result["e_gt"], result["n_gt"]
    out = result["outage"]
    e_aid = e.copy()
    n_aid = n.copy()
    e_aid[out] = np.nan
    n_aid[out] = np.nan
    ax.plot(e_aid, n_aid, color=_GNSS, lw=2.0, label="GNSS (aided)")
    if out.any():
        ax.plot(e[out], n[out], color=_GNSS, lw=1.2, ls="--", alpha=0.85, label="GT during outage")
    e_coast = result["e_dr"].copy()
    n_coast = result["n_dr"].copy()
    e_coast[~out] = np.nan
    n_coast[~out] = np.nan
    ax.plot(e_coast, n_coast, color=_DR, lw=1.8, label="DR (10 Hz windowed v)")
    if out.any():
        i0 = int(np.flatnonzero(out)[0])
        ax.scatter([e[i0]], [n[i0]], c="#7b2d00", s=28, zorder=5, label="outage start")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("East (m)")
    ax.set_ylabel("North (m)")
    ax.set_title(f"GNSS vs dead reckoning\n{source} · {WINDOW_SAMPLES} samples / {WINDOW_SECONDS:.0f} s")
    _style(ax)
    ax.legend(frameon=False, fontsize=8, loc="best")
    fig.tight_layout()
    fig.savefig(dest, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_outage_zoom(result: dict, source: str, dest: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 6.2), dpi=160)
    out = result["outage"]
    if not out.any():
        out = np.ones(len(result["t"]), dtype=bool)
    pad = max(5, int(0.08 * np.count_nonzero(out)))
    idx = np.flatnonzero(out)
    lo = max(0, int(idx[0]) - pad)
    hi = min(len(out), int(idx[-1]) + 1)
    sl = slice(lo, hi)
    ax.plot(result["e_gt"][sl], result["n_gt"][sl], color=_GNSS, lw=2.0, label="GT / GNSS")
    ax.plot(result["e_dr"][out], result["n_dr"][out], color=_DR, lw=1.8, label="DR")
    ax.plot(result["e_gt"][out], result["n_gt"][out], color=_OUT, lw=3.2, alpha=0.45, zorder=0)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("East (m)")
    ax.set_ylabel("North (m)")
    err = result["outage_err_m"]
    dist = result["outage_dist_m"]
    ax.set_title(
        f"Outage zoom · {dist:.0f} m / {err:.1f} m error ({result['measured_drift_pct']:.2f}%)\n{source}"
    )
    _style(ax)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(dest, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_drift(result: dict, source: str, dest: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.6, 5.0), dpi=160)
    dist = result["dist"]
    err = result["err"]
    ax.plot(dist, err, color=_DR, lw=1.8, label="|DR − GT|")
    if result["outage"].any():
        ax.plot(dist[result["outage"]], err[result["outage"]], color="#7b2d00", lw=2.2, label="during outage")
    isro = 0.10 * np.maximum(dist, 1.0)
    ax.plot(dist, isro, color="#6b6b6b", ls=":", lw=1.2, label="ISRO 10% envelope")
    ax.set_xlabel("Distance travelled (m)")
    ax.set_ylabel("Position error (m)")
    ax.set_title(f"Drift vs distance · 10 Hz windows\n{source}")
    _style(ax)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(dest, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_error_budget(result: dict, source: str, dest: Path) -> None:
    labels = [row[0] for row in F8_ROWS]
    f8_pos = np.array([row[1] for row in F8_ROWS], dtype=np.float64)
    meas_pos = np.array([m[0] for m in result["f8_measured"]], dtype=np.float64)

    fig, ax = plt.subplots(figsize=(8.4, 5.4), dpi=160)
    y = np.arange(len(labels))
    h = 0.36
    ax.barh(y + h / 2, f8_pos, height=h, color="#5b7c99", label="F8 (sandbox)")
    ax.barh(y - h / 2, meas_pos, height=h, color=_DR, label="Measured (this trace)")
    for i, (f8, meas, row) in enumerate(zip(f8_pos, meas_pos, F8_ROWS)):
        ax.text(f8 + 2.0, i + h / 2, f"F8 {row[1]:.1f} m / {row[2]:.2f}%", va="center", fontsize=7, color="#2f2f2f")
        ax.text(meas + 2.0, i - h / 2, f"meas {meas:.1f} m / {result['f8_measured'][i][1]:.2f}%", va="center", fontsize=7, color="#7b2d00")
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("Position error (m)")
    ax.set_xlim(0, float(max(f8_pos.max(), meas_pos.max())) * 1.55)
    ax.set_title(f"Error budget [F8] · heading binds, not speed\n{source} · 10 Hz windows")
    _style(ax)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(dest, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def run(figures_dir: Path | None = None) -> dict:
    figures = Path(figures_dir) if figures_dir is not None else FIGURES_DIR
    figures.mkdir(parents=True, exist_ok=True)
    path, source = resolve_csv()
    try:
        result = infer(load_trace(path))
    except Exception as exc:  # noqa: BLE001 — fall back to fixture for proposal pack
        print(f"WARN: failed on {path} ({exc}); using fixture")
        from synthetic_iovnbd import write_csv

        path = write_csv()
        source = "IO-VNBD fixture (real CSV column map failed)"
        result = infer(load_trace(path))
    result["source"] = source
    result["csv_path"] = path
    plot_traj(result, source, figures / "traj_gnss_vs_dr.png")
    plot_outage_zoom(result, source, figures / "outage_zoom.png")
    plot_drift(result, source, figures / "drift_vs_distance.png")
    plot_error_budget(result, source, figures / "error_budget_bar.png")
    return result


def main() -> dict:
    result = run()
    print(
        f"source={result['source']}\n"
        f"csv={result['csv_path']}\n"
        f"window={result['window_samples']} samples @ {HZ} Hz\n"
        f"outage={result['outage_dist_m']:.1f} m  err={result['outage_err_m']:.2f} m  "
        f"drift={result['measured_drift_pct']:.2f}%\n"
        f"figures={FIGURES_DIR}"
    )
    return result


if __name__ == "__main__":
    main()
