/**
 * ConstraintManifold — map constraint as a plug-in [Phase 2 / F2].
 *
 * RoadGraphManifold wraps shipping road-graph geometry (same scoring as mapProject).
 * CorridorManifold is a synthetic 1-D polyline + lateral tolerance demo only —
 * not field-validated for rail, undersea, or planetary navigation.
 */

import type { IRoadGraph, IGraphEdge } from "../types/index.ts";
import { haversineM, wrap360, llaToEnu, enuToLla, headingBetween, mulberry32, clamp } from "../math.ts";
import {
  nearestEdges,
  interpolateEdge,
  projectS,
  edgeById,
  outgoing,
} from "./geometry.ts";

export interface ManifoldState {
  lat: number;
  lon: number;
  alt: number;
  yaw_deg: number;
  edge_id: string;
  s: number;
  lateral_m: number;
}

export interface ConstraintManifold {
  project(state: ManifoldState): ManifoldState;
  neighbours(state: ManifoldState, distance_m: number): ManifoldState[];
  transition_cost(a: ManifoldState, b: ManifoldState): number;
  dim(): number;
}

function circDiffAbs(a: number, b: number): number {
  let d = wrap360(a) - wrap360(b);
  if (d > 180) d -= 360;
  if (d < -180) d += 360;
  return Math.abs(d);
}

function emptyState(): ManifoldState {
  return { lat: 0, lon: 0, alt: 0, yaw_deg: 0, edge_id: "", s: 0, lateral_m: 0 };
}

export class RoadGraphManifold implements ConstraintManifold {
  constructor(public readonly graph: IRoadGraph) {}

  dim(): number {
    return 1;
  }

  project(state: ManifoldState): ManifoldState {
    const out = { ...state };
    const cands = nearestEdges(this.graph, state.lat, state.lon, 5);
    if (!cands.length) return out;
    let best: IGraphEdge | null = null;
    let bestScore = 1e300;
    for (const e of cands) {
      const dH = circDiffAbs(e.heading_deg, state.yaw_deg);
      const p = interpolateEdge(this.graph, e, projectS(this.graph, e, state.lat, state.lon));
      const d = haversineM(state.lat, state.lon, p.lat, p.lon);
      const score = d + 0.15 * dH;
      if (score < bestScore) {
        bestScore = score;
        best = e;
      }
    }
    if (!best) return out;
    const s = projectS(this.graph, best, state.lat, state.lon);
    const p = interpolateEdge(this.graph, best, s);
    out.lat = p.lat;
    out.lon = p.lon;
    out.alt = p.alt;
    out.edge_id = best.id;
    out.s = s;
    out.yaw_deg = best.heading_deg;
    out.lateral_m = 0;
    return out;
  }

  neighbours(state: ManifoldState, distance_m: number): ManifoldState[] {
    const edge = edgeById(this.graph, state.edge_id);
    if (!edge) {
      return nearestEdges(this.graph, state.lat, state.lon, 8).map((e) => {
        const p = interpolateEdge(this.graph, e, 0);
        return {
          ...emptyState(),
          lat: p.lat,
          lon: p.lon,
          alt: p.alt,
          edge_id: e.id,
          yaw_deg: e.heading_deg,
          s: 0,
        };
      });
    }
    const remain = (1 - state.s) * edge.length_m;
    if (remain >= distance_m) {
      const n = { ...state };
      n.s = clamp(state.s + distance_m / Math.max(1e-3, edge.length_m), 0, 0.999);
      const p = interpolateEdge(this.graph, edge, n.s);
      n.lat = p.lat;
      n.lon = p.lon;
      n.alt = p.alt;
      n.yaw_deg = edge.heading_deg;
      return [n];
    }
    const outs = outgoing(this.graph, edge.to);
    if (!outs.length) {
      const n = { ...state, s: 0.999, yaw_deg: edge.heading_deg };
      const p = interpolateEdge(this.graph, edge, n.s);
      n.lat = p.lat;
      n.lon = p.lon;
      n.alt = p.alt;
      return [n];
    }
    return outs.map((o) => {
      const p = interpolateEdge(this.graph, o, 0);
      return {
        ...emptyState(),
        lat: p.lat,
        lon: p.lon,
        alt: p.alt,
        edge_id: o.id,
        yaw_deg: o.heading_deg,
        s: 0,
      };
    });
  }

  transition_cost(a: ManifoldState, b: ManifoldState): number {
    return haversineM(a.lat, a.lon, b.lat, b.lon) + 0.05 * circDiffAbs(a.yaw_deg, b.yaw_deg);
  }
}

interface Seg {
  a: { lat: number; lon: number; alt: number };
  b: { lat: number; lon: number; alt: number };
  len_m: number;
  cum_m: number;
  heading_deg: number;
}

/** SYNTHETIC DEMO ONLY — not field-validated. */
export class CorridorManifold implements ConstraintManifold {
  readonly lateral_tol_m: number;
  readonly polyline: { lat: number; lon: number; alt: number }[];
  readonly origin: { lat: number; lon: number; alt: number };
  private segs: Seg[] = [];
  private total_m = 0;

  constructor(
    polyline: { lat: number; lon: number; alt: number }[],
    lateral_tol_m: number,
    origin?: { lat: number; lon: number; alt: number },
  ) {
    this.polyline = polyline;
    this.lateral_tol_m = Math.max(0.1, lateral_tol_m);
    this.origin = origin ?? polyline[0] ?? { lat: 0, lon: 0, alt: 0 };
    let cum = 0;
    for (let i = 0; i + 1 < polyline.length; i++) {
      const a = polyline[i]!;
      const b = polyline[i + 1]!;
      let len = haversineM(a.lat, a.lon, b.lat, b.lon);
      if (len < 1e-6) len = 1e-6;
      cum += len;
      this.segs.push({
        a,
        b,
        len_m: len,
        cum_m: cum,
        heading_deg: headingBetween(a.lat, a.lon, b.lat, b.lon),
      });
    }
    this.total_m = cum;
  }

  dim(): number {
    return 1;
  }

  length_m(): number {
    return this.total_m;
  }

  pointAt(s_m: number): { lat: number; lon: number; alt: number } {
    if (!this.segs.length) return this.origin;
    s_m = clamp(s_m, 0, this.total_m);
    for (let i = 0; i < this.segs.length; i++) {
      const seg = this.segs[i]!;
      const start = seg.cum_m - seg.len_m;
      if (s_m <= seg.cum_m || i === this.segs.length - 1) {
        const u = (s_m - start) / seg.len_m;
        return {
          lat: seg.a.lat + (seg.b.lat - seg.a.lat) * u,
          lon: seg.a.lon + (seg.b.lon - seg.a.lon) * u,
          alt: seg.a.alt + (seg.b.alt - seg.a.alt) * u,
        };
      }
    }
    return this.polyline[this.polyline.length - 1]!;
  }

  project(state: ManifoldState): ManifoldState {
    const out = { ...state };
    if (!this.segs.length) return out;
    let bestD = Infinity;
    let bestSm = 0;
    let bestLat = 0;
    let bestH = 0;
    let bestSeg = 0;
    for (let i = 0; i < this.segs.length; i++) {
      const seg = this.segs[i]!;
      const pa = llaToEnu(this.origin, seg.a.lat, seg.a.lon, seg.a.alt);
      const pb = llaToEnu(this.origin, seg.b.lat, seg.b.lon, seg.b.alt);
      const pq = llaToEnu(this.origin, state.lat, state.lon, seg.a.alt);
      const vx = pb.e - pa.e;
      const vy = pb.n - pa.n;
      const wx = pq.e - pa.e;
      const wy = pq.n - pa.n;
      const den = vx * vx + vy * vy || 1;
      const t = clamp((wx * vx + wy * vy) / den, 0, 1);
      const cx = pa.e + t * vx;
      const cy = pa.n + t * vy;
      const latM = (wx * -vy + wy * vx) / Math.sqrt(den);
      const d = Math.hypot(pq.e - cx, pq.n - cy);
      if (d < bestD) {
        bestD = d;
        bestSm = seg.cum_m - seg.len_m + t * seg.len_m;
        bestLat = latM;
        bestH = seg.heading_deg;
        bestSeg = i;
      }
    }
    const clamped = clamp(bestLat, -this.lateral_tol_m, this.lateral_tol_m);
    const centre = this.pointAt(bestSm);
    const seg = this.segs[bestSeg]!;
    const pa = llaToEnu(this.origin, seg.a.lat, seg.a.lon, seg.a.alt);
    const pb = llaToEnu(this.origin, seg.b.lat, seg.b.lon, seg.b.alt);
    const vx = pb.e - pa.e;
    const vy = pb.n - pa.n;
    const len = Math.hypot(vx, vy) || 1;
    const nx = -vy / len;
    const ny = vx / len;
    const c = llaToEnu(this.origin, centre.lat, centre.lon, centre.alt);
    const snapped = enuToLla(this.origin, c.e + nx * clamped, c.n + ny * clamped, c.u);
    out.lat = snapped.lat;
    out.lon = snapped.lon;
    out.alt = snapped.alt;
    out.yaw_deg = bestH;
    out.s = this.total_m > 0 ? bestSm / this.total_m : 0;
    out.lateral_m = clamped;
    out.edge_id = String(bestSeg);
    return out;
  }

  neighbours(state: ManifoldState, distance_m: number): ManifoldState[] {
    if (!this.segs.length) return [];
    const s0 = clamp(state.s, 0, 1) * this.total_m;
    return [-distance_m, distance_m].map((ds) => {
      const p = this.pointAt(s0 + ds);
      return this.project({
        ...state,
        lat: p.lat,
        lon: p.lon,
        alt: p.alt,
        s: this.total_m > 0 ? clamp(s0 + ds, 0, this.total_m) / this.total_m : 0,
      });
    });
  }

  transition_cost(a: ManifoldState, b: ManifoldState): number {
    return Math.abs(a.s - b.s) * this.total_m + 0.5 * Math.abs(a.lateral_m - b.lateral_m);
  }
}

export interface ManifoldFilterConfig {
  n?: number;
  seed?: number;
}

/** Tiny manifold-only particle cloud for regression (not production GraphPF). */
export class ManifoldParticleFilter {
  private rng: () => number;
  private n: number;
  private particles: ManifoldState[] = [];
  private weights: number[] = [];

  constructor(
    private readonly m: ConstraintManifold,
    cfg: ManifoldFilterConfig = {},
  ) {
    this.n = cfg.n ?? 64;
    this.rng = mulberry32(cfg.seed ?? 26168);
  }

  seed(lat: number, lon: number, yawDeg: number): void {
    const base = this.m.project({ ...emptyState(), lat, lon, yaw_deg: yawDeg });
    const nbrs = this.m.neighbours(base, 5);
    this.particles = [];
    this.weights = [];
    for (let i = 0; i < this.n; i++) {
      let p = nbrs.length ? { ...nbrs[i % nbrs.length]! } : { ...base };
      p.s = clamp(p.s + 0.02 * (this.rng() - 0.5), 0, 1);
      this.particles.push(this.m.project(p));
      this.weights.push(1 / this.n);
    }
  }

  step(dt: number, speedMps: number, yawDeg: number): void {
    const dist = Math.max(0, speedMps) * dt;
    for (let i = 0; i < this.particles.length; i++) {
      const p = { ...this.particles[i]!, yaw_deg: yawDeg };
      const cands = this.m.neighbours(p, dist);
      if (!cands.length) {
        this.particles[i] = this.m.project(p);
        continue;
      }
      let best = cands[0]!;
      let bestCost = 1e300;
      for (const c of cands) {
        const cost = this.m.transition_cost(p, c) + 0.1 * circDiffAbs(c.yaw_deg, yawDeg);
        if (cost < bestCost) {
          bestCost = cost;
          best = c;
        }
      }
      this.weights[i]! *= Math.exp(-0.05 * bestCost);
      this.particles[i] = this.m.project(best);
    }
    let sum = this.weights.reduce((a, b) => a + b, 0);
    if (sum <= 0) sum = 1;
    this.weights = this.weights.map((w) => w / sum);
  }

  estimate(): ManifoldState {
    let best = 0;
    for (let i = 1; i < this.weights.length; i++) {
      if (this.weights[i]! > this.weights[best]!) best = i;
    }
    return this.particles[best] ?? emptyState();
  }

  lateralErrorM(lat: number, lon: number): number {
    const proj = this.m.project({ ...emptyState(), lat, lon });
    return haversineM(lat, lon, proj.lat, proj.lon);
  }
}
