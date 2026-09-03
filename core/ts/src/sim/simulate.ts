/**
 * Physics simulator: leaning single-track vehicle + LSM6DSM-class MEMS noise.
 * A bicycle is kinematically a scooter. Generates frozen log schema §5.8.
 */

import type { ISensorFrame, IGnssFix, ILogMeta, IRoadGraph } from "../types/index.ts";
import { G, gauss, mulberry32, deg2rad, hypot3 } from "../math.ts";
import { campusGraph, ROUTES, routeEdges, CAMPUS_ORIGIN } from "./campus.ts";
import { interpolateEdge, edgeById, nodeById } from "../graphpf/index.ts";
import { yawRateFromLean } from "../leansolver/index.ts";

export interface TruthSample {
  t_ns: number;
  lat: number;
  lon: number;
  alt: number;
  ve: number;
  vn: number;
  yaw: number;
  lean: number;
  speed: number;
  edge_id: string;
  gnss_visible: boolean;
}

export interface SimulatedLog {
  meta: ILogMeta;
  imu: ISensorFrame[];
  gnss: IGnssFix[];
  truth: TruthSample[];
  graph: IRoadGraph;
}

export interface SimConfig {
  route: readonly string[];
  vehicle: ILogMeta["vehicle"];
  hz: number;
  speed: number;
  seed: number;
  leanScale: number;
  mountNoise: number;
  gyroBias: number;
  name: string;
}

const LSM = {
  gyro_arw: (3.8e-3 * Math.PI) / 180, // rad/s/√Hz
  accel_nd: 90e-6 * G, // m/s²/√Hz
  vib_a: 0.15 * G,
  vib_w: 0.08,
};

export function defaultConfigs(): Record<string, SimConfig> {
  return {
    act1: {
      route: ROUTES.act1_handoff,
      vehicle: "bicycle",
      hz: 50,
      speed: 1.45,
      seed: 11,
      leanScale: 0.35,
      mountNoise: 0.02,
      gyroBias: 0.002,
      name: "act1_handoff",
    },
    act2: {
      route: ROUTES.act2_bicycle,
      vehicle: "bicycle",
      hz: 50,
      speed: 5.5,
      seed: 22,
      leanScale: 1,
      mountNoise: 0.04,
      gyroBias: 0.003,
      name: "act2_bicycle",
    },
    act3: {
      route: ROUTES.act3_tunnel,
      vehicle: "scooter",
      hz: 50,
      speed: 16.67,
      seed: 33,
      leanScale: 0.7,
      mountNoise: 0.03,
      gyroBias: 0.004,
      name: "act3_tunnel",
    },
    act4: {
      route: [...ROUTES.act4_branch25, "j15", "j15a"],
      vehicle: "scooter",
      hz: 50,
      speed: 8,
      seed: 44,
      leanScale: 1,
      mountNoise: 0.03,
      gyroBias: 0.003,
      name: "act4_branch",
    },
  };
}

export function simulate(cfg: SimConfig): SimulatedLog {
  const graph = campusGraph();
  const edgeIds = routeEdges(graph, cfg.route);
  const rng = mulberry32(cfg.seed);
  const n = gauss.bind(null, rng);

  const imu: ISensorFrame[] = [];
  const gnss: IGnssFix[] = [];
  const truth: TruthSample[] = [];

  const dt = 1 / cfg.hz;
  let t = 0;
  let t_ns = 0;
  let speed = cfg.speed * 0.2;

  const totalLen = edgeIds.reduce((s, id) => s + (edgeById(graph, id)?.length_m ?? 0), 0);

  let dist = 0;
  let phi = 0;
  let yaw = 0;

  const bg: [number, number, number] = [cfg.gyroBias * 0.4, cfg.gyroBias * 0.2, cfg.gyroBias];

  while (dist < totalLen - 0.05) {
    const { edge, s, along } = locate(graph, edgeIds, dist);
    const p = interpolateEdge(graph, edge, s);
    const nextD = Math.min(totalLen, dist + 0.6);
    const nxt = locate(graph, edgeIds, nextD);
    const p2 = interpolateEdge(graph, nxt.edge, nxt.s);

    const dE = (p2.lon - p.lon) * 111412.84 * Math.cos((p.lat * Math.PI) / 180);
    const dN = (p2.lat - p.lat) * 111132.92;
    const pathYaw = Math.atan2(dE, dN);

    const target = cfg.speed;
    speed += (target - speed) * 0.08 + 0.05 * n();
    speed = Math.max(0.3, speed);

    let psiDot = 0;
    if (t > 0) psiDot = wrap(pathYaw - yaw) / dt;
    yaw = pathYaw;

    const phiTarget = Math.atan2(speed * psiDot * cfg.leanScale, G);
    phi += (phiTarget - phi) * 0.45;
    const phiDot = (phiTarget - phi) / Math.max(dt, 1e-3) * 0.45;

    // Body gyro from F1: ω = [φ̇, ψ̇ sin φ, ψ̇ cos φ]
    const gx = phiDot + LSM.vib_w * n() + bg[0] + LSM.gyro_arw * Math.sqrt(cfg.hz) * n();
    const gy = psiDot * Math.sin(phi) + LSM.vib_w * 0.5 * n() + bg[1] + LSM.gyro_arw * Math.sqrt(cfg.hz) * n();
    const gz = psiDot * Math.cos(phi) + LSM.vib_w * 0.4 * n() + bg[2] + LSM.gyro_arw * Math.sqrt(cfg.hz) * n();

    // Coordinated-turn specific force ≈ [0, 0, g/cos φ] plus along-track accel
    const aFwd = 0.1 * n();
    const cphi = Math.cos(phi) || 1e-3;
    const ax = aFwd + LSM.vib_a * 0.3 * n() + LSM.accel_nd * Math.sqrt(cfg.hz) * n();
    const ay = LSM.vib_a * 0.4 * n() + LSM.accel_nd * Math.sqrt(cfg.hz) * n();
    const az = G / cphi + LSM.vib_a * n() + LSM.accel_nd * Math.sqrt(cfg.hz) * n();

    const tunnel = edge.tunnel;
    const garage = edge.garage;
    const gnss_visible = !tunnel && !garage;
    const lux = tunnel
      ? pulseLux(along, edge.light_spacing_m ?? 20, rng)
      : garage
        ? 8 + 4 * rng()
        : 420 + 40 * n();
    const pressure = 1013.25 * Math.exp(-(CAMPUS_ORIGIN.alt + p.alt) / 8435) + 0.04 * n();

    imu.push({
      t_ns,
      ax: ax + cfg.mountNoise * n(),
      ay: ay + cfg.mountNoise * n(),
      az,
      gx,
      gy,
      gz,
      mx: 18 * Math.cos(yaw) + 3 * n(),
      my: 18 * Math.sin(yaw) + 3 * n(),
      mz: 38 + 2 * n(),
      pressure_hpa: pressure,
      lux,
    });

    truth.push({
      t_ns,
      lat: p.lat,
      lon: p.lon,
      alt: p.alt,
      ve: speed * Math.sin(yaw),
      vn: speed * Math.cos(yaw),
      yaw,
      lean: phi,
      speed,
      edge_id: edge.id,
      gnss_visible,
    });

    if (gnss_visible && t_ns % 1_000_000_000 < dt * 1e9) {
      gnss.push({
        t_ns,
        lat: p.lat + (2.2 * n()) / 111132,
        lon: p.lon + (2.2 * n()) / (111412 * Math.cos(deg2rad(p.lat))),
        alt: p.alt + 3 * n(),
        speed: speed + 0.25 * n(),
        bearing: ((yaw * 180) / Math.PI + 360 + 3 * n()) % 360,
        acc_h: 3.5,
        acc_v: 6,
        n_sats: 9 + Math.floor(rng() * 4),
      });
    }

    dist += speed * dt;
    t += dt;
    t_ns = Math.round(t * 1e9);
  }

  const start = truth[0]!;
  return {
    meta: {
      phone_model: "Pixel 7 (simulated LSM6DSM class)",
      mount_type: cfg.vehicle === "car" ? "dash" : "handlebar",
      vehicle: cfg.vehicle,
      rider: "sim",
      route_id: cfg.name,
      loop_closure: { lat: start.lat, lon: start.lon },
      notes: `synthetic ${cfg.vehicle} ${cfg.name} totalLen=${totalLen.toFixed(1)}m`,
      imu_hz: cfg.hz,
      leans: cfg.vehicle !== "car",
    },
    imu,
    gnss,
    truth,
    graph,
  };
}

function locate(graph: IRoadGraph, edgeIds: string[], dist: number) {
  let acc = 0;
  for (const id of edgeIds) {
    const e = edgeById(graph, id)!;
    if (dist <= acc + e.length_m) {
      const s = (dist - acc) / e.length_m;
      return { edge: e, s, along: dist - acc };
    }
    acc += e.length_m;
  }
  const last = edgeById(graph, edgeIds[edgeIds.length - 1]!)!;
  return { edge: last, s: 1, along: last.length_m };
}

function wrap(a: number): number {
  while (a > Math.PI) a -= 2 * Math.PI;
  while (a < -Math.PI) a += 2 * Math.PI;
  return a;
}

function pulseLux(along: number, spacing: number, rng: () => number): number {
  const phase = (along % spacing) / spacing;
  const near = phase < 0.08 || phase > 0.92;
  const detect = rng() > 0.4;
  if (near && detect) return 80 + 40 * rng();
  return 4 + 6 * rng();
}

export function logToCsv(log: SimulatedLog): { imu: string; gnss: string; meta: string } {
  const imu =
    "t_ns,ax,ay,az,gx,gy,gz,mx,my,mz,pressure_hpa,lux\n" +
    log.imu
      .map(
        (f) =>
          `${f.t_ns},${f.ax},${f.ay},${f.az},${f.gx},${f.gy},${f.gz},${f.mx},${f.my},${f.mz},${f.pressure_hpa},${f.lux}`,
      )
      .join("\n");
  const gnss =
    "t_ns,lat,lon,alt,speed,bearing,acc_h,acc_v,n_sats\n" +
    log.gnss
      .map(
        (g) =>
          `${g.t_ns},${g.lat},${g.lon},${g.alt},${g.speed},${g.bearing},${g.acc_h},${g.acc_v},${g.n_sats}`,
      )
      .join("\n");
  return { imu, gnss, meta: JSON.stringify(log.meta, null, 2) };
}

export { CAMPUS_ORIGIN, hypot3, yawRateFromLean };
