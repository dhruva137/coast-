/**
 * Metrics — implement BEFORE any model. Loop closure is both the dev metric
 * and the demo metric. Branch-decision accuracy [F12] is what the driver feels.
 */

import type { INavState, IMetrics, IGnssFix } from "../types/index.ts";
import { haversineM } from "../math.ts";

export function pathLength(states: { lat: number; lon: number }[]): number {
  let d = 0;
  for (let i = 1; i < states.length; i++) {
    d += haversineM(states[i - 1]!.lat, states[i - 1]!.lon, states[i]!.lat, states[i]!.lon);
  }
  return d;
}

export function loopClosureError(
  states: { lat: number; lon: number }[],
  marker: { lat: number; lon: number },
): number {
  if (states.length === 0) return Infinity;
  const last = states[states.length - 1]!;
  return haversineM(last.lat, last.lon, marker.lat, marker.lon);
}

export function driftPct(errorM: number, distanceM: number): number {
  if (distanceM < 1) return 0;
  return (100 * errorM) / distanceM;
}

export function ate(est: { lat: number; lon: number }[], gt: { lat: number; lon: number }[]): number {
  const n = Math.min(est.length, gt.length);
  if (n === 0) return 0;
  let s = 0;
  for (let i = 0; i < n; i++) s += haversineM(est[i]!.lat, est[i]!.lon, gt[i]!.lat, gt[i]!.lon);
  return s / n;
}

export function rte(
  est: { lat: number; lon: number }[],
  gt: { lat: number; lon: number }[],
  window = 100,
): number {
  const n = Math.min(est.length, gt.length);
  if (n < window + 1) return ate(est, gt);
  let s = 0;
  let c = 0;
  for (let i = 0; i + window < n; i += Math.max(1, Math.floor(window / 4))) {
    s += haversineM(est[i + window]!.lat, est[i + window]!.lon, gt[i + window]!.lat, gt[i + window]!.lon);
    c += 1;
  }
  return c ? s / c : 0;
}

export function errorCdf(errors: number[], pcts = [0.5, 0.75, 0.9, 0.95]): Record<string, number> {
  const a = errors.slice().sort((x, y) => x - y);
  const out: Record<string, number> = {};
  for (const p of pcts) {
    const i = Math.min(a.length - 1, Math.max(0, Math.floor(p * a.length)));
    out[`p${Math.round(p * 100)}`] = a[i] ?? 0;
  }
  return out;
}

export function branchAccuracy(predicted: string[], truth: string[]): number {
  const n = Math.min(predicted.length, truth.length);
  if (n === 0) return 0;
  let ok = 0;
  for (let i = 0; i < n; i++) if (predicted[i] === truth[i]) ok += 1;
  return ok / n;
}

export function leanRmseDeg(est: number[], gt: number[]): number {
  const n = Math.min(est.length, gt.length);
  if (n === 0) return 0;
  let s = 0;
  for (let i = 0; i < n; i++) {
    const d = ((est[i]! - gt[i]!) * 180) / Math.PI;
    s += d * d;
  }
  return Math.sqrt(s / n);
}

export function summarize(
  est: INavState[],
  gt: { lat: number; lon: number }[],
  marker: { lat: number; lon: number },
  branches?: { pred: string[]; truth: string[] },
  lean?: { est: number[]; gt: number[] },
  latencyMs = 0,
): IMetrics {
  const dist = pathLength(gt.length ? gt : est);
  const lc = loopClosureError(est, marker);
  return {
    loop_closure_m: lc,
    distance_m: dist,
    drift_pct: driftPct(lc, dist),
    ate_m: ate(est, gt),
    rte_m: rte(est, gt),
    branch_accuracy: branches ? branchAccuracy(branches.pred, branches.truth) : 0,
    lean_rmse_deg: lean ? leanRmseDeg(lean.est, lean.gt) : 0,
    latency_ms: latencyMs,
  };
}

export function gnssOutageMask(fixes: IGnssFix[], t_ns: number, gapNs = 1.5e9): boolean {
  if (fixes.length === 0) return true;
  let nearest = Infinity;
  for (const f of fixes) {
    const d = Math.abs(f.t_ns - t_ns);
    if (d < nearest) nearest = d;
  }
  return nearest > gapNs;
}
