"""Road-constrained particle filter: the map inside the loop, not after it.

Why this exists
---------------
Two measured results forced this design.

`run_heading_ablation.py` (23 drives, 186 outages): substituting a *perfect*
yaw sensor into free dead reckoning still fails 55% of 60 s road-speed
segments. A phone gyro cannot carry 60 s of heading.

`run_mapmatch_eval.py` (37 outages, real 3 271 km OSM graph): snapping the
finished dead-reckoned track to the road network afterwards gives 0.98x. It
*hurts* the near-miss cases, because once the track is hundreds of metres out
the matcher confidently snaps onto whichever road lies underneath.

The common cause is that free dead reckoning lets error grow without bound
before the map ever gets a say. So the map has to be in the loop.

The state change that does the work
-----------------------------------
Free DR carries an unconstrained 2D position, so heading error integrates into
unbounded cross-track error. Here a particle carries **where it is on the road
network**:

    (edge, s along edge, direction, speed_scale)

Position is *derived* from that, so it is always on a road. Cross-track error
is therefore bounded by road width by construction -- it cannot grow -- and the
only error that accumulates is along-track, driven by speed error alone. At 5%
speed error over 900 m that is ~45 m, which is inside the ISRO bar.

Heading stops being a quantity we integrate and becomes evidence. The gyro is
no longer asked "what is my absolute heading after 60 s", a question it cannot
answer; it is asked "does the turn I just felt match the geometry of the road
this particle claims to be on", which it answers well. That reframing is the
whole point, and it is the graph-decision framing from findings F9/F10 made
concrete.

Failure mode
------------
The error mode becomes discrete rather than gradual: a wrong branch at a
junction, not a slow drift. That is worse when it happens and better on
average, and it is what `branch accuracy` (F12) was defined to measure. The
filter reports its own posterior spread so a caller can tell the two apart.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

EARTH_R_M = 6_371_008.8
DEFAULT_N_PARTICLES = 600
DEFAULT_SPEED_SCALE_SIGMA = 0.06
DEFAULT_YAW_SIGMA_RAD_S = 0.12
DEFAULT_HEADING_SIGMA_DEG = 16.6
DEFAULT_SEED_RADIUS_M = 60.0
DEFAULT_ESS_FRACTION = 0.5
JUNCTION_TURN_PENALTY_DEG = 100.0


@dataclass
class FilterState:
    lat: float
    lon: float
    edge: int
    spread_m: float
    ess: float
    on_graph: bool


class RoadParticleFilter:
    """Particles live on the graph; position is derived, never integrated freely."""

    def __init__(
        self,
        graph: Any,
        *,
        n_particles: int = DEFAULT_N_PARTICLES,
        speed_scale_sigma: float = DEFAULT_SPEED_SCALE_SIGMA,
        yaw_sigma_rad_s: float = DEFAULT_YAW_SIGMA_RAD_S,
        seed: int = 26168,
        allowed_edges: set[int] | None = None,
    ) -> None:
        self.g = graph
        # Restrict the filter to a known set of edges. Used to model a tunnel or
        # underpass, which is topologically 1D: no branch decision exists, so
        # only along-track error can accumulate. A corridor result must always
        # be labelled as such -- it is a different scenario, not a better score.
        self.allowed_edges = allowed_edges
        self.n = int(n_particles)
        self.speed_scale_sigma = float(speed_scale_sigma)
        self.yaw_sigma = float(yaw_sigma_rad_s)
        self.rng = np.random.default_rng(seed)
        self.edge = np.zeros(self.n, dtype=np.int64)
        self.s = np.zeros(self.n, dtype=np.float64)
        self.forward = np.ones(self.n, dtype=bool)
        self.speed_scale = np.ones(self.n, dtype=np.float64)
        self.w = np.full(self.n, 1.0 / self.n, dtype=np.float64)
        self.alive = False
        self._geom_cache: dict[int, tuple] = {}

    # --- geometry helpers ------------------------------------------------

    def _geom(self, edge: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
        """Cached (seg lengths, seg bearings, cumulative length, total) for an edge.

        Slicing and re-running cumsum per particle per timestep was the single
        biggest cost in this filter: 400 particles x 600 steps is 240 000
        repetitions of work that depends only on the edge. Particles cluster on
        a handful of edges, so caching collapses it.
        """
        hit = self._geom_cache.get(edge)
        if hit is not None:
            return hit
        a, b = int(self.g.seg_ptr[edge]), int(self.g.seg_ptr[edge + 1])
        lens = np.asarray(self.g.seg_len_m[a:b], dtype=np.float64)
        bears = np.asarray(self.g.seg_bearing_deg[a:b], dtype=np.float64)
        cum = np.cumsum(lens) if lens.size else np.zeros(1)
        total = float(cum[-1]) if lens.size else 0.0
        out = (lens, bears, cum, total)
        self._geom_cache[edge] = out
        return out

    def _edge_seg_bearings(self, edge: int) -> tuple[np.ndarray, np.ndarray]:
        lens, bears, _, _ = self._geom(edge)
        return lens, bears

    def _pos_on_edge(self, edge: int, s: float, forward: bool) -> tuple[float, float, float]:
        """(lat, lon, bearing_deg) at arc length ``s`` along ``edge``."""
        lens, bears = self._edge_seg_bearings(edge)
        total = float(lens.sum())
        if total <= 0.0:
            u = int(self.g.edge_u[edge])
            return float(self.g.node_lat[u]), float(self.g.node_lon[u]), 0.0
        s = min(max(s, 0.0), total)
        walk = s if forward else total - s
        cum = np.cumsum(lens)
        k = int(np.searchsorted(cum, walk, side="left"))
        k = min(k, lens.size - 1)
        prev = float(cum[k - 1]) if k > 0 else 0.0
        frac = (walk - prev) / max(float(lens[k]), 1e-9)
        a0, _ = int(self.g.edge_ptr[edge]), 0
        n0 = int(self.g.edge_nodes[a0 + k])
        n1 = int(self.g.edge_nodes[a0 + k + 1])
        lat = float(self.g.node_lat[n0]) + frac * float(
            self.g.node_lat[n1] - self.g.node_lat[n0]
        )
        lon = float(self.g.node_lon[n0]) + frac * float(
            self.g.node_lon[n1] - self.g.node_lon[n0]
        )
        bear = float(bears[k]) if forward else (float(bears[k]) + 180.0) % 360.0
        return lat, lon, bear

    def _edge_length(self, edge: int) -> float:
        return self._geom(edge)[3]

    def _expected_yaw_rate(self, edge: int, s: float, forward: bool, v: float) -> float:
        """Road curvature at ``s`` expressed as a yaw rate for speed ``v``.

        The bearing difference between consecutive road segments divided by the
        distance over which it occurs is the local curvature; times speed gives
        the yaw rate a vehicle following this road must experience. This is what
        the gyro is compared against.
        """
        lens, bears = self._edge_seg_bearings(edge)
        if lens.size < 2:
            return 0.0
        total = float(lens.sum())
        walk = s if forward else total - s
        cum = np.cumsum(lens)
        k = int(np.searchsorted(cum, walk, side="left"))
        k = min(max(k, 0), lens.size - 2)
        d = (float(bears[k + 1]) - float(bears[k]) + 180.0) % 360.0 - 180.0
        span = max(float(lens[k]), 1.0)
        kappa = math.radians(d) / span
        return (kappa * v) if forward else (-kappa * v)

    def _neighbours(self, edge: int, forward: bool) -> list[tuple[int, bool]]:
        """Edges reachable from the far end of ``edge``, with their direction."""
        node = int(self.g.edge_v[edge]) if forward else int(self.g.edge_u[edge])
        out: list[tuple[int, bool]] = []
        for k in range(int(self.g.adj_ptr[node]), int(self.g.adj_ptr[node + 1])):
            code = int(self.g.adj_edge[k])
            fwd = code < self.g.n_edges
            e = code if fwd else code - self.g.n_edges
            if e == edge:
                continue
            if self.allowed_edges is not None and e not in self.allowed_edges:
                continue
            out.append((e, fwd))
        return out

    # --- lifecycle -------------------------------------------------------

    def seed_from_fix(
        self, lat: float, lon: float, heading_deg: float, radius_m: float = DEFAULT_SEED_RADIUS_M
    ) -> bool:
        """Initialise the cloud from the last GNSS fix before the outage."""
        cands: list[tuple[int, float, bool, float]] = []
        for e in self.g.nearby_edges(lat, lon, radius_m):
            e = int(e)
            if self.allowed_edges is not None and e not in self.allowed_edges:
                continue
            plat, plon, d, along, bearing = self.g.project(e, lat, lon)
            if not math.isfinite(d) or d > radius_m:
                continue
            for fwd in (True, False):
                b = bearing if fwd else (bearing + 180.0) % 360.0
                dh = abs((heading_deg - b + 180.0) % 360.0 - 180.0)
                if dh > 90.0:
                    continue
                total = self._edge_length(e)
                s = along if fwd else max(total - along, 0.0)
                logw = -0.5 * (d / 20.0) ** 2 - 0.5 * (dh / 30.0) ** 2
                cands.append((e, s, fwd, logw))
        if not cands:
            self.alive = False
            return False
        logw = np.array([c[3] for c in cands])
        p = np.exp(logw - logw.max())
        p /= p.sum()
        pick = self.rng.choice(len(cands), size=self.n, p=p)
        self.edge = np.array([cands[i][0] for i in pick], dtype=np.int64)
        self.s = np.array([cands[i][1] for i in pick], dtype=np.float64)
        self.forward = np.array([cands[i][2] for i in pick], dtype=bool)
        self.speed_scale = self.rng.normal(1.0, self.speed_scale_sigma, self.n)
        self.w = np.full(self.n, 1.0 / self.n)
        self.alive = True
        return True

    def step(
        self,
        v_mps: float,
        yaw_rate_rad_s: float,
        dt: float,
        *,
        heading_deg: float | None = None,
        heading_sigma_deg: float = DEFAULT_HEADING_SIGMA_DEG,
        want_position: bool = True,
    ) -> FilterState:
        """Advance one sample: propagate along the graph, weight by turn evidence.

        Vectorised by grouping particles on the same edge. The per-particle
        Python loop this replaces made a 60 s segment take ~6 s, which was too
        slow to gather enough segments to conclude anything. Only the junction
        crossings -- a handful of particles per step -- still loop.

        ``want_position=False`` skips deriving lat/lon for every particle, which
        is pure reporting cost. Callers that only need the final fix should pass
        False on intermediate steps.
        """
        if not self.alive:
            return FilterState(float("nan"), float("nan"), -1, float("inf"), 0.0, False)

        logw = np.log(np.maximum(self.w, 1e-300))
        v_all = max(v_mps, 0.0) * self.speed_scale

        # --- expected yaw rate from road curvature, grouped by edge ---------
        uniq, inv = np.unique(self.edge, return_inverse=True)
        expected = np.zeros(self.n, dtype=np.float64)
        totals = np.zeros(self.n, dtype=np.float64)
        for gi, e in enumerate(uniq):
            m = inv == gi
            lens, bears, cum, total = self._geom(int(e))
            totals[m] = total
            walk = np.where(self.forward[m], self.s[m], total - self.s[m])
            heading_k = np.clip(
                np.searchsorted(cum, walk, side="left"), 0, max(lens.size - 1, 0)
            )
            if heading_deg is not None and math.isfinite(heading_deg) and lens.size:
                road_heading = np.where(
                    self.forward[m],
                    bears[heading_k],
                    (bears[heading_k] + 180.0) % 360.0,
                )
                heading_residual = (
                    float(heading_deg) - road_heading + 180.0
                ) % 360.0 - 180.0
                logw[m] += -0.5 * (
                    heading_residual / max(float(heading_sigma_deg), 1e-3)
                ) ** 2
            if lens.size < 2:
                continue
            fwd = self.forward[m]
            k = np.clip(np.searchsorted(cum, walk, side="left"), 0, lens.size - 2)
            d = (bears[k + 1] - bears[k] + 180.0) % 360.0 - 180.0
            kappa = np.radians(d) / np.maximum(lens[k], 1.0)
            ev = kappa * v_all[m]
            expected[m] = np.where(fwd, ev, -ev)

        logw += -0.5 * ((yaw_rate_rad_s - expected) / self.yaw_sigma) ** 2
        self.s += v_all * dt

        # --- junction crossings: only the few particles that ran off an edge -
        crossed = np.flatnonzero(self.s > totals)
        for i in crossed:
            i = int(i)
            e, fwd = int(self.edge[i]), bool(self.forward[i])
            total = totals[i]
            guard = 0
            while self.s[i] > total and guard < 4:
                guard += 1
                overshoot = float(self.s[i]) - total
                nbrs = self._neighbours(e, fwd)
                if not nbrs:
                    self.s[i] = total
                    logw[i] -= 20.0  # dead end: implausible, not impossible
                    break
                _, _, cur_bear = self._pos_on_edge(e, total, fwd)
                scores = np.empty(len(nbrs))
                for j, (ne, nfwd) in enumerate(nbrs):
                    _, _, nb = self._pos_on_edge(ne, 0.0, nfwd)
                    turn = (nb - cur_bear + 180.0) % 360.0 - 180.0
                    turn_rate = math.radians(turn) / max(dt * 4.0, 1e-3)
                    scores[j] = (
                        -0.5 * ((yaw_rate_rad_s - turn_rate) / (self.yaw_sigma * 6.0)) ** 2
                        - abs(turn) / JUNCTION_TURN_PENALTY_DEG
                    )
                pr = np.exp(scores - scores.max())
                pr /= pr.sum()
                j = int(self.rng.choice(len(nbrs), p=pr))
                e, fwd = nbrs[j]
                self.edge[i], self.forward[i] = e, fwd
                self.s[i] = overshoot
                total = self._edge_length(e)

        logw -= logw.max()
        w = np.exp(logw)
        total_w = float(w.sum())
        if not np.isfinite(total_w) or total_w <= 0.0:
            self.alive = False
            return FilterState(float("nan"), float("nan"), -1, float("inf"), 0.0, False)
        self.w = w / total_w

        ess = 1.0 / float(np.sum(self.w**2))
        if ess < DEFAULT_ESS_FRACTION * self.n:
            idx = self.rng.choice(self.n, size=self.n, p=self.w)
            self.edge = self.edge[idx]
            self.s = self.s[idx]
            self.forward = self.forward[idx]
            self.speed_scale = self.speed_scale[idx] * self.rng.normal(
                1.0, self.speed_scale_sigma * 0.25, self.n
            )
            self.w = np.full(self.n, 1.0 / self.n)

        best = int(self.edge[int(np.argmax(self.w))])
        if not want_position:
            return FilterState(float("nan"), float("nan"), best, float("nan"), ess, True)
        return self._position(best, ess)

    def _position(self, best_edge: int, ess: float) -> FilterState:
        """Weighted mean position of the cloud, plus its spread in metres."""
        lats = np.empty(self.n)
        lons = np.empty(self.n)
        uniq, inv = np.unique(self.edge, return_inverse=True)
        for gi, e in enumerate(uniq):
            m = np.flatnonzero(inv == gi)
            for i in m:
                lats[i], lons[i], _ = self._pos_on_edge(
                    int(e), float(self.s[i]), bool(self.forward[i])
                )
        lat = float(np.sum(self.w * lats))
        lon = float(np.sum(self.w * lons))
        clat = math.cos(math.radians(lat))
        dx = (lons - lon) * EARTH_R_M * math.radians(1.0) * clat
        dy = (lats - lat) * EARTH_R_M * math.radians(1.0)
        spread = float(np.sqrt(np.sum(self.w * (dx**2 + dy**2))))
        return FilterState(lat, lon, best_edge, spread, ess, True)
