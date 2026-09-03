/**
 * Frozen sensor / estimator API. Do not change field names.
 * Log schema §5.8 of SIH26168_PROJECT_BIBLE.md
 */

export const DEG = Math.PI / 180;
export const RAD = 180 / Math.PI;

/** Uniform IMU+aiding frame at one timestamp. SI units. */
export interface ISensorFrame {
  t_ns: number;
  ax: number;
  ay: number;
  az: number;
  gx: number;
  gy: number;
  gz: number;
  mx: number;
  my: number;
  mz: number;
  pressure_hpa: number;
  lux: number;
}

export interface IGnssFix {
  t_ns: number;
  lat: number;
  lon: number;
  alt: number;
  speed: number;
  bearing: number;
  acc_h: number;
  acc_v: number;
  n_sats: number;
}

export interface ILogMeta {
  phone_model: string;
  mount_type: "handlebar" | "pocket" | "tankbag" | "frame" | "dash";
  vehicle: "car" | "scooter" | "motorcycle" | "bicycle";
  rider: string;
  route_id: string;
  loop_closure: { lat: number; lon: number };
  notes: string;
  imu_hz: number;
  leans: boolean;
}

export interface INavState {
  t_ns: number;
  lat: number;
  lon: number;
  alt: number;
  ve: number;
  vn: number;
  vu: number;
  roll: number;
  pitch: number;
  yaw: number;
  /** Lean estimate φ (two-wheeler), rad */
  lean: number;
  speed: number;
  /** 3x3 ENU position covariance, row-major */
  P_pos: number[];
  gnss_aided: boolean;
  edge_id: string | null;
  branch_posteriors: Record<string, number>;
  mode: "gnss" | "ins" | "graph" | "coast";
}

export interface IMetrics {
  loop_closure_m: number;
  distance_m: number;
  drift_pct: number;
  ate_m: number;
  rte_m: number;
  branch_accuracy: number;
  lean_rmse_deg: number;
  latency_ms: number;
}

export interface IGraphNode {
  id: string;
  lat: number;
  lon: number;
  alt: number;
  kind: "outdoor" | "tunnel" | "garage" | "junction" | "ramp" | "portal";
}

export interface IGraphEdge {
  id: string;
  from: string;
  to: string;
  heading_deg: number;
  length_m: number;
  tunnel: boolean;
  garage: boolean;
  light_spacing_m: number | null;
  grade: number;
  lanes: number;
}

export interface IRoadGraph {
  name: string;
  origin: { lat: number; lon: number; alt: number };
  nodes: IGraphNode[];
  edges: IGraphEdge[];
}

export interface IParticle {
  edge_id: string;
  s: number;
  weight: number;
  heading: number;
}

export interface Vec3 {
  x: number;
  y: number;
  z: number;
}