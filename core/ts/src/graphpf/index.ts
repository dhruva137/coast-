/**
 * Particle filter on the road graph [F9, F10].
 *
 * Along an edge, map projection annihilates heading error (10° → 0.7 m, 99.3%).
 * Heading value is concentrated at junctions. Adaptive compute: cheap along
 * an edge, maximum approaching a fork. This is a GRAPH DECISION problem —
 * "which ramp did you take" — not a regression problem.
 */

import type { IRoadGraph, IGraphEdge, IParticle, INavState } from "../types/index.ts";
import { haversineM, wrap360, gauss, mulberry32 } from "../math.ts";
import {
  edgeById,
  interpolateEdge,
  nearestEdges,
  nodeById,
  outgoing,
  projectS,
} from "./geometry.ts";

export {
  edgeById,
  interpolateEdge,
  nearestEdges,
  nodeById,
  outgoing,
  projectS,
  headingBetween,
  enuToLla,
} from "./geometry.ts";
export { VectorMapLocator, edgeFeature, cosineSimilarity } from "./vector_locator.ts";
export type {
  EdgeFeature,
  EdgePosterior,
  VectorBelief,
  VectorLocatorConfig,
  LocateQuery,
} from "./vector_locator.ts";

export interface GraphPfConfig {
  n: number;
  seed?: number;
}

export class GraphParticleFilter {
  particles: IParticle[] = [];
  graph: IRoadGraph;
  private rng: () => number;
  private n: number;
  private lastEdge: string | null = null;
  junctionBoost = false;

  constructor(graph: IRoadGraph, cfg: GraphPfConfig = { n: 256 }) {
    this.graph = graph;
    this.n = cfg.n;
    this.rng = mulberry32(cfg.seed ?? 26168);
  }

  seed(lat: number, lon: number, yawDeg: number): void {
    const nearest = nearestEdges(this.graph, lat, lon, 8);
    this.particles = [];
    const w = 1 / Math.max(1, nearest.length);
    for (let i = 0; i < this.n; i++) {
      const e = nearest[i % Math.max(1, nearest.length)];
      if (!e) continue;
      this.particles.push({
        edge_id: e.id,
        s: 0.15 + 0.7 * this.rng(),
        weight: w / (this.n / Math.max(1, nearest.length)),
        heading: e.heading_deg,
      });
    }
    if (this.particles.length === 0) {
      const e0 = this.graph.edges[0];
      if (e0) {
        this.particles = Array.from({ length: this.n }, () => ({
          edge_id: e0.id,
          s: this.rng(),
          weight: 1 / this.n,
          heading: yawDeg,
        }));
      }
    }
    this.normalize();
  }

  step(dt: number, speed: number, yawDeg: number, lux: number, baroHpa: number): void {
    const dist = Math.max(0, speed) * dt;
    const next: IParticle[] = [];
    for (const p of this.particles) {
      const edge = edgeById(this.graph, p.edge_id);
      if (!edge) continue;
      let s = p.s + dist / Math.max(1e-3, edge.length_m);
      let heading = p.heading;
      let id = p.edge_id;
      let w = p.weight;

      const remaining = 1 - p.s;
      const metresToNode = remaining * edge.length_m;
      const approaching = metresToNode < adaptiveHorizon(edge, speed);

      if (s >= 1) {
        const outs = outgoing(this.graph, edge.to);
        if (outs.length === 0) {
          s = 1;
        } else {
          const scored = outs.map((o) => {
            const dH = circDiff(o.heading_deg, yawDeg);
            const sigma = outs.length <= 2 ? 18 : 12;
            const lh = Math.exp(-0.5 * (dH / sigma) ** 2);
            return { o, lh };
          });
          const sum = scored.reduce((a, b) => a + b.lh, 0) || 1;
          let u = this.rng() * sum;
          let chosen = scored[0]!.o;
          for (const sc of scored) {
            u -= sc.lh;
            if (u <= 0) {
              chosen = sc.o;
              break;
            }
          }
          const leftover = (s - 1) * edge.length_m;
          id = chosen.id;
          s = leftover / Math.max(1e-3, chosen.length_m);
          heading = chosen.heading_deg;
          const dH = circDiff(chosen.heading_deg, yawDeg);
          w *= Math.exp(-0.5 * (dH / 14) ** 2);
        }
      } else {
        const dH = circDiff(edge.heading_deg, yawDeg);
        const sigma = approaching ? 10 : 28;
        w *= Math.exp(-0.5 * (dH / sigma) ** 2);
        heading = edge.heading_deg;
        if (edge.tunnel && edge.light_spacing_m) {
          w *= lightCountLikelihood(s * edge.length_m, edge.light_spacing_m, lux);
        }
        if (edge.garage) {
          w *= baroLikelihood(this.graph, edge, baroHpa);
        }
      }
      next.push({ edge_id: id, s: Math.min(0.999, Math.max(0, s)), weight: Math.max(1e-12, w), heading });
      this.junctionBoost = approaching;
    }
    this.particles = next;
    this.normalize();
    if (this.ess() < this.n * 0.35) this.resample();
  }

  estimate(state: INavState): INavState {
    if (this.particles.length === 0) return { ...state, mode: "ins" };
    const byEdge: Record<string, number> = {};
    for (const p of this.particles) {
      byEdge[p.edge_id] = (byEdge[p.edge_id] ?? 0) + p.weight;
    }
    let bestId = this.particles[0]!.edge_id;
    let bestW = -1;
    for (const [id, w] of Object.entries(byEdge)) {
      if (w > bestW) {
        bestW = w;
        bestId = id;
      }
    }
    const edge = edgeById(this.graph, bestId);
    if (!edge) return { ...state, branch_posteriors: byEdge, mode: "ins" };
    const meanS =
      this.particles.filter((p) => p.edge_id === bestId).reduce((a, p) => a + p.s * p.weight, 0) /
      Math.max(1e-9, bestW);
    const { lat, lon, alt } = interpolateEdge(this.graph, edge, meanS);
    this.lastEdge = bestId;
    return {
      ...state,
      lat,
      lon,
      alt,
      edge_id: bestId,
      branch_posteriors: byEdge,
      mode: state.gnss_aided ? "gnss" : "graph",
      yaw: (edge.heading_deg * Math.PI) / 180,
    };
  }

  mapProject(lat: number, lon: number, yawDeg: number): { lat: number; lon: number; edge_id: string; residual_m: number } {
    const cands = nearestEdges(this.graph, lat, lon, 5);
    let best = cands[0];
    let bestScore = Infinity;
    for (const e of cands) {
      const dH = circDiff(e.heading_deg, yawDeg);
      const { lat: a, lon: b } = interpolateEdge(this.graph, e, projectS(this.graph, e, lat, lon));
      const d = haversineM(lat, lon, a, b);
      const score = d + 0.15 * dH;
      if (score < bestScore) {
        bestScore = score;
        best = e;
      }
    }
    if (!best) return { lat, lon, edge_id: "", residual_m: 0 };
    const s = projectS(this.graph, best, lat, lon);
    const p = interpolateEdge(this.graph, best, s);
    return { lat: p.lat, lon: p.lon, edge_id: best.id, residual_m: haversineM(lat, lon, p.lat, p.lon) };
  }

  private normalize(): void {
    const s = this.particles.reduce((a, p) => a + p.weight, 0) || 1;
    for (const p of this.particles) p.weight /= s;
  }

  private ess(): number {
    const ss = this.particles.reduce((a, p) => a + p.weight * p.weight, 0);
    return ss > 0 ? 1 / ss : 0;
  }

  private resample(): void {
    const n = this.particles.length;
    const cdf: number[] = [];
    let acc = 0;
    for (const p of this.particles) {
      acc += p.weight;
      cdf.push(acc);
    }
    const out: IParticle[] = [];
    let i = 0;
    const u0 = this.rng() / n;
    for (let j = 0; j < n; j++) {
      const u = u0 + j / n;
      while (i < cdf.length - 1 && cdf[i]! < u) i += 1;
      const src = this.particles[i]!;
      out.push({ ...src, weight: 1 / n, s: clamp01(src.s + 0.002 * gauss(this.rng)) });
    }
    this.particles = out;
  }
}

function adaptiveHorizon(edge: IGraphEdge, speed: number): number {
  // [F10] spend heading compute near junctions. Horizon grows with speed.
  return Math.max(8, Math.min(28, 6 + speed * 0.8)) * (edge.tunnel ? 1.2 : 1);
}

function lightCountLikelihood(along: number, spacing: number, lux: number): number {
  // Count pulses from portal, do NOT phase-match [F11].
  if (spacing <= 0) return 1;
  const expected = Math.floor(along / spacing);
  const bright = lux > 40;
  return bright ? 1.05 : expected > 0 ? 0.98 : 1;
}

function baroLikelihood(graph: IRoadGraph, edge: IGraphEdge, hpa: number): number {
  const from = nodeById(graph, edge.from);
  if (!from) return 1;
  const expected = 1013.25 * Math.exp(-from.alt / 8435);
  const dh = (hpa - expected) * 8.435;
  return Math.exp(-0.5 * (dh / 3) ** 2);
}

function circDiff(a: number, b: number): number {
  let d = wrap360(a) - wrap360(b);
  if (d > 180) d -= 360;
  if (d < -180) d += 360;
  return Math.abs(d);
}

function clamp01(x: number): number {
  return Math.max(0, Math.min(1, x));
}
