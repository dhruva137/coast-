/**
 * VectorMapLocator — edge embeddings + soft assignment [F9, F10].
 *
 * Faster path than always-on GraphParticleFilter: locate by cosine similarity
 * + distance kernel, keep a 1-D Gaussian belief on along-edge s, and only enter
 * junction (branching) mode near nodes. Map-matching itself is prior art
 * (Newson & Krumm); we claim application + adaptive junction compute + lean
 * composition elsewhere in the stack.
 */

import type { IRoadGraph, IGraphEdge, INavState } from "../types/index.ts";
import { haversineM, wrap360, deg2rad, clamp } from "../math.ts";
import { edgeById, interpolateEdge, outgoing, projectS } from "./geometry.ts";

/** [sinθ, cosθ, length_norm, tunnel_flag, garage_flag] */
export type EdgeFeature = readonly [number, number, number, number, number];

export interface VectorLocatorConfig {
  /** Softmax temperature; lower → peakier. */
  temperature?: number;
  /** Distance kernel σ in metres. */
  distSigmaM?: number;
  /** Default top-k edges returned / considered. */
  topK?: number;
  /** Weight on cosine similarity vs distance log-kernel. */
  cosWeight?: number;
  /** Weight on distance kernel (log domain contribution). */
  distWeight?: number;
  /** Collapse to single edge when mass ≥ this. */
  collapseMass?: number;
  /** Process noise on s per √metre travelled. */
  sProcessNoise?: number;
}

export interface EdgePosterior {
  edge_id: string;
  weight: number;
  s: number;
  cosine: number;
  dist_m: number;
}

export interface VectorBelief {
  edge_id: string;
  s_mean: number;
  s_var: number;
  mode: "edge" | "junction";
  branch_posteriors: Record<string, number>;
  junctionBoost: boolean;
}

export interface LocateQuery {
  yawDeg: number;
  speed: number;
  lat: number;
  lon: number;
  topK?: number;
}

const DEFAULTS: Required<VectorLocatorConfig> = {
  temperature: 0.35,
  distSigmaM: 25,
  topK: 5,
  cosWeight: 1.0,
  distWeight: 1.0,
  collapseMass: 0.72,
  sProcessNoise: 0.02,
};

export class VectorMapLocator {
  graph: IRoadGraph;
  private cfg: Required<VectorLocatorConfig>;
  private feats = new Map<string, EdgeFeature>();
  private Lref = 1;
  belief: VectorBelief | null = null;
  junctionBoost = false;

  constructor(graph: IRoadGraph, cfg: VectorLocatorConfig = {}) {
    this.graph = graph;
    this.cfg = { ...DEFAULTS, ...cfg };
    this.rebuildFeatures();
  }

  setGraph(graph: IRoadGraph): void {
    this.graph = graph;
    this.rebuildFeatures();
    this.belief = null;
  }

  /** Precompute edge feature vectors. */
  rebuildFeatures(): void {
    this.feats.clear();
    let maxL = 1;
    for (const e of this.graph.edges) maxL = Math.max(maxL, e.length_m);
    this.Lref = maxL;
    for (const e of this.graph.edges) {
      this.feats.set(e.id, edgeFeature(e, maxL));
    }
  }

  featureOf(edgeId: string): EdgeFeature | undefined {
    return this.feats.get(edgeId);
  }

  /**
   * Soft edge posteriors via softmax( cosWeight·cosine + distWeight·log κ(d) ).
   * Along-edge s from geometric projection of pos_hint onto each candidate.
   */
  locate(q: LocateQuery): EdgePosterior[] {
    const k = q.topK ?? this.cfg.topK;
    const yawR = deg2rad(q.yawDeg);
    // Query: heading dominant; length/flags neutral so they do not dominate cosine.
    const query: EdgeFeature = [Math.sin(yawR), Math.cos(yawR), 0.5, 0.5, 0.5];
    const scored: EdgePosterior[] = [];

    for (const e of this.graph.edges) {
      const feat = this.feats.get(e.id)!;
      const cos = cosineSimilarity(query, feat);
      const s = projectS(this.graph, e, q.lat, q.lon);
      const p = interpolateEdge(this.graph, e, s);
      const dist = haversineM(q.lat, q.lon, p.lat, p.lon);
      const logKern = -0.5 * (dist / this.cfg.distSigmaM) ** 2;
      const score = this.cfg.cosWeight * cos + this.cfg.distWeight * logKern;
      scored.push({ edge_id: e.id, weight: score, s, cosine: cos, dist_m: dist });
    }

    scored.sort((a, b) => b.weight - a.weight);
    const top = scored.slice(0, Math.min(k, scored.length));
    return softmaxWeights(top, this.cfg.temperature);
  }

  seed(lat: number, lon: number, yawDeg: number): void {
    const posts = this.locate({ yawDeg, speed: 0, lat, lon, topK: this.cfg.topK });
    const best = posts[0];
    if (!best) {
      this.belief = null;
      return;
    }
    this.belief = {
      edge_id: best.edge_id,
      s_mean: best.s,
      s_var: 0.01,
      mode: "edge",
      branch_posteriors: Object.fromEntries(posts.map((p) => [p.edge_id, p.weight])),
      junctionBoost: false,
    };
    this.junctionBoost = false;
  }

  /**
   * Propagate belief along edge; enter junction mode near nodes and soft-assign
   * over outgoing edges (F10). Returns updated belief.
   */
  step(dt: number, speed: number, yawDeg: number, lat: number, lon: number): VectorBelief {
    if (!this.belief) this.seed(lat, lon, yawDeg);
    let b = this.belief!;
    const edge = edgeById(this.graph, b.edge_id);
    if (!edge) {
      this.seed(lat, lon, yawDeg);
      return this.belief!;
    }

    const dist = Math.max(0, speed) * Math.max(0, dt);
    const ds = dist / Math.max(1e-3, edge.length_m);
    let s = clamp(b.s_mean + ds, 0, 0.999);
    let sVar = b.s_var + (this.cfg.sProcessNoise * Math.sqrt(dist + 1e-6)) ** 2;

    // Observation: project INS hint onto current edge (cheap Kalman-ish blend).
    const sObs = projectS(this.graph, edge, lat, lon);
    const R = 0.04; // observation variance on s
    const K = sVar / (sVar + R);
    s = s + K * (sObs - s);
    sVar = (1 - K) * sVar;
    s = clamp(s, 0, 0.999);

    const metresToNode = (1 - s) * edge.length_m;
    const horizon = adaptiveHorizon(edge, speed);
    const approaching = metresToNode < horizon;
    this.junctionBoost = approaching;

    let mode: "edge" | "junction" = approaching ? "junction" : "edge";
    let branch: Record<string, number> = { [edge.id]: 1 };
    let edgeId = edge.id;

    if (approaching || s + ds >= 0.98) {
      const outs = outgoing(this.graph, edge.to);
      if (outs.length > 0) {
        mode = "junction";
        const scored = outs.map((o) => {
          const dH = circDiff(o.heading_deg, yawDeg);
          const sigma = outs.length <= 2 ? 18 : 12;
          const lh = Math.exp(-0.5 * (dH / sigma) ** 2);
          return { o, lh };
        });
        const sum = scored.reduce((a, c) => a + c.lh, 0) || 1;
        branch = {};
        for (const sc of scored) branch[sc.o.id] = sc.lh / sum;

        // If past the node, commit to MAP outgoing and carry leftover distance.
        if (s >= 0.995 || metresToNode <= 0) {
          let best = scored[0]!;
          for (const sc of scored) if (sc.lh > best.lh) best = sc;
          const leftover = Math.max(0, (s - 1) * edge.length_m + dist * 0.05);
          edgeId = best.o.id;
          s = clamp(leftover / Math.max(1e-3, best.o.length_m), 0, 0.999);
          sVar = Math.max(sVar, 0.02);
          mode = outs.length >= 3 ? "junction" : "edge";
          // Re-normalise branch around chosen fan if still multi.
          if (mode === "edge") branch = { [edgeId]: 1 };
        }
      }
    } else {
      // Along-edge: refresh soft posteriors cheaply for API consumers.
      const posts = this.locate({ yawDeg, speed, lat, lon, topK: this.cfg.topK });
      branch = Object.fromEntries(posts.map((p) => [p.edge_id, p.weight]));
      const map = posts[0];
      if (map && map.weight >= this.cfg.collapseMass && map.edge_id !== edgeId) {
        // Only jump if residual is clearly better (avoid chatter).
        if (map.dist_m + 4 < haversineM(lat, lon, interpolateEdge(this.graph, edge, s).lat, interpolateEdge(this.graph, edge, s).lon)) {
          edgeId = map.edge_id;
          s = map.s;
          sVar = Math.max(sVar, 0.015);
        }
      }
    }

    b = {
      edge_id: edgeId,
      s_mean: s,
      s_var: Math.min(0.25, Math.max(1e-6, sVar)),
      mode,
      branch_posteriors: branch,
      junctionBoost: approaching,
    };
    this.belief = b;
    return b;
  }

  estimate(state: INavState): INavState {
    const b = this.belief;
    if (!b) return { ...state, mode: "ins" };
    const edge = edgeById(this.graph, b.edge_id);
    if (!edge) return { ...state, branch_posteriors: b.branch_posteriors, mode: "ins" };
    const { lat, lon, alt } = interpolateEdge(this.graph, edge, b.s_mean);
    // Inflate position cov from s variance (along-track only, rough).
    const alongM = Math.sqrt(b.s_var) * edge.length_m;
    const P = state.P_pos.slice();
    const inflate = alongM * alongM;
    if (P.length >= 9) {
      P[0] = (P[0] ?? 0) + inflate;
      P[4] = (P[4] ?? 0) + inflate;
    }
    return {
      ...state,
      lat,
      lon,
      alt,
      P_pos: P,
      edge_id: b.edge_id,
      branch_posteriors: b.branch_posteriors,
      mode: state.gnss_aided ? "gnss" : "graph",
      yaw: deg2rad(edge.heading_deg),
    };
  }

  /** True when caller should run GraphParticleFilter for this tick (F10). */
  shouldUseParticleFilter(): boolean {
    const b = this.belief;
    if (!b) return false;
    if (b.mode !== "junction") return false;
    const masses = Object.values(b.branch_posteriors);
    if (masses.length < 2) return false;
    const H = entropy(masses);
    // High entropy over ≥2 branches → PF earns its keep.
    return H > 0.85 || masses.length >= 3;
  }
}

export function edgeFeature(e: IGraphEdge, Lref: number): EdgeFeature {
  const th = deg2rad(e.heading_deg);
  const ln = clamp(e.length_m / Math.max(1e-3, Lref), 0, 1);
  return [Math.sin(th), Math.cos(th), ln, e.tunnel ? 1 : 0, e.garage ? 1 : 0];
}

export function cosineSimilarity(a: EdgeFeature, b: EdgeFeature): number {
  let dot = 0, na = 0, nb = 0;
  for (let i = 0; i < 5; i++) {
    const x = a[i]!, y = b[i]!;
    dot += x * y;
    na += x * x;
    nb += y * y;
  }
  const d = Math.sqrt(na) * Math.sqrt(nb);
  return d < 1e-12 ? 0 : dot / d;
}

function softmaxWeights(items: EdgePosterior[], temperature: number): EdgePosterior[] {
  if (items.length === 0) return items;
  const t = Math.max(1e-3, temperature);
  const maxS = Math.max(...items.map((x) => x.weight));
  const exps = items.map((x) => Math.exp((x.weight - maxS) / t));
  const sum = exps.reduce((a, b) => a + b, 0) || 1;
  return items.map((x, i) => ({ ...x, weight: exps[i]! / sum }));
}

function adaptiveHorizon(edge: IGraphEdge, speed: number): number {
  return Math.max(8, Math.min(28, 6 + speed * 0.8)) * (edge.tunnel ? 1.2 : 1);
}

function circDiff(a: number, b: number): number {
  let d = wrap360(a) - wrap360(b);
  if (d > 180) d -= 360;
  if (d < -180) d += 360;
  return Math.abs(d);
}

function entropy(weights: number[]): number {
  const s = weights.reduce((a, b) => a + b, 0) || 1;
  let H = 0;
  for (const w of weights) {
    const p = w / s;
    if (p > 1e-12) H -= p * Math.log(p);
  }
  return H;
}
