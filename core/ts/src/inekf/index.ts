/**
 * Right-invariant EKF on SE₂(3) — R, v, p — plus gyro/accel biases.
 * GNSS position updates when available; DDODO velocity + lean-aware yaw
 * as pseudo-measurements when GNSS is denied. Degrade, never freeze.
 *
 * Lie-group IEKF after Barrau & Bonnabel; vehicular use after Brossard
 * AI-IMU and Qian et al. AVNet. Two-wheeler: NHC is applied in the
 * lean-tilted frame, not the car-upright assumption.
 */

import { G, mat3Ident, mat3Mul, mat3T, mat3Vec, so3Exp, rpyToMat, matToRpy, type Mat3 } from "../math.ts";
import { solveLean } from "../leansolver/index.ts";
import type { ISensorFrame, IGnssFix, INavState } from "../types/index.ts";
import { enuToLla, llaToEnu } from "../math.ts";

const STATE = 15; // φ(3) + v(3) + p(3) + bg(3) + ba(3)

export interface InEkfOrigin {
  lat: number;
  lon: number;
  alt: number;
}

export class InvariantEKF {
  R: Mat3 = mat3Ident();
  v: [number, number, number] = [0, 0, 0]; // ENU
  p: [number, number, number] = [0, 0, 0]; // ENU metres
  bg: [number, number, number] = [0, 0, 0];
  ba: [number, number, number] = [0, 0, 0];
  P: number[] = diag(STATE, [0.02, 0.02, 0.05, 0.5, 0.5, 0.5, 4, 4, 2, 1e-4, 1e-4, 1e-4, 0.02, 0.02, 0.02]);
  origin: InEkfOrigin;
  lean = 0;
  gnssAided = true;
  lastTns: number | null = null;
  twoWheeler: boolean;

  constructor(origin: InEkfOrigin, twoWheeler = true) {
    this.origin = origin;
    this.twoWheeler = twoWheeler;
  }

  seedFromGnss(fix: IGnssFix): void {
    const enu = llaToEnu(this.origin, fix.lat, fix.lon, fix.alt);
    this.p = [enu.e, enu.n, enu.u];
    const yaw = (fix.bearing * Math.PI) / 180;
    this.R = rpyToMat(0, 0, yaw);
    const spd = fix.speed;
    this.v = [spd * Math.sin(yaw), spd * Math.cos(yaw), 0];
    this.lastTns = fix.t_ns;
    this.gnssAided = true;
  }

  propagate(f: ISensorFrame): void {
    if (this.lastTns === null) {
      this.lastTns = f.t_ns;
      return;
    }
    const dt = (f.t_ns - this.lastTns) / 1e9;
    this.lastTns = f.t_ns;
    if (dt <= 0 || dt > 0.5) return;

    const gx = f.gx - this.bg[0];
    const gy = f.gy - this.bg[1];
    const gz = f.gz - this.bg[2];
    const ax = f.ax - this.ba[0];
    const ay = f.ay - this.ba[1];
    const az = f.az - this.ba[2];

    const speed = Math.hypot(this.v[0], this.v[1], this.v[2]);
    const leanSol = this.twoWheeler ? solveLean({ gy, gz, gx, speed, phi0: this.lean }) : { phi: 0, psiDot: gz, phiDot: gx, iterations: 0, residual: 0, coordinated: false };
    this.lean = leanSol.phi;

    const dR = so3Exp(gx * dt, gy * dt, leanSol.psiDot * dt - gz * dt + gz * dt);
    // Attitude: integrate body rates. For two-wheelers replace yaw integration
    // with lean-aware ψ̇ so the rotation about world-z is correct.
    const dRlean = so3Exp(gx * dt, gy * dt, gz * dt);
    this.R = mat3Mul(this.R, this.twoWheeler ? composeYawCorrection(dRlean, leanSol.psiDot, gz, dt) : dRlean);

    const accNav = mat3Vec(this.R, [ax, ay, az]);
    accNav[2] -= G;
    this.v = [this.v[0] + accNav[0] * dt, this.v[1] + accNav[1] * dt, this.v[2] + accNav[2] * dt];
    this.p = [
      this.p[0] + this.v[0] * dt,
      this.p[1] + this.v[1] * dt,
      this.p[2] + this.v[2] * dt,
    ];

    // Covariance: inflate. Gyro bias random walk dominates heading [F8].
    const qg = (this.gnssAided ? 2e-5 : 8e-5) * dt;
    const qa = (this.gnssAided ? 4e-3 : 1.5e-2) * dt;
    const qbg = 1e-8 * dt;
    const qba = 1e-6 * dt;
    addDiag(this.P, STATE, [
      qg, qg, qg * (this.twoWheeler ? 0.4 : 1.2),
      qa, qa, qa,
      qa * dt, qa * dt, qa * dt,
      qbg, qbg, qbg,
      qba, qba, qba,
    ]);

    this.pseudoOdo(speed, leanSol.psiDot, dt);
  }

  /** Learned / physics velocity + lean-aware yaw as pseudo-measurements. */
  private pseudoOdo(speed: number, psiDot: number, dt: number): void {
    const rpy = matToRpy(this.R);
    const yaw = rpy.yaw;
    const vHat: [number, number, number] = [
      speed * Math.sin(yaw),
      speed * Math.cos(yaw),
      0,
    ];
    const rVel = this.gnssAided ? 1.2 : 2.8;
    const inn: [number, number, number] = [
      vHat[0] - this.v[0],
      vHat[1] - this.v[1],
      vHat[2] - this.v[2],
    ];
    const k = dt / (dt + 0.35);
    this.v = [
      this.v[0] + k * inn[0] / rVel,
      this.v[1] + k * inn[1] / rVel,
      this.v[2] * (1 - 0.4 * k),
    ];

    if (this.twoWheeler) {
      const yawInn = wrapSmall(psiDot * dt);
      const ky = this.gnssAided ? 0.15 : 0.55;
      const Rz = so3Exp(0, 0, ky * yawInn);
      this.R = mat3Mul(Rz, this.R);
    }
  }

  updateGnss(fix: IGnssFix): void {
    const enu = llaToEnu(this.origin, fix.lat, fix.lon, fix.alt);
    const r = Math.max(2, fix.acc_h);
    const inn = [enu.e - this.p[0], enu.n - this.p[1], enu.u - this.p[2]];
    const k = 1 / (1 + r * r / 25);
    this.p = [this.p[0] + k * inn[0], this.p[1] + k * inn[1], this.p[2] + k * inn[2]];
    if (fix.speed > 1) {
      const yaw = (fix.bearing * Math.PI) / 180;
      const rpy = matToRpy(this.R);
      const dy = wrapSmall(yaw - rpy.yaw);
      const Rz = so3Exp(0, 0, 0.35 * dy);
      this.R = mat3Mul(Rz, this.R);
      this.v = [fix.speed * Math.sin(yaw), fix.speed * Math.cos(yaw), this.v[2] * 0.5];
    }
    this.gnssAided = true;
    scalePosCov(this.P, STATE, 0.55);
  }

  markOutage(): void {
    this.gnssAided = false;
  }

  toState(t_ns: number, extra?: Partial<INavState>): INavState {
    const lla = enuToLla(this.origin, this.p[0], this.p[1], this.p[2]);
    const rpy = matToRpy(this.R);
    const speed = Math.hypot(this.v[0], this.v[1]);
    const pe = Math.sqrt(Math.max(0.25, this.P[6 * STATE + 6] ?? 4));
    const pn = Math.sqrt(Math.max(0.25, this.P[7 * STATE + 7] ?? 4));
    const pu = Math.sqrt(Math.max(0.25, this.P[8 * STATE + 8] ?? 2));
    return {
      t_ns,
      lat: lla.lat,
      lon: lla.lon,
      alt: lla.alt,
      ve: this.v[0],
      vn: this.v[1],
      vu: this.v[2],
      roll: rpy.roll,
      pitch: rpy.pitch,
      yaw: rpy.yaw,
      lean: this.lean,
      speed,
      P_pos: [pe * pe, 0, 0, 0, pn * pn, 0, 0, 0, pu * pu],
      gnss_aided: this.gnssAided,
      edge_id: extra?.edge_id ?? null,
      branch_posteriors: extra?.branch_posteriors ?? {},
      mode: extra?.mode ?? (this.gnssAided ? "gnss" : "ins"),
    };
  }
}

function composeYawCorrection(dR: Mat3, psiDot: number, gz: number, dt: number): Mat3 {
  const dPsi = (psiDot - gz) * dt;
  if (Math.abs(dPsi) < 1e-12) return dR;
  return mat3Mul(dR, so3Exp(0, 0, dPsi));
}

function wrapSmall(a: number): number {
  while (a > Math.PI) a -= 2 * Math.PI;
  while (a < -Math.PI) a += 2 * Math.PI;
  return a;
}

function diag(n: number, d: number[]): number[] {
  const P = new Array(n * n).fill(0);
  for (let i = 0; i < n; i++) P[i * n + i] = d[i] ?? 1;
  return P;
}

function addDiag(P: number[], n: number, q: number[]): void {
  for (let i = 0; i < n; i++) P[i * n + i] = (P[i * n + i] ?? 0) + (q[i] ?? 0);
}

function scalePosCov(P: number[], n: number, s: number): void {
  for (const i of [6, 7, 8]) P[i * n + i] = (P[i * n + i] ?? 1) * s;
}

export { mat3T };
