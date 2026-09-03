/**
 * Full navigation engine: preprocess → odo → lean → InEKF → graph PF.
 * Also runs a car-style baseline (ψ̇ = ω_z) on the same log for Act 2.
 */

import type { ISensorFrame, IGnssFix, INavState, IRoadGraph, ILogMeta } from "./types/index.ts";
import { BiasCalibrator, SixAxisFilter, resampleLinear } from "./preprocess/index.ts";
import { FrequencyDecoupledOdo } from "./inference/index.ts";
import { InvariantEKF } from "./inekf/index.ts";
import { GraphParticleFilter, VectorMapLocator } from "./graphpf/index.ts";
import { gnssOutageMask } from "./metrics/index.ts";
import { solveLean } from "./leansolver/index.ts";
import { createLightCounter, stepLightCount } from "./aiding/index.ts";
import { campusGraph } from "./sim/campus.ts";

export interface EngineResult {
  ours: INavState[];
  baseline: INavState[];
  meta: ILogMeta;
}

export interface RunOpts {
  twoWheeler?: boolean;
  graph?: IRoadGraph;
  targetHz?: number;
  /** After this timestamp, ignore GNSS (demo: show open-loop DR). */
  forceOutageAfterNs?: number;
  /**
   * Use VectorMapLocator (edge embeddings + Gaussian-on-s) instead of always-on
   * GraphParticleFilter. Falls back to PF near high-entropy junctions [F10].
   */
  useVectorLocator?: boolean;
}

export function runEngine(
  imu: ISensorFrame[],
  gnss: IGnssFix[],
  meta: ILogMeta,
  opts: RunOpts = {},
): EngineResult {
  const hz = opts.targetHz ?? Math.min(50, meta.imu_hz || 50);
  const frames = resampleLinear(imu, hz);
  const graph = opts.graph ?? campusGraph();
  const twoWheeler = opts.twoWheeler ?? meta.leans ?? meta.vehicle !== "car";
  const cut = opts.forceOutageAfterNs;
  const useVec = opts.useVectorLocator ?? false;

  const ours = runOne(frames, gnss, graph, true, twoWheeler, true, cut, useVec);
  const baseline = runOne(frames, gnss, graph, false, false, false, cut, false);
  return { ours, baseline, meta };
}

function runOne(
  frames: ISensorFrame[],
  gnss: IGnssFix[],
  graph: IRoadGraph,
  leanAware: boolean,
  twoWheeler: boolean,
  useGraph: boolean,
  forceOutageAfterNs?: number,
  useVectorLocator = false,
): INavState[] {
  const filt = new SixAxisFilter(8, 50);
  const cal = new BiasCalibrator();
  const odo = new FrequencyDecoupledOdo(50);
  const origin = graph.origin;
  const ekf = new InvariantEKF(origin, leanAware && twoWheeler);
  const pf = new GraphParticleFilter(graph, { n: 180, seed: leanAware ? 1 : 2 });
  const vec = useVectorLocator ? new VectorMapLocator(graph) : null;
  const lights = createLightCounter();

  if (gnss[0]) ekf.seedFromGnss(gnss[0]);
  else if (frames[0]) {
    ekf.seedFromGnss({
      t_ns: frames[0].t_ns,
      lat: origin.lat,
      lon: origin.lon,
      alt: origin.alt,
      speed: 0,
      bearing: 0,
      acc_h: 5,
      acc_v: 8,
      n_sats: 0,
    });
  }
  const seedState = ekf.toState(0);
  pf.seed(seedState.lat, seedState.lon, 0);
  vec?.seed(seedState.lat, seedState.lon, 0);

  const out: INavState[] = [];
  let gi = 0;
  let lastT = frames[0]?.t_ns ?? 0;
  let light = lights;

  for (const raw of frames) {
    cal.observe(raw);
    const f = filt.apply(cal.apply(raw));
    const forced = forceOutageAfterNs !== undefined && f.t_ns >= forceOutageAfterNs;
    const denied = forced || gnssOutageMask(gnss, f.t_ns);
    if (denied) ekf.markOutage();

    while (gi < gnss.length && gnss[gi]!.t_ns <= f.t_ns) {
      if (!denied && !gnssOutageMask([gnss[gi]!], f.t_ns, 0.8e9)) ekf.updateGnss(gnss[gi]!);
      gi += 1;
    }

    const lastFix = gnss[Math.max(0, gi - 1)];
    if (lastFix && lastFix.speed > 0.3) odo.setSpeed(lastFix.speed);
    const o = odo.push(f);

    ekf.propagate(f);
    const dt = (f.t_ns - lastT) / 1e9;
    lastT = f.t_ns;
    if (!leanAware) {
      ekf.lean = 0;
    } else {
      const sol = solveLean({ gy: f.gy, gz: f.gz, gx: f.gx, speed: o.speed || ekf.toState(f.t_ns).speed, phi0: ekf.lean });
      ekf.lean = sol.phi;
    }

    let st = ekf.toState(f.t_ns);
    const yawDeg = (st.yaw * 180) / Math.PI;
    if (denied && useGraph) {
      const edge = graph.edges.find((e) => e.id === st.edge_id) ?? graph.edges.find((e) => e.tunnel);
      if (edge?.light_spacing_m) {
        light = stepLightCount(light, f.lux, f.t_ns, edge.light_spacing_m);
      }
      if (vec) {
        vec.step(Math.max(0.001, dt), st.speed, yawDeg, st.lat, st.lon);
        if (vec.shouldUseParticleFilter()) {
          // F10: expensive branching only when vector belief is multimodal at a junction.
          pf.step(Math.max(0.001, dt), st.speed, yawDeg, f.lux, f.pressure_hpa);
          st = pf.estimate(st);
        } else {
          st = vec.estimate(st);
        }
      } else {
        pf.step(Math.max(0.001, dt), st.speed, yawDeg, f.lux, f.pressure_hpa);
        st = pf.estimate(st);
      }
    } else if (!denied && useGraph) {
      const proj = pf.mapProject(st.lat, st.lon, yawDeg);
      pf.seed(proj.lat, proj.lon, yawDeg);
      vec?.seed(proj.lat, proj.lon, yawDeg);
      st = { ...st, edge_id: proj.edge_id, mode: "gnss" };
    } else {
      st = { ...st, mode: denied ? "ins" : "gnss" };
    }
    out.push(st);
  }
  return out;
}

export function downsample<T>(arr: T[], every: number): T[] {
  if (every <= 1) return arr;
  const out: T[] = [];
  for (let i = 0; i < arr.length; i += every) out.push(arr[i]!);
  return out;
}
