"""Synthetic ConstraintManifold tests (corridor + dual-manifold lateral bound)."""

from __future__ import annotations

import json
import math
import sys
import unittest
from pathlib import Path

import numpy as np

_NAV = Path(__file__).resolve().parents[1] / "lab" / "nav"
if str(_NAV) not in sys.path:
    sys.path.insert(0, str(_NAV))

from manifold import (  # noqa: E402
    CorridorManifold,
    ManifoldParticleFilter,
    ManifoldState,
    RoadGraphManifold,
)


EARTH_R_M = 6_371_008.8
ORIGIN = (12.9912, 77.5523)


def _enu_to_lla(e: float, n: float, origin: tuple[float, float] = ORIGIN) -> tuple[float, float]:
    lat0, lon0 = origin
    lat = lat0 + math.degrees(n / EARTH_R_M)
    lon = lon0 + math.degrees(e / (EARTH_R_M * max(math.cos(math.radians(lat0)), 1e-9)))
    return lat, lon


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dn = math.radians(lat2 - lat1) * EARTH_R_M
    de = math.radians(lon2 - lon1) * EARTH_R_M * math.cos(math.radians(lat1))
    return math.hypot(de, dn)


class _TinyRoadGraph:
    """Minimal stand-in so RoadGraphManifold can be exercised without OSM NPZ."""

    def __init__(self) -> None:
        # Two-node eastbound edge, ~200 m.
        a = _enu_to_lla(0.0, 0.0)
        b = _enu_to_lla(200.0, 0.0)
        self.node_lat = np.array([a[0], b[0]], dtype=np.float64)
        self.node_lon = np.array([a[1], b[1]], dtype=np.float64)
        self.edge_ptr = np.array([0, 2], dtype=np.int64)
        self.edge_nodes = np.array([0, 1], dtype=np.int64)
        self.edge_u = np.array([0], dtype=np.int64)
        self.edge_v = np.array([1], dtype=np.int64)
        self.edge_len_m = np.array([200.0], dtype=np.float64)
        self.edge_bearing_deg = np.array([90.0], dtype=np.float64)
        self.adj_ptr = np.array([0, 0, 0], dtype=np.int64)
        self.adj_edge = np.array([], dtype=np.int64)
        self.n_edges = 1
        self.grid_ptr = np.array([0, 1], dtype=np.int64)
        self.grid_edge = np.array([0], dtype=np.int64)
        self.grid_lat0 = ORIGIN[0] - 0.01
        self.grid_lon0 = ORIGIN[1] - 0.01
        self.grid_deg = 0.05
        self.grid_n_lat = 4
        self.grid_n_lon = 4

    def nearby_edges(self, lat: float, lon: float, radius_m: float) -> np.ndarray:
        return np.array([0], dtype=np.int64)

    def project(self, edge: int, lat: float, lon: float) -> tuple[float, float, float, float, float]:
        # Delegate to a one-segment ENU projection matching MapGraph semantics.
        a0, a1 = float(self.node_lat[0]), float(self.node_lon[0])
        b0, b1 = float(self.node_lat[1]), float(self.node_lon[1])
        clat = math.cos(math.radians(lat))
        ax = (a1 - lon) * EARTH_R_M * math.radians(1.0) * clat
        ay = (a0 - lat) * EARTH_R_M * math.radians(1.0)
        bx = (b1 - lon) * EARTH_R_M * math.radians(1.0) * clat
        by = (b0 - lat) * EARTH_R_M * math.radians(1.0)
        vx, vy = bx - ax, by - ay
        seg_len = math.hypot(vx, vy)
        t = 0.0 if seg_len < 1e-9 else max(0.0, min(1.0, -(ax * vx + ay * vy) / (seg_len * seg_len)))
        cx, cy = ax + t * vx, ay + t * vy
        d = math.hypot(cx, cy)
        out_lat = lat + math.degrees(cy / EARTH_R_M)
        out_lon = lon + math.degrees(cx / (EARTH_R_M * max(clat, 1e-9)))
        bearing = math.degrees(math.atan2(vx, vy)) % 360.0
        return out_lat, out_lon, d, t * seg_len, bearing


class ManifoldTests(unittest.TestCase):
    def test_corridor_clamps_and_bounds_filter(self) -> None:
        poly = [_enu_to_lla(i * 20.0, 0.0) for i in range(11)]
        corridor = CorridorManifold(poly, 3.0, origin=ORIGIN)
        self.assertEqual(corridor.dim(), 1)
        self.assertTrue(190.0 < corridor.length_m() < 210.0)

        off = _enu_to_lla(100.0, 8.0)
        snapped = corridor.project(ManifoldState(lat=off[0], lon=off[1], yaw_deg=90.0))
        residual = _haversine(off[0], off[1], snapped.lat, snapped.lon)
        self.assertTrue(4.5 < residual < 5.5, residual)
        self.assertLessEqual(abs(snapped.lateral_m), 3.0 + 1e-9)

        pf = ManifoldParticleFilter(corridor, n=48, seed=7)
        pf.seed(poly[0][0], poly[0][1], 90.0)
        max_lat = 0.0
        for _ in range(40):
            pf.step(0.5, 10.0, 90.0)
            est = pf.estimate()
            max_lat = max(max_lat, pf.lateral_error_m(est.lat, est.lon))
        self.assertLess(max_lat, 3.5, max_lat)

    def test_dual_manifold_lateral_semantics(self) -> None:
        g = _TinyRoadGraph()
        road = RoadGraphManifold(g)
        self.assertEqual(road.dim(), 1)

        poly = [_enu_to_lla(i * 25.0, 0.0) for i in range(9)]
        corridor = CorridorManifold(poly, 4.0, origin=ORIGIN)

        start = poly[0]
        road_pf = ManifoldParticleFilter(road, n=32, seed=11)
        corr_pf = ManifoldParticleFilter(corridor, n=32, seed=11)
        road_pf.seed(start[0], start[1], 90.0)
        corr_pf.seed(start[0], start[1], 90.0)

        max_road = 0.0
        max_corr = 0.0
        max_corr_lat = 0.0
        for k in range(30):
            free = _enu_to_lla(8.0 * k, 5.0 + 0.2 * k)
            road_pf.step(0.4, 12.0, 90.0)
            corr_pf.step(0.4, 12.0, 90.0)
            re = road_pf.estimate()
            ce = corr_pf.estimate()
            max_road = max(max_road, road_pf.lateral_error_m(re.lat, re.lon))
            max_corr = max(max_corr, corr_pf.lateral_error_m(ce.lat, ce.lon))
            cp = corridor.project(ManifoldState(lat=free[0], lon=free[1], yaw_deg=90.0))
            max_corr_lat = max(max_corr_lat, abs(cp.lateral_m))

        self.assertLess(max_road, 1.0, max_road)
        self.assertLess(max_corr, 4.5, max_corr)
        self.assertLessEqual(max_corr_lat, 4.0 + 1e-6, max_corr_lat)

    def test_mapfilter_headline_unchanged(self) -> None:
        """Committed mapfilter numbers must remain the shipping headline (2.02×)."""
        report = Path(__file__).resolve().parents[1] / "lab" / "stress" / "results" / "mapfilter" / "report.json"
        data = json.loads(report.read_text(encoding="utf-8"))
        junc = data["scenarios"]["junctions"]
        self.assertAlmostEqual(junc["improvement_x"], 2.018070842498746, places=12)
        self.assertAlmostEqual(junc["pf_median_error_m"], 125.19966812248491, places=12)
        self.assertAlmostEqual(junc["free_median_error_m"], 252.6617997285065, places=12)


if __name__ == "__main__":
    unittest.main()
