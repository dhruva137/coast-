"""ConstraintManifold — map constraint as a plug-in [Phase 2 / F2].

``RoadGraphManifold`` wraps ``MapGraph`` projection / neighbour geometry used by
the shipping road-constrained particle filter. Numeric mapfilter outputs are
unchanged: ``RoadParticleFilter`` still calls ``MapGraph`` directly; this module
exposes the same operations behind a domain-general interface.

``CorridorManifold`` is a **synthetic demonstration only** (1-D polyline +
lateral tolerance). It is not field-validated for rail, undersea, or planetary
navigation.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from typing import Any, Sequence

import numpy as np

EARTH_R_M = 6_371_008.8


@dataclass
class ManifoldState:
    lat: float = 0.0
    lon: float = 0.0
    alt: float = 0.0
    yaw_deg: float = 0.0
    edge_id: str = ""
    s: float = 0.0
    lateral_m: float = 0.0
    # OSM edge index when wrapping MapGraph (avoids string round-trips).
    edge: int = -1


class ConstraintManifold(ABC):
    @abstractmethod
    def project(self, state: ManifoldState) -> ManifoldState: ...

    @abstractmethod
    def neighbours(self, state: ManifoldState, distance_m: float) -> list[ManifoldState]: ...

    @abstractmethod
    def transition_cost(self, a: ManifoldState, b: ManifoldState) -> float: ...

    @abstractmethod
    def dim(self) -> int: ...


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dn = math.radians(lat2 - lat1) * EARTH_R_M
    de = math.radians(lon2 - lon1) * EARTH_R_M * math.cos(math.radians(lat1))
    return math.hypot(de, dn)


def _circ_diff_abs(a: float, b: float) -> float:
    d = (a - b + 180.0) % 360.0 - 180.0
    return abs(d)


class RoadGraphManifold(ConstraintManifold):
    """Existing OSM / MapGraph geometry behind the ConstraintManifold interface."""

    def __init__(self, graph: Any) -> None:
        self.g = graph

    def dim(self) -> int:
        return 1

    def project(self, state: ManifoldState) -> ManifoldState:
        out = ManifoldState(
            lat=state.lat,
            lon=state.lon,
            alt=state.alt,
            yaw_deg=state.yaw_deg,
            edge_id=state.edge_id,
            s=state.s,
            lateral_m=0.0,
            edge=state.edge,
        )
        edges = self.g.nearby_edges(state.lat, state.lon, 80.0)
        if edges.size == 0:
            return out
        best_score = float("inf")
        best: tuple[int, float, float, float, float, float] | None = None
        for e in edges:
            e = int(e)
            plat, plon, d, along, bearing = self.g.project(e, state.lat, state.lon)
            if not math.isfinite(d):
                continue
            dH = _circ_diff_abs(bearing, state.yaw_deg)
            score = d + 0.15 * dH
            if score < best_score:
                best_score = score
                best = (e, plat, plon, d, along, bearing)
        if best is None:
            return out
        e, plat, plon, _d, along, bearing = best
        total = float(self.g.edge_len_m[e])
        out.lat = plat
        out.lon = plon
        out.edge = e
        out.edge_id = str(e)
        out.s = along / max(total, 1e-9)
        out.yaw_deg = bearing
        out.lateral_m = 0.0
        return out

    def neighbours(self, state: ManifoldState, distance_m: float) -> list[ManifoldState]:
        e = state.edge if state.edge >= 0 else (int(state.edge_id) if state.edge_id.isdigit() else -1)
        if e < 0:
            out: list[ManifoldState] = []
            for ne in self.g.nearby_edges(state.lat, state.lon, max(distance_m, 40.0))[:8]:
                ne = int(ne)
                plat, plon, _, _, bearing = self.g.project(ne, state.lat, state.lon)
                out.append(
                    ManifoldState(
                        lat=plat,
                        lon=plon,
                        yaw_deg=bearing,
                        edge=ne,
                        edge_id=str(ne),
                        s=0.0,
                    )
                )
            return out
        total = float(self.g.edge_len_m[e])
        remain = (1.0 - state.s) * total
        if remain >= distance_m:
            s = min(state.s + distance_m / max(total, 1e-9), 0.999)
            # Re-project along edge by walking from u toward v.
            plat, plon, _, _, bearing = self.g.project(e, state.lat, state.lon)
            # Approximate: move toward edge end.
            u = int(self.g.edge_u[e])
            v = int(self.g.edge_v[e])
            lat = float(self.g.node_lat[u]) + s * (float(self.g.node_lat[v]) - float(self.g.node_lat[u]))
            lon = float(self.g.node_lon[u]) + s * (float(self.g.node_lon[v]) - float(self.g.node_lon[u]))
            return [
                ManifoldState(
                    lat=lat,
                    lon=lon,
                    yaw_deg=float(self.g.edge_bearing_deg[e]),
                    edge=e,
                    edge_id=str(e),
                    s=s,
                )
            ]
        # Junction: adjacent edges from v.
        node = int(self.g.edge_v[e])
        out = []
        for k in range(int(self.g.adj_ptr[node]), int(self.g.adj_ptr[node + 1])):
            code = int(self.g.adj_edge[k])
            fwd = code < self.g.n_edges
            ne = code if fwd else code - self.g.n_edges
            if ne == e:
                continue
            u = int(self.g.edge_u[ne]) if fwd else int(self.g.edge_v[ne])
            out.append(
                ManifoldState(
                    lat=float(self.g.node_lat[u]),
                    lon=float(self.g.node_lon[u]),
                    yaw_deg=float(self.g.edge_bearing_deg[ne]) if fwd else (float(self.g.edge_bearing_deg[ne]) + 180.0) % 360.0,
                    edge=ne,
                    edge_id=str(ne),
                    s=0.0,
                )
            )
        return out or [
            ManifoldState(
                lat=state.lat,
                lon=state.lon,
                yaw_deg=state.yaw_deg,
                edge=e,
                edge_id=str(e),
                s=0.999,
            )
        ]

    def transition_cost(self, a: ManifoldState, b: ManifoldState) -> float:
        return _haversine_m(a.lat, a.lon, b.lat, b.lon) + 0.05 * _circ_diff_abs(a.yaw_deg, b.yaw_deg)


class CorridorManifold(ConstraintManifold):
    """1-D polyline + hard lateral tolerance.

    SYNTHETIC DEMO ONLY — not field-validated for rail / channel / planetary use.
    """

    def __init__(
        self,
        polyline: Sequence[tuple[float, float]] | np.ndarray,
        lateral_tol_m: float,
        *,
        origin: tuple[float, float] | None = None,
    ) -> None:
        pts = [(float(p[0]), float(p[1])) for p in polyline]
        if len(pts) < 2:
            raise ValueError("CorridorManifold needs >= 2 polyline vertices")
        self.poly = pts
        self.lateral_tol_m = max(0.1, float(lateral_tol_m))
        self.origin = origin or pts[0]
        self._segs: list[tuple[tuple[float, float], tuple[float, float], float, float, float]] = []
        cum = 0.0
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            length = _haversine_m(a[0], a[1], b[0], b[1])
            if length < 1e-6:
                length = 1e-6
            cum += length
            de = math.radians(b[1] - a[1]) * EARTH_R_M * math.cos(math.radians(a[0]))
            dn = math.radians(b[0] - a[0]) * EARTH_R_M
            heading = math.degrees(math.atan2(de, dn)) % 360.0
            self._segs.append((a, b, length, cum, heading))
        self.total_m = cum

    def dim(self) -> int:
        return 1

    def length_m(self) -> float:
        return self.total_m

    def point_at(self, s_m: float) -> tuple[float, float]:
        s_m = min(max(s_m, 0.0), self.total_m)
        for i, (a, b, length, cum, _) in enumerate(self._segs):
            start = cum - length
            if s_m <= cum or i == len(self._segs) - 1:
                u = (s_m - start) / length
                return a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u
        return self.poly[-1]

    def project(self, state: ManifoldState) -> ManifoldState:
        best_d = float("inf")
        best_s_m = 0.0
        best_lat = 0.0
        best_h = 0.0
        best_i = 0
        olat, olon = self.origin
        for i, (a, b, length, cum, heading) in enumerate(self._segs):
            clat0 = math.cos(math.radians(olat))
            pae = (a[1] - olon) * EARTH_R_M * math.radians(1.0) * clat0
            pan = (a[0] - olat) * EARTH_R_M * math.radians(1.0)
            pbe = (b[1] - olon) * EARTH_R_M * math.radians(1.0) * clat0
            pbn = (b[0] - olat) * EARTH_R_M * math.radians(1.0)
            pqe = (state.lon - olon) * EARTH_R_M * math.radians(1.0) * clat0
            pqn = (state.lat - olat) * EARTH_R_M * math.radians(1.0)
            vx, vy = pbe - pae, pbn - pan
            wx, wy = pqe - pae, pqn - pan
            den = vx * vx + vy * vy
            t = (wx * vx + wy * vy) / (den if den > 0 else 1.0)
            t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
            cx, cy = pae + t * vx, pan + t * vy
            lat_m = (wx * (-vy) + wy * vx) / math.sqrt(den if den > 0 else 1.0)
            d = math.hypot(pqe - cx, pqn - cy)
            if d < best_d:
                best_d = d
                best_s_m = (cum - length) + t * length
                best_lat = lat_m
                best_h = heading
                best_i = i
        clamped = max(-self.lateral_tol_m, min(self.lateral_tol_m, best_lat))
        a, b, length, cum, _ = self._segs[best_i]
        clat0 = math.cos(math.radians(olat))
        pae = (a[1] - olon) * EARTH_R_M * math.radians(1.0) * clat0
        pan = (a[0] - olat) * EARTH_R_M * math.radians(1.0)
        pbe = (b[1] - olon) * EARTH_R_M * math.radians(1.0) * clat0
        pbn = (b[0] - olat) * EARTH_R_M * math.radians(1.0)
        vx, vy = pbe - pae, pbn - pan
        ln = math.hypot(vx, vy) or 1.0
        nx, ny = -vy / ln, vx / ln
        ce, cn = self._enu_of(*self.point_at(best_s_m))
        lat, lon = self._lla_of(ce + nx * clamped, cn + ny * clamped)
        return ManifoldState(
            lat=lat,
            lon=lon,
            yaw_deg=best_h,
            edge_id=str(best_i),
            edge=best_i,
            s=best_s_m / self.total_m if self.total_m > 0 else 0.0,
            lateral_m=clamped,
        )

    def _enu_of(self, lat: float, lon: float) -> tuple[float, float]:
        olat, olon = self.origin
        clat0 = math.cos(math.radians(olat))
        e = (lon - olon) * EARTH_R_M * math.radians(1.0) * clat0
        n = (lat - olat) * EARTH_R_M * math.radians(1.0)
        return e, n

    def _lla_of(self, e: float, n: float) -> tuple[float, float]:
        olat, olon = self.origin
        clat0 = math.cos(math.radians(olat))
        lat = olat + math.degrees(n / EARTH_R_M)
        lon = olon + math.degrees(e / (EARTH_R_M * max(clat0, 1e-9)))
        return lat, lon

    def neighbours(self, state: ManifoldState, distance_m: float) -> list[ManifoldState]:
        s0 = min(max(state.s, 0.0), 1.0) * self.total_m
        out: list[ManifoldState] = []
        for ds in (-distance_m, distance_m):
            lat, lon = self.point_at(s0 + ds)
            probe = ManifoldState(
                lat=lat,
                lon=lon,
                yaw_deg=state.yaw_deg,
                s=min(max(s0 + ds, 0.0), self.total_m) / self.total_m if self.total_m else 0.0,
            )
            out.append(self.project(probe))
        return out

    def transition_cost(self, a: ManifoldState, b: ManifoldState) -> float:
        return abs(a.s - b.s) * self.total_m + 0.5 * abs(a.lateral_m - b.lateral_m)


class ManifoldParticleFilter:
    """Tiny manifold-only particle cloud for regression (not RoadParticleFilter)."""

    def __init__(
        self,
        manifold: ConstraintManifold,
        *,
        n: int = 64,
        seed: int = 26168,
    ) -> None:
        self.m = manifold
        self.n = int(n)
        self.rng = np.random.default_rng(seed)
        self.particles: list[ManifoldState] = []
        self.weights: np.ndarray = np.array([])

    def seed(self, lat: float, lon: float, yaw_deg: float) -> None:
        base = self.m.project(ManifoldState(lat=lat, lon=lon, yaw_deg=yaw_deg))
        nbrs = self.m.neighbours(base, 5.0)
        self.particles = []
        for i in range(self.n):
            src = nbrs[i % len(nbrs)] if nbrs else base
            p = replace(src, s=min(max(src.s + 0.02 * (float(self.rng.random()) - 0.5), 0.0), 1.0))
            self.particles.append(self.m.project(p))
        self.weights = np.full(self.n, 1.0 / self.n)

    def step(self, dt: float, speed_mps: float, yaw_deg: float) -> None:
        dist = max(0.0, speed_mps) * dt
        for i, p in enumerate(self.particles):
            p.yaw_deg = yaw_deg
            cands = self.m.neighbours(p, dist)
            if not cands:
                self.particles[i] = self.m.project(p)
                continue
            best = cands[0]
            best_cost = float("inf")
            for c in cands:
                cost = self.m.transition_cost(p, c) + 0.1 * _circ_diff_abs(c.yaw_deg, yaw_deg)
                if cost < best_cost:
                    best_cost = cost
                    best = c
            self.weights[i] *= math.exp(-0.05 * best_cost)
            self.particles[i] = self.m.project(best)
        total = float(self.weights.sum())
        if total <= 0:
            total = 1.0
        self.weights /= total

    def estimate(self) -> ManifoldState:
        if not self.particles:
            return ManifoldState()
        return self.particles[int(np.argmax(self.weights))]

    def lateral_error_m(self, lat: float, lon: float) -> float:
        proj = self.m.project(ManifoldState(lat=lat, lon=lon))
        return _haversine_m(lat, lon, proj.lat, proj.lon)
