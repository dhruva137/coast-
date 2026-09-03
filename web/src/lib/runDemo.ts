import {
  defaultConfigs,
  simulate,
  runEngine,
  summarize,
  downsample,
  campusGraph,
  type SimulatedLog,
  type INavState,
  type IMetrics,
  type IRoadGraph,
} from "@sih26168/nav-core";

export type ActId = 1 | 2 | 3 | 4 | 5;

export interface DemoBundle {
  act: ActId;
  log: SimulatedLog;
  ours: INavState[];
  baseline: INavState[];
  metricsOurs: IMetrics;
  metricsBase: IMetrics;
  graph: IRoadGraph;
}

const ACTS: Record<ActId, { key: keyof ReturnType<typeof defaultConfigs>; title: string; line: string }> = {
  1: { key: "act1", title: "The handoff", line: "GPS dies in the basement. The dot keeps moving. Loop closure is the score." },
  2: { key: "act2", title: "The vehicle", line: "Same bicycle ride. Car-style baseline vs lean-aware IDR. Watch the turns." },
  3: { key: "act3", title: "The benchmark", line: "Underpass replay. ISRO asked <10% drift and <100 m per km." },
  4: { key: "act4", title: "The metric", line: "Not drift %. Did we take the right ramp?" },
  5: { key: "act2", title: "The ask", line: "200M two-wheelers. Any phone. Zero extra hardware. Ships as an SDK." },
};

export const ACT_COPY = ACTS;

export function buildDemo(act: ActId): DemoBundle {
  const cfg = { ...defaultConfigs()[ACTS[act].key] };
  if (act === 3) cfg.speed = 16.67;
  const log = simulate(cfg);
  const graph = campusGraph();
  const forceOutageAfterNs = act === 2 || act === 5 ? 3e9 : undefined;
  const { ours, baseline } = runEngine(log.imu, log.gnss, log.meta, {
    graph,
    targetHz: 25,
    twoWheeler: true,
    useVectorLocator: true,
    forceOutageAfterNs,
  });
  const o = downsample(ours, 2);
  const b = downsample(baseline, 2);
  const truth = downsample(log.truth, Math.max(1, Math.floor(log.truth.length / o.length)));
  const marker = log.meta.loop_closure;
  const metricsOurs = summarize(o, truth, marker, {
    pred: o.map((s) => s.edge_id ?? ""),
    truth: truth.map((t) => t.edge_id),
  }, { est: o.map((s) => s.lean), gt: truth.map((t) => t.lean) });
  const metricsBase = summarize(b, truth, marker);
  return { act, log, ours: o, baseline: b, metricsOurs, metricsBase, graph };
}
