"""
SIH26168 evaluation metrics — implement before any model (PROJECT_BIBLE §5.9).

All functions are NumPy-only. Same arrays in → same scalars out (no RNG here).

Coordinate frame
----------------
Planar ENU metres unless noted: ``x`` = east, ``y`` = north.
Heading ``yaw`` is navigation-style: 0 faces north, +π/2 faces east,
so  v_e = speed * sin(yaw),  v_n = speed * cos(yaw).
Lat/lon inputs are converted with a local tangent plane at the first fix.

Metrics
-------
* **Loop closure error** — |p_end − p_start| (or |p_end − marker|).
  Zero-infrastructure ground truth: ride back to a painted mark.
* **Drift %** — final error / distance travelled × 100. ISRO bar: < 10 %.
* **ATE** — RMSE of absolute position (optional SE(2) Umeyama align).
* **RTE** — KITTI-style relative translation on 100–900 m subsequences
  (Geiger, Lenz, Urtasun, CVPR 2012).
* **Error CDF** — percentile position error (tails, not means).
* **Branch-decision accuracy [F12]** — fraction of junctions where the
  correct graph edge was chosen. The metric the rider actually feels.
* **Lean RMSE** — two-wheeler module health, reported in degrees.
* **On-device latency** — placeholder until Android NAVIGATE logs exist.
  Requirement: 10 Hz sustained.
"""

from __future__ import annotations

from typing import Iterable, Mapping, Sequence

import numpy as np

G = 9.80665
"""Standard gravity, m/s² (same constant as core/ts)."""

KITTI_LENGTHS_M: tuple[int, ...] = (100, 200, 300, 400, 500, 600, 700, 800, 900)
"""KITTI odometry subsequence lengths. Bible §5.9 asks 100–900 m."""

_DEFAULT_PERCENTILES: tuple[int, ...] = (50, 75, 90, 95, 99)

# WGS-84 metres-per-degree at the equator; refined by cos(lat) for east.
_M_PER_DEG_LAT = 111_132.92
_M_PER_DEG_LON_EQ = 111_412.84


def _as_xy(points: np.ndarray) -> np.ndarray:
    """Coerce (N, 2) float64. Accepts (N, 2+) and drops extra columns."""
    p = np.asarray(points, dtype=np.float64)
    if p.ndim != 2 or p.shape[1] < 2:
        raise ValueError(f"expected (N, 2) positions, got shape {p.shape}")
    return np.ascontiguousarray(p[:, :2])


def _finite_pairs(
    est: np.ndarray, gt: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    est = _as_xy(est)
    gt = _as_xy(gt)
    n = min(len(est), len(gt))
    if n == 0:
        return est[:0], gt[:0]
    e = est[:n]
    g = gt[:n]
    mask = np.isfinite(e).all(axis=1) & np.isfinite(g).all(axis=1)
    return e[mask], g[mask]


def wrap_pi(angle: np.ndarray | float) -> np.ndarray:
    """Wrap to (−π, π]. Vectorised; matches the TS while-loop for normal values."""
    a = np.asarray(angle, dtype=np.float64)
    return (a + np.pi) % (2.0 * np.pi) - np.pi


def lla_to_enu(
    lat_deg: np.ndarray,
    lon_deg: np.ndarray,
    origin_lat_deg: float | None = None,
    origin_lon_deg: float | None = None,
) -> np.ndarray:
    """Geographic degrees → local east/north metres at the first sample."""
    lat = np.asarray(lat_deg, dtype=np.float64).ravel()
    lon = np.asarray(lon_deg, dtype=np.float64).ravel()
    if lat.size != lon.size:
        raise ValueError("lat and lon must have the same length")
    lat0 = float(lat[0] if origin_lat_deg is None else origin_lat_deg)
    lon0 = float(lon[0] if origin_lon_deg is None else origin_lon_deg)
    c = np.cos(np.deg2rad(lat0))
    east = (lon - lon0) * _M_PER_DEG_LON_EQ * c
    north = (lat - lat0) * _M_PER_DEG_LAT
    return np.column_stack([east, north])


def path_length(positions: np.ndarray) -> float:
    """Distance travelled: sum of consecutive Euclidean steps, metres."""
    p = _as_xy(positions)
    if len(p) < 2:
        return 0.0
    step = np.linalg.norm(np.diff(p, axis=0), axis=1)
    return float(np.sum(step, where=np.isfinite(step)))


def cumulative_distance(positions: np.ndarray) -> np.ndarray:
    """Inclusive prefix path length, shape (N,). ``out[0] = 0``."""
    p = _as_xy(positions)
    out = np.zeros(len(p), dtype=np.float64)
    if len(p) < 2:
        return out
    out[1:] = np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))
    return out


def loop_closure_error(
    positions: np.ndarray | None = None,
    *,
    p_end: np.ndarray | None = None,
    p_start: np.ndarray | None = None,
    marker: np.ndarray | None = None,
) -> float:
    """
    |p_end − p_start| in metres.

    Pass either a trajectory ``positions`` (uses last vs first / marker)
    or explicit endpoints. A painted loop-closure mark overrides p_start
    when provided — that is the self-labelling protocol in §6.
    """
    if p_end is None or (p_start is None and marker is None):
        if positions is None:
            raise ValueError("pass positions or p_end and p_start/marker")
        p = _as_xy(positions)
        if len(p) == 0:
            return float("inf")
        p_end = p[-1]
        p_start = p[0] if p_start is None else np.asarray(p_start, dtype=np.float64)
    end = np.asarray(p_end, dtype=np.float64).ravel()[:2]
    start = np.asarray(
        marker if marker is not None else p_start, dtype=np.float64
    ).ravel()[:2]
    if not (np.isfinite(end).all() and np.isfinite(start).all()):
        return float("inf")
    return float(np.linalg.norm(end - start))


def drift_pct(error_m: float, distance_m: float) -> float:
    """
    Final error ÷ distance travelled, as a percent.

    ISRO benchmark: < 10 %. Distance below 1 m → 0 (undefined ratio),
    matching core/ts ``driftPct``.
    """
    err = float(error_m)
    dist = float(distance_m)
    if not np.isfinite(err) or not np.isfinite(dist) or dist < 1.0:
        return 0.0
    return 100.0 * err / dist


def position_errors(est: np.ndarray, gt: np.ndarray) -> np.ndarray:
    """Per-timestep |p_est − p_gt| in metres. Truncated to the shared length."""
    e, g = _finite_pairs(est, gt)
    if len(e) == 0:
        return np.zeros(0, dtype=np.float64)
    return np.linalg.norm(e - g, axis=1)


def _umeyama_se2(est: np.ndarray, gt: np.ndarray) -> np.ndarray:
    """
    Least-squares rigid SE(2) alignment of ``est`` onto ``gt`` (no scale).

    Umeyama (1991) in 2-D. Default ATE does **not** align — same-frame
    comparison is what makes car-style vs lean-aware numbers comparable.
    """
    src = _as_xy(est)
    dst = _as_xy(gt)
    n = min(len(src), len(dst))
    src = src[:n]
    dst = dst[:n]
    mu_s = src.mean(axis=0)
    mu_d = dst.mean(axis=0)
    src_c = src - mu_s
    dst_c = dst - mu_d
    cov = (dst_c.T @ src_c) / n
    u, _, vt = np.linalg.svd(cov)
    r = u @ vt
    if np.linalg.det(r) < 0.0:
        u = u.copy()
        u[:, -1] *= -1.0
        r = u @ vt
    t = mu_d - r @ mu_s
    return (r @ src.T).T + t


def ate(est: np.ndarray, gt: np.ndarray, *, align: bool = False) -> float:
    """
    Absolute Trajectory Error: RMSE of position, metres.

    KITTI's published table is relative; the TUM RGB-D ATE (Sturm et al.)
    is RMSE after alignment. We default to **same-frame** RMSE so two
    integrators that ate the same IMU stay comparable (golden rule).
    Set ``align=True`` for a rigid SE(2) fit before RMSE.
    """
    e, g = _finite_pairs(est, gt)
    if len(e) == 0:
        return 0.0
    if align:
        e = _umeyama_se2(e, g)
    sq = np.sum((e - g) ** 2, axis=1)
    return float(np.sqrt(np.mean(sq)))


def _to_std_se2(x: float, y: float, yaw: float) -> tuple[float, float, float]:
    """Nav yaw (0 = north) → standard SE(2) θ from +east toward +north."""
    return float(x), float(y), float(np.pi / 2.0 - yaw)


def _se2_inv(pose: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, th = pose
    c = np.cos(th)
    s = np.sin(th)
    return (-c * x - s * y, s * x - c * y, -th)


def _se2_mul(
    a: tuple[float, float, float], b: tuple[float, float, float]
) -> tuple[float, float, float]:
    xa, ya, ta = a
    xb, yb, tb = b
    c = np.cos(ta)
    s = np.sin(ta)
    return (xa + c * xb - s * yb, ya + s * xb + c * yb, ta + tb)


def _relative_trans_rot(
    est: np.ndarray,
    gt: np.ndarray,
    yaw_est: np.ndarray | None,
    yaw_gt: np.ndarray | None,
    i: int,
    j: int,
) -> tuple[float, float]:
    """KITTI pose-error translation (m) and rotation (rad) from i → j."""
    if yaw_est is None or yaw_gt is None:
        d_est = est[j] - est[i]
        d_gt = gt[j] - gt[i]
        return float(np.linalg.norm(d_est - d_gt)), 0.0
    pe_i = _to_std_se2(est[i, 0], est[i, 1], float(yaw_est[i]))
    pe_j = _to_std_se2(est[j, 0], est[j, 1], float(yaw_est[j]))
    pg_i = _to_std_se2(gt[i, 0], gt[i, 1], float(yaw_gt[i]))
    pg_j = _to_std_se2(gt[j, 0], gt[j, 1], float(yaw_gt[j]))
    d_est = _se2_mul(_se2_inv(pe_i), pe_j)
    d_gt = _se2_mul(_se2_inv(pg_i), pg_j)
    err = _se2_mul(_se2_inv(d_est), d_gt)
    trans = float(np.hypot(err[0], err[1]))
    rot = float(np.abs(wrap_pi(err[2])))
    return trans, rot


def rte_kitti(
    est: np.ndarray,
    gt: np.ndarray,
    *,
    lengths_m: Sequence[float] = KITTI_LENGTHS_M,
    yaw_est: np.ndarray | None = None,
    yaw_gt: np.ndarray | None = None,
    step: int = 1,
) -> dict:
    """
    KITTI-style relative translational / rotational error.

    For every start index ``i`` and every length ``L`` in 100, 200, …, 900 m,
    find the first ``j`` whose ground-truth path length from ``i`` is ≥ L.
    Compare the relative SE(2) pose ``i → j`` of estimate vs truth:

        E = inv(inv(P_i) P_j) · (inv(Q_i) Q_j)

    Translation error is |trans(E)|; we also report it as % of L.
    Rotation error is |angle(E)| / L in deg/m (0 if yaw arrays omitted).

    Returns a dict with per-length means, overall means, and window counts.
    Lengths with no window yield NaN — a 40 m toy path must not invent a
    900 m number.
    """
    e, g = _finite_pairs(est, gt)
    n = len(g)
    empty = {
        "lengths_m": list(lengths_m),
        "trans_m": {float(L): float("nan") for L in lengths_m},
        "trans_pct": {float(L): float("nan") for L in lengths_m},
        "rot_deg_per_m": {float(L): float("nan") for L in lengths_m},
        "n_windows": {float(L): 0 for L in lengths_m},
        "rte_m": float("nan"),
        "rte_pct": float("nan"),
        "rte_rot_deg_per_m": float("nan"),
    }
    if n < 2:
        return empty

    ye = None if yaw_est is None else np.asarray(yaw_est, dtype=np.float64)[:n]
    yg = None if yaw_gt is None else np.asarray(yaw_gt, dtype=np.float64)[:n]
    if ye is not None and len(ye) < n:
        ye = None
    if yg is not None and len(yg) < n:
        yg = None

    cum = cumulative_distance(g)
    trans_m: dict[float, float] = {}
    trans_pct: dict[float, float] = {}
    rot_dpm: dict[float, float] = {}
    counts: dict[float, int] = {}
    all_t: list[float] = []
    all_pct: list[float] = []
    all_r: list[float] = []

    for L in lengths_m:
        L = float(L)
        ts: list[float] = []
        rs: list[float] = []
        for i in range(0, n, max(1, int(step))):
            target = cum[i] + L
            if target > cum[-1] + 1e-9:
                continue
            j = int(np.searchsorted(cum, target, side="left"))
            if j >= n or j <= i:
                continue
            t_err, r_err = _relative_trans_rot(e, g, ye, yg, i, j)
            ts.append(t_err)
            rs.append(r_err)
        counts[L] = len(ts)
        if ts:
            trans_m[L] = float(np.mean(ts))
            trans_pct[L] = float(100.0 * np.mean(np.asarray(ts) / L))
            rot_dpm[L] = float(np.rad2deg(np.mean(rs)) / L)
            all_t.extend(ts)
            all_pct.extend(float(100.0 * t / L) for t in ts)
            all_r.extend(float(np.rad2deg(r) / L) for r in rs)
        else:
            trans_m[L] = float("nan")
            trans_pct[L] = float("nan")
            rot_dpm[L] = float("nan")

    return {
        "lengths_m": [float(L) for L in lengths_m],
        "trans_m": trans_m,
        "trans_pct": trans_pct,
        "rot_deg_per_m": rot_dpm,
        "n_windows": counts,
        "rte_m": float(np.mean(all_t)) if all_t else float("nan"),
        "rte_pct": float(np.mean(all_pct)) if all_pct else float("nan"),
        "rte_rot_deg_per_m": float(np.mean(all_r)) if all_r else float("nan"),
    }


def error_cdf(
    errors: np.ndarray | Sequence[float],
    percentiles: Sequence[float] = _DEFAULT_PERCENTILES,
) -> dict[str, float]:
    """
    Empirical CDF of position error, as percentile → metres.

    Tails matter more than the mean: a 95th-percentile blow-up is a missed
    ramp. Uses ``numpy.quantile`` (linear). Empty input → NaNs.
    """
    e = np.asarray(errors, dtype=np.float64).ravel()
    e = e[np.isfinite(e)]
    out: dict[str, float] = {}
    for p in percentiles:
        key = f"p{int(round(float(p)))}"
        if e.size == 0:
            out[key] = float("nan")
        else:
            out[key] = float(np.quantile(e, float(p) / 100.0))
    return out


def branch_decision_accuracy(
    predicted: Sequence[object],
    truth: Sequence[object],
) -> float:
    """
    [F12] Fraction of junctions where the correct graph edge was chosen.

    This is the metric the field is missing. Drift % is a paper number;
    the rider experiences "did I take the right ramp." Empty → 0.
    """
    n = min(len(predicted), len(truth))
    if n == 0:
        return 0.0
    ok = 0
    for i in range(n):
        if predicted[i] == truth[i]:
            ok += 1
    return ok / n


def lean_rmse(
    est_rad: np.ndarray | Sequence[float],
    gt_rad: np.ndarray | Sequence[float],
) -> float:
    """
    Lean RMSE in **degrees** (inputs in radians).

    Two-wheeler module health. F5 claims 0.5–1.0° on coordinated-turn
    simulation. Angle error is **not** wrapped — lean lives in (−π/2, π/2).
    """
    a = np.asarray(est_rad, dtype=np.float64).ravel()
    b = np.asarray(gt_rad, dtype=np.float64).ravel()
    n = min(a.size, b.size)
    if n == 0:
        return 0.0
    d_deg = np.rad2deg(a[:n] - b[:n])
    mask = np.isfinite(d_deg)
    if not np.any(mask):
        return float("nan")
    return float(np.sqrt(np.mean(d_deg[mask] ** 2)))


def on_device_latency(
    sample_ms: np.ndarray | Sequence[float] | None = None,
    *,
    required_hz: float = 10.0,
) -> dict[str, float | bool | str | None]:
    """
    On-device inference latency. **Placeholder** until NAVIGATE logs exist.

    Pass a vector of per-inference milliseconds from the phone. With no
    samples this returns NaNs and a note — do not invent a 10 Hz claim.
    """
    note = (
        "placeholder: no on-device inference timestamps yet; "
        f"ISRO / bible require {required_hz:.0f} Hz sustained"
    )
    if sample_ms is None:
        return {
            "latency_ms": float("nan"),
            "hz_sustained": float("nan"),
            "meets_10hz": False,
            "n": 0,
            "note": note,
        }
    s = np.asarray(sample_ms, dtype=np.float64).ravel()
    s = s[np.isfinite(s) & (s > 0.0)]
    if s.size == 0:
        return {
            "latency_ms": float("nan"),
            "hz_sustained": float("nan"),
            "meets_10hz": False,
            "n": 0,
            "note": note,
        }
    med = float(np.median(s))
    hz = 1000.0 / med if med > 0.0 else float("nan")
    return {
        "latency_ms": med,
        "hz_sustained": float(hz),
        "meets_10hz": bool(np.isfinite(hz) and hz >= required_hz),
        "n": int(s.size),
        "note": "median inference time from provided device samples",
    }


def summarize(
    est: np.ndarray,
    gt: np.ndarray,
    *,
    marker: np.ndarray | None = None,
    yaw_est: np.ndarray | None = None,
    yaw_gt: np.ndarray | None = None,
    branches: tuple[Sequence[object], Sequence[object]] | None = None,
    lean: tuple[np.ndarray | Sequence[float], np.ndarray | Sequence[float]]
    | None = None,
    sample_ms: np.ndarray | Sequence[float] | None = None,
    align_ate: bool = False,
) -> dict:
    """
    Full §5.9 bundle. Distance is always measured on **ground truth**
    (falls back to the estimate if GT is empty) so two methods on the
    same ride share a denominator.
    """
    e = _as_xy(est) if len(np.asarray(est)) else np.zeros((0, 2))
    g = _as_xy(gt) if len(np.asarray(gt)) else np.zeros((0, 2))
    dist_src = g if len(g) else e
    distance = path_length(dist_src)
    lc = loop_closure_error(e, marker=marker)
    errs = position_errors(e, g) if len(g) and len(e) else np.zeros(0)
    rte = rte_kitti(e, g, yaw_est=yaw_est, yaw_gt=yaw_gt) if len(g) else rte_kitti(
        e, e
    )
    lat = on_device_latency(sample_ms)
    return {
        "loop_closure_m": lc,
        "distance_m": distance,
        "drift_pct": drift_pct(lc, distance),
        "ate_m": ate(e, g, align=align_ate) if len(g) else float("nan"),
        "rte_m": rte["rte_m"],
        "rte_pct": rte["rte_pct"],
        "rte": rte,
        "error_cdf": error_cdf(errs),
        "errors_m": errs,
        "branch_accuracy": (
            branch_decision_accuracy(branches[0], branches[1])
            if branches is not None
            else 0.0
        ),
        "lean_rmse_deg": lean_rmse(lean[0], lean[1]) if lean is not None else float("nan"),
        "latency_ms": lat["latency_ms"],
        "latency_hz": lat["hz_sustained"],
        "latency": lat,
    }


def jsonable(obj: object) -> object:
    """Convert numpy scalars / arrays inside a report to JSON types."""
    if isinstance(obj, dict):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsonable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [jsonable(v) for v in obj.tolist()]
    if isinstance(obj, (np.floating, np.integer)):
        val = float(obj) if isinstance(obj, np.floating) else int(obj)
        if isinstance(val, float) and not np.isfinite(val):
            return None
        return val
    if isinstance(obj, float) and not np.isfinite(obj):
        return None
    if isinstance(obj, Mapping):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, Iterable) and not isinstance(obj, (str, bytes)):
        return [jsonable(v) for v in obj]
    return obj


if __name__ == "__main__":
    # Deterministic sanity: a 3-4-5 triangle, then a closed square.
    gt = np.array([[0.0, 0.0], [3.0, 0.0], [3.0, 4.0]], dtype=np.float64)
    est = gt.copy()
    assert abs(path_length(gt) - 7.0) < 1e-12
    assert loop_closure_error(gt) == 5.0
    assert abs(drift_pct(5.0, 7.0) - 100.0 * 5.0 / 7.0) < 1e-12
    assert ate(est, gt) == 0.0
    assert branch_decision_accuracy(["a", "b"], ["a", "c"]) == 0.5
    assert abs(lean_rmse([0.0], [0.0]) ) < 1e-12
    print("metrics.py self-check ok")
