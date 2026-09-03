/** Shared road-graph geometry helpers (no locator / PF dependency). */

import type { IRoadGraph, IGraphEdge } from "../types/index.ts";
import { haversineM, llaToEnu, headingBetween, enuToLla } from "../math.ts";

export function nearestEdges(graph: IRoadGraph, lat: number, lon: number, k: number): IGraphEdge[] {
  const scored = graph.edges.map((e) => {
    const s = projectS(graph, e, lat, lon);
    const p = interpolateEdge(graph, e, s);
    return { e, d: haversineM(lat, lon, p.lat, p.lon) };
  });
  scored.sort((a, b) => a.d - b.d);
  return scored.slice(0, k).map((x) => x.e);
}

export function interpolateEdge(graph: IRoadGraph, e: IGraphEdge, s: number): { lat: number; lon: number; alt: number } {
  const a = nodeById(graph, e.from)!;
  const b = nodeById(graph, e.to)!;
  const u = clamp01(s);
  return {
    lat: a.lat + (b.lat - a.lat) * u,
    lon: a.lon + (b.lon - a.lon) * u,
    alt: a.alt + (b.alt - a.alt) * u,
  };
}

export function projectS(graph: IRoadGraph, e: IGraphEdge, lat: number, lon: number): number {
  const a = nodeById(graph, e.from)!;
  const b = nodeById(graph, e.to)!;
  const o = graph.origin;
  const pa = llaToEnu(o, a.lat, a.lon, a.alt);
  const pb = llaToEnu(o, b.lat, b.lon, b.alt);
  const pq = llaToEnu(o, lat, lon, a.alt);
  const vx = pb.e - pa.e, vy = pb.n - pa.n;
  const wx = pq.e - pa.e, wy = pq.n - pa.n;
  const den = vx * vx + vy * vy || 1;
  return clamp01((wx * vx + wy * vy) / den);
}

export function outgoing(graph: IRoadGraph, nodeId: string): IGraphEdge[] {
  return graph.edges.filter((e) => e.from === nodeId);
}

export function edgeById(graph: IRoadGraph, id: string): IGraphEdge | undefined {
  return graph.edges.find((e) => e.id === id);
}

export function nodeById(graph: IRoadGraph, id: string) {
  return graph.nodes.find((n) => n.id === id);
}

function clamp01(x: number): number {
  return Math.max(0, Math.min(1, x));
}

export { headingBetween, enuToLla };
