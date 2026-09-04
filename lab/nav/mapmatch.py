"""Hidden Markov map matching over an offline OpenStreetMap road graph.

Formulation is Newson & Krumm (2009), "Hidden Markov Map Matching Through Noise
and Sparseness", ACM SIGSPATIAL GIS '09. **This is their algorithm, not ours.**
We cite it and use it; the contribution here is applying it to a *dead-reckoned*
track during a full GNSS outage rather than to noisy GNSS fixes, and adding a
heading-consistency term that encodes the non-holonomic constraint the problem
statement asks for.

Why this module is the load-bearing one
---------------------------------------
`lab/stress/run_heading_ablation.py` measured, across 23 drives and 186 forced
60 s outages scored against CAN ground truth, that substituting a *perfect*
yaw sensor still fails 55% of segments at 12.4% median drift. Free-inertial
dead reckoning on a smartphone cannot meet the ISRO bar on its own. The map is
the only remaining source of the information that is missing.

Adaptation for dead-reckoned input
----------------------------------
Newson & Krumm assume independent GNSS fixes with roughly stationary noise. A
dead-reckoned track is the opposite: locally the *shape* is good and the
absolute position drifts monotonically. Two changes follow.

1. **Growing emission sigma.** Measurement uncertainty starts at the seed
   accuracy and grows with time since the outage began, so late points are
   allowed to sit further from their true edge without being penalised out of
   contention.
2. **Shape over position in the transition term.** The transition cost compares
   the *dead-reckoned* step length against the on-graph route distance, which
   is drift-invariant to first order: a track offset by 200 m still has the
   right inter-point distances.

The emission model also carries a heading term. A vehicle cannot travel
sideways along a road, so a candidate edge whose bearing disagrees with the
direction of travel is unlikely regardless of how close it is. That is the
non-holonomic constraint expressed as a probability rather than a hard filter.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

EARTH_R_M = 6_371_008.8

# Newson & Krumm fit sigma_z = 4.07 m for taxi GNSS. A dead-reckoned track is
# far less certain, so sigma is larger here.
#
# The growth term was measured and REJECTED. Letting sigma grow over the outage
# seemed principled -- uncertainty really does grow -- but it weakens the very
# constraint that makes map matching work, and on 16 segments with free-DR
# error under 400 m it made things worse:
#
#     sigma policy      median error   helped   ratio vs free DR
#     15 m + 1.5 m/s       199.8 m      6/16         1.21
#     15 m fixed           169.8 m      8/16         1.03
#     30 m fixed           158.4 m     10/16         0.96   <- best
#     60 m fixed           210.3 m      6/16         1.28
#
# So the default growth is 0. Keep the parameter: a filter that carries a real
# covariance should drive sigma from it rather than from elapsed time.
DEFAULT_SIGMA_Z_M = 30.0
DEFAULT_SIGMA_GROWTH_M_PER_S = 0.0
DEFAULT_BETA_M = 30.0
DEFAULT_HEADING_SIGMA_DEG = 45.0
DEFAULT_SEARCH_RADIUS_M = 120.0
DEFAULT_MAX_CANDIDATES = 12
ROUTE_SEARCH_CAP_M = 2_000.0


@dataclass
class Candidate:
    """One projection of a measurement onto a road edge."""

    edge: int
    lat: float
    lon: float
    distance_m: float
    along_m: float
    bearing_deg: float
    emission_logp: float = 0.0


@dataclass
class MatchResult:
    lat: np.ndarray
    lon: np.ndarray
    edge: np.ndarray
    matched: np.ndarray
    n_points: int = 0
    n_matched: int = 0
    meta: dict[str, Any] = field(default_factory=dict)


class MapGraph:
    """Read-only wrapper over a ``.graph.npz`` built by ``maps/osm_extract.py``."""

    def __init__(self, graph: dict[str, Any]) -> None:
        self.g = graph
        self.node_lat = graph["node_lat"]
        self.node_lon = graph["node_lon"]
        self.edge_ptr = graph["edge_ptr"]
        self.edge_nodes = graph["edge_nodes"]
        self.edge_u = graph["edge_u"]
        self.edge_v = graph["edge_v"]
        self.edge_len_m = graph["edge_len_m"]
        self.edge_bearing_deg = graph["edge_bearing_deg"]
        self.adj_ptr = graph["adj_ptr"]
        self.adj_edge = graph["adj_edge"]
        self.grid_ptr = graph["grid_ptr"]
        self.grid_edge = graph["grid_edge"]
        self.grid_lat0 = float(graph["grid_lat0"])
        self.grid_lon0 = float(graph["grid_lon0"])
        self.grid_deg = float(graph["grid_deg"])
        self.grid_n_lat = int(graph["grid_n_lat"])
        self.grid_n_lon = int(graph["grid_n_lon"])
        self.n_edges = int(self.edge_u.size)
        self.meta = graph.get("meta", {})

    @classmethod
    def load(cls, path: Path | str) -> MapGraph:
        import sys

        maps_dir = Path(__file__).resolve().parents[2] / "maps"
        if str(maps_dir) not in sys.path:
            sys.path.insert(0, str(maps_dir))
        from osm_extract import load_graph  # noqa: PLC0415

        return cls(load_graph(path))

    def _cells(self, lat: float, lon: float, radius_m: float) -> list[int]:
        dlat = radius_m / 111_320.0
        dlon = radius_m / max(111_320.0 * math.cos(math.radians(lat)), 1.0)
        i0 = int((lat - dlat - self.grid_lat0) / self.grid_deg)
        i1 = int((lat + dlat - self.grid_lat0) / self.grid_deg)
        j0 = int((lon - dlon - self.grid_lon0) / self.grid_deg)
        j1 = int((lon + dlon - self.grid_lon0) / self.grid_deg)
        out: list[int] = []
        for i in range(max(i0, 0), min(i1, self.grid_n_lat - 1) + 1):
            for j in range(max(j0, 0), min(j1, self.grid_n_lon - 1) + 1):
                out.append(i * self.grid_n_lon + j)
        return out

    def nearby_edges(self, lat: float, lon: float, radius_m: float) -> np.ndarray:
        parts = [
            self.grid_edge[self.grid_ptr[c] : self.grid_ptr[c + 1]]
            for c in self._cells(lat, lon, radius_m)
            if 0 <= c < self.grid_ptr.size - 1
        ]
        if not parts:
            return np.empty(0, dtype=np.int64)
        return np.unique(np.concatenate(parts))

    def project(self, edge: int, lat: float, lon: float) -> tuple[float, float, float, float, float]:
        """Closest point on ``edge`` to (lat, lon).

        Returns (lat, lon, perpendicular distance m, along-edge distance m,
        local bearing deg). Works in a local ENU tangent plane, which is exact
        enough at the scale of one road segment.
        """
        a, b = int(self.edge_ptr[edge]), int(self.edge_ptr[edge + 1])
        idx = self.edge_nodes[a:b]
        clat = math.cos(math.radians(lat))
        px = (self.node_lon[idx] - lon) * EARTH_R_M * math.radians(1.0) * clat
        py = (self.node_lat[idx] - lat) * EARTH_R_M * math.radians(1.0)
        best = (float("inf"), 0.0, 0.0, 0.0, 0.0, 0.0)
        along = 0.0
        for k in range(idx.size - 1):
            ax, ay = px[k], py[k]
            bx, by = px[k + 1], py[k + 1]
            vx, vy = bx - ax, by - ay
            seg_len = math.hypot(vx, vy)
            if seg_len < 1e-9:
                continue
            t = -(ax * vx + ay * vy) / (seg_len * seg_len)
            t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
            cx, cy = ax + t * vx, ay + t * vy
            d = math.hypot(cx, cy)
            if d < best[0]:
                bearing = math.degrees(math.atan2(vx, vy)) % 360.0
                best = (d, cx, cy, along + t * seg_len, bearing, seg_len)
            along += seg_len
        if not math.isfinite(best[0]):
            return lat, lon, float("inf"), 0.0, 0.0
        d, cx, cy, along_m, bearing, _ = best
        out_lat = lat + math.degrees(cy / EARTH_R_M)
        out_lon = lon + math.degrees(cx / (EARTH_R_M * max(clat, 1e-9)))
        return out_lat, out_lon, d, along_m, bearing

    def route_distance_m(self, e_from: int, e_to: int, cap_m: float) -> float:
        """Shortest on-graph distance between two edges, capped.

        Dijkstra over node endpoints. Returns ``inf`` when no route is found
        inside ``cap_m``, which the transition term then treats as impossible.
        """
        if e_from == e_to:
            return 0.0
        targets = {int(self.edge_u[e_to]), int(self.edge_v[e_to])}
        start = int(self.edge_v[e_from])
        heap: list[tuple[float, int]] = [(0.0, start)]
        seen: dict[int, float] = {start: 0.0}
        while heap:
            dist, node = heapq.heappop(heap)
            if node in targets:
                return dist
            if dist > cap_m:
                return float("inf")
            if dist > seen.get(node, float("inf")):
                continue
            for k in range(int(self.adj_ptr[node]), int(self.adj_ptr[node + 1])):
                # The adjacency is directed: codes below n_edges are forward
                # traversals (u -> v); codes at or above it are the reverse
                # traversal of edge (code - n_edges), which only exists for
                # two-way edges. Decoding this wrong walks the wrong way down
                # one-way roads and indexes out of bounds.
                code = int(self.adj_edge[k])
                forward = code < self.n_edges
                e = code if forward else code - self.n_edges
                nxt = int(self.edge_v[e]) if forward else int(self.edge_u[e])
                nd = dist + float(self.edge_len_m[e])
                if nd < seen.get(nxt, float("inf")) and nd <= cap_m:
                    seen[nxt] = nd
                    heapq.heappush(heap, (nd, nxt))
        return float("inf")


def _angle_diff_deg(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def _great_circle_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    mlat = math.radians((lat1 + lat2) * 0.5)
    return math.hypot(dlat, dlon * math.cos(mlat)) * EARTH_R_M


def match(
    lat: np.ndarray,
    lon: np.ndarray,
    graph: MapGraph,
    *,
    t_s: np.ndarray | None = None,
    heading_deg: np.ndarray | None = None,
    sigma_z_m: float = DEFAULT_SIGMA_Z_M,
    sigma_growth_m_per_s: float = DEFAULT_SIGMA_GROWTH_M_PER_S,
    beta_m: float = DEFAULT_BETA_M,
    heading_sigma_deg: float = DEFAULT_HEADING_SIGMA_DEG,
    search_radius_m: float = DEFAULT_SEARCH_RADIUS_M,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
) -> MatchResult:
    """Viterbi-decode a track onto the road graph.

    ``lat``/``lon`` is the dead-reckoned track. ``heading_deg`` is optional and
    only sharpens the emission model. Points with no candidate inside
    ``search_radius_m`` are passed through unmatched rather than forced onto a
    distant road, and ``MatchResult.matched`` flags which is which.
    """
    lat = np.asarray(lat, dtype=np.float64)
    lon = np.asarray(lon, dtype=np.float64)
    n = lat.size
    if n == 0:
        return MatchResult(lat.copy(), lon.copy(), np.full(0, -1), np.zeros(0, bool))
    t = np.arange(n, dtype=np.float64) if t_s is None else np.asarray(t_s, dtype=np.float64)
    t0 = float(t[0])

    # --- candidate generation + emission ---------------------------------
    cands: list[list[Candidate]] = []
    for i in range(n):
        sigma = sigma_z_m + sigma_growth_m_per_s * max(float(t[i]) - t0, 0.0)
        radius = max(search_radius_m, 3.0 * sigma)
        found: list[Candidate] = []
        for e in graph.nearby_edges(float(lat[i]), float(lon[i]), radius):
            plat, plon, d, along, bearing = graph.project(int(e), float(lat[i]), float(lon[i]))
            if not math.isfinite(d) or d > radius:
                continue
            logp = -0.5 * (d / sigma) ** 2 - math.log(sigma)
            if heading_deg is not None and math.isfinite(float(heading_deg[i])):
                # Non-holonomic constraint: a vehicle runs along the road, in
                # either direction on a two-way edge.
                dh = min(
                    _angle_diff_deg(float(heading_deg[i]), bearing),
                    _angle_diff_deg(float(heading_deg[i]), bearing + 180.0),
                )
                logp += -0.5 * (dh / heading_sigma_deg) ** 2
            found.append(Candidate(int(e), plat, plon, d, along, bearing, logp))
        found.sort(key=lambda c: -c.emission_logp)
        cands.append(found[:max_candidates])

    # --- Viterbi ---------------------------------------------------------
    score: list[float] = []
    back: list[list[int]] = []
    prev_score: list[float] = [c.emission_logp for c in cands[0]]
    for i in range(1, n):
        cur = cands[i]
        prev = cands[i - 1]
        step_m = _great_circle_m(
            float(lat[i - 1]), float(lon[i - 1]), float(lat[i]), float(lon[i])
        )
        cap = min(ROUTE_SEARCH_CAP_M, 2.0 * step_m + 300.0)
        row_back = [-1] * len(cur)
        row_score = [-math.inf] * len(cur)
        for cj, c in enumerate(cur):
            best, best_k = -math.inf, -1
            for pk, p in enumerate(prev):
                if not math.isfinite(prev_score[pk]):
                    continue
                route = graph.route_distance_m(p.edge, c.edge, cap)
                if not math.isfinite(route):
                    continue
                # Newson & Krumm transition: exponential in |great-circle
                # distance - route distance|.
                trans = -abs(step_m - route) / beta_m
                s = prev_score[pk] + trans
                if s > best:
                    best, best_k = s, pk
            if best_k >= 0:
                row_score[cj] = best + c.emission_logp
                row_back[cj] = best_k
            elif cur:
                # No reachable predecessor: restart the chain here rather than
                # dropping the whole remainder of the track.
                row_score[cj] = c.emission_logp - 50.0
                row_back[cj] = -1
        score.append(max(row_score) if row_score else -math.inf)
        back.append(row_back)
        prev_score = row_score

    # --- backtrack -------------------------------------------------------
    out_lat = lat.copy()
    out_lon = lon.copy()
    out_edge = np.full(n, -1, dtype=np.int64)
    matched = np.zeros(n, dtype=bool)
    if not cands[-1] or not math.isfinite(max(prev_score, default=-math.inf)):
        return MatchResult(out_lat, out_lon, out_edge, matched, n, 0)
    # A predecessor of -1 means the chain restarted at that point because no
    # candidate was reachable from the previous step. Restarting the backtrack
    # from the best candidate of the earlier point recovers the rest of the
    # track; breaking out instead silently drops everything before the first
    # discontinuity, which on a 60 s outage is most of the segment.
    k = int(np.argmax(prev_score))
    scores_at = [[c.emission_logp for c in cs] for cs in cands]
    for i in range(n - 1, -1, -1):
        if k < 0 or k >= len(cands[i]):
            if not cands[i]:
                k = -1
                continue
            k = int(np.argmax(scores_at[i]))
        c = cands[i][k]
        out_lat[i], out_lon[i], out_edge[i], matched[i] = c.lat, c.lon, c.edge, True
        if i == 0:
            break
        k = back[i - 1][k]
    return MatchResult(
        out_lat,
        out_lon,
        out_edge,
        matched,
        n_points=n,
        n_matched=int(matched.sum()),
        meta={
            "sigma_z_m": sigma_z_m,
            "sigma_growth_m_per_s": sigma_growth_m_per_s,
            "beta_m": beta_m,
            "heading_sigma_deg": heading_sigma_deg,
            "formulation": "Newson & Krumm 2009 (cited, not novel)",
        },
    )
