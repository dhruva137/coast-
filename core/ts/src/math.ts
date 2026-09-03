/** Small SE(3)/SO(3) helpers. No external linear-algebra dependency. */

export const G = 9.80665;

export function clamp(x: number, a: number, b: number): number {
  return Math.max(a, Math.min(b, x));
}

export function hypot3(x: number, y: number, z: number): number {
  return Math.hypot(x, y, z);
}

export function wrapPi(a: number): number {
  let x = ((a + Math.PI) % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI) - Math.PI;
  return x;
}

export function wrap360(deg: number): number {
  return ((deg % 360) + 360) % 360;
}

export function deg2rad(d: number): number {
  return (d * Math.PI) / 180;
}

export function rad2deg(r: number): number {
  return (r * 180) / Math.PI;
}

export type Mat3 = [
  number, number, number,
  number, number, number,
  number, number, number,
];

export function mat3Ident(): Mat3 {
  return [1, 0, 0, 0, 1, 0, 0, 0, 1];
}

export function mat3Mul(a: Mat3, b: Mat3): Mat3 {
  const r: number[] = [];
  for (let i = 0; i < 3; i++) {
    for (let j = 0; j < 3; j++) {
      r.push(a[i * 3 + 0]! * b[0 * 3 + j]! + a[i * 3 + 1]! * b[1 * 3 + j]! + a[i * 3 + 2]! * b[2 * 3 + j]!);
    }
  }
  return r as Mat3;
}

export function mat3T(a: Mat3): Mat3 {
  return [a[0], a[3], a[6], a[1], a[4], a[7], a[2], a[5], a[8]];
}

export function mat3Vec(a: Mat3, v: [number, number, number]): [number, number, number] {
  return [
    a[0] * v[0] + a[1] * v[1] + a[2] * v[2],
    a[3] * v[0] + a[4] * v[1] + a[5] * v[2],
    a[6] * v[0] + a[7] * v[1] + a[8] * v[2],
  ];
}

export function skew(x: number, y: number, z: number): Mat3 {
  return [0, -z, y, z, 0, -x, -y, x, 0];
}

export function so3Exp(wx: number, wy: number, wz: number): Mat3 {
  const th = Math.hypot(wx, wy, wz);
  if (th < 1e-12) {
    const K = skew(wx, wy, wz);
    return [
      1 + K[0], K[1], K[2],
      K[3], 1 + K[4], K[5],
      K[6], K[7], 1 + K[8],
    ];
  }
  const k: [number, number, number] = [wx / th, wy / th, wz / th];
  const K = skew(k[0], k[1], k[2]);
  const s = Math.sin(th);
  const c = 1 - Math.cos(th);
  const I = mat3Ident();
  const out: number[] = [];
  for (let i = 0; i < 9; i++) {
    const kk =
      (i === 0 ? k[0] * k[0] : i === 1 ? k[0] * k[1] : i === 2 ? k[0] * k[2]
        : i === 3 ? k[1] * k[0] : i === 4 ? k[1] * k[1] : i === 5 ? k[1] * k[2]
        : i === 6 ? k[2] * k[0] : i === 7 ? k[2] * k[1] : k[2] * k[2]);
    out.push(I[i]! + s * K[i]! + c * (kk - (i % 4 === 0 && i < 9 ? (i === 0 || i === 4 || i === 8 ? 1 : 0) : 0)));
  }
  // Rodrigues: I + sinθ K + (1-cosθ) K²
  const K2 = mat3Mul(K, K);
  return [
    1 + s * K[0] + c * K2[0],
    s * K[1] + c * K2[1],
    s * K[2] + c * K2[2],
    s * K[3] + c * K2[3],
    1 + s * K[4] + c * K2[4],
    s * K[5] + c * K2[5],
    s * K[6] + c * K2[6],
    s * K[7] + c * K2[7],
    1 + s * K[8] + c * K2[8],
  ];
}

export function rpyToMat(roll: number, pitch: number, yaw: number): Mat3 {
  const cr = Math.cos(roll), sr = Math.sin(roll);
  const cp = Math.cos(pitch), sp = Math.sin(pitch);
  const cy = Math.cos(yaw), sy = Math.sin(yaw);
  // ZYX: R = Rz(yaw) Ry(pitch) Rx(roll)
  return [
    cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr,
    sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr,
    -sp, cp * sr, cp * cr,
  ];
}

export function matToRpy(R: Mat3): { roll: number; pitch: number; yaw: number } {
  const pitch = Math.asin(clamp(-R[6], -1, 1));
  const roll = Math.atan2(R[7], R[8]);
  const yaw = Math.atan2(R[3], R[0]);
  return { roll, pitch, yaw };
}

/** WGS84 metres-per-degree at latitude. */
export function metersPerDeg(latDeg: number): { mLat: number; mLon: number } {
  const lat = deg2rad(latDeg);
  const mLat = 111132.92 - 559.82 * Math.cos(2 * lat) + 1.175 * Math.cos(4 * lat);
  const mLon = 111412.84 * Math.cos(lat) - 93.5 * Math.cos(3 * lat);
  return { mLat, mLon };
}

export function enuToLla(
  origin: { lat: number; lon: number; alt: number },
  e: number,
  n: number,
  u: number,
): { lat: number; lon: number; alt: number } {
  const { mLat, mLon } = metersPerDeg(origin.lat);
  return {
    lat: origin.lat + n / mLat,
    lon: origin.lon + e / mLon,
    alt: origin.alt + u,
  };
}

export function llaToEnu(
  origin: { lat: number; lon: number; alt: number },
  lat: number,
  lon: number,
  alt: number,
): { e: number; n: number; u: number } {
  const { mLat, mLon } = metersPerDeg(origin.lat);
  return {
    e: (lon - origin.lon) * mLon,
    n: (lat - origin.lat) * mLat,
    u: alt - origin.alt,
  };
}

export function haversineM(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371000;
  const p1 = deg2rad(lat1);
  const p2 = deg2rad(lat2);
  const dp = deg2rad(lat2 - lat1);
  const dl = deg2rad(lon2 - lon1);
  const a = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(a)));
}

export function headingBetween(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const p1 = deg2rad(lat1);
  const p2 = deg2rad(lat2);
  const dl = deg2rad(lon2 - lon1);
  const y = Math.sin(dl) * Math.cos(p2);
  const x = Math.cos(p1) * Math.sin(p2) - Math.sin(p1) * Math.cos(p2) * Math.cos(dl);
  return wrap360(rad2deg(Math.atan2(y, x)));
}

export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function gauss(rng: () => number): number {
  const u = Math.max(1e-12, rng());
  const v = rng();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}
