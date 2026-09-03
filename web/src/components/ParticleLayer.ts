/**
 * Graph particles → GeoJSON points for MapLibre / deck.gl.
 * `s` is arc-length fraction along the edge (0 at `from`, 1 at `to`).
 */

export type ParticleSample = {
  edge_id: string;
  s: number;
  weight: number;
};

export type GraphNodeLike = {
  id: string;
  lat: number;
  lon: number;
};

export type GraphEdgeLike = {
  id: string;
  from: string;
  to: string;
};

export type GraphLike = {
  nodes: readonly GraphNodeLike[];
  edges: readonly GraphEdgeLike[];
};

export type ParticlePointProperties = {
  edge_id: string;
  s: number;
  weight: number;
};

export type ParticleFeature = {
  type: "Feature";
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: ParticlePointProperties;
};

export type ParticleFeatureCollection = {
  type: "FeatureCollection";
  features: ParticleFeature[];
};

export const emptyParticleLayer: ParticleFeatureCollection = {
  type: "FeatureCollection",
  features: [],
};

function clamp01(x: number): number {
  if (!Number.isFinite(x)) return 0;
  return Math.max(0, Math.min(1, x));
}

function indexById<T extends { id: string }>(rows: readonly T[]): Map<string, T> {
  const m = new Map<string, T>();
  for (const row of rows) m.set(row.id, row);
  return m;
}

function interpolate(a: GraphNodeLike, b: GraphNodeLike, s: number): [number, number] {
  const u = clamp01(s);
  const lat = a.lat + (b.lat - a.lat) * u;
  const lon = a.lon + (b.lon - a.lon) * u;
  return [lon, lat];
}

/** GeoJSON FeatureCollection of particle positions on the road graph. */
export function particlesToGeoJSON(
  particles: readonly ParticleSample[],
  graph: GraphLike,
): ParticleFeatureCollection {
  const nodes = indexById(graph.nodes);
  const edges = indexById(graph.edges);
  const features: ParticleFeature[] = [];

  for (const p of particles) {
    const edge = edges.get(p.edge_id);
    if (!edge) continue;
    const from = nodes.get(edge.from);
    const to = nodes.get(edge.to);
    if (!from || !to) continue;
    if (!Number.isFinite(from.lat) || !Number.isFinite(from.lon)) continue;
    if (!Number.isFinite(to.lat) || !Number.isFinite(to.lon)) continue;

    const s = clamp01(p.s);
    const weight = Number.isFinite(p.weight) ? p.weight : 0;
    features.push({
      type: "Feature",
      geometry: { type: "Point", coordinates: interpolate(from, to, s) },
      properties: { edge_id: p.edge_id, s, weight },
    });
  }

  return { type: "FeatureCollection", features };
}
