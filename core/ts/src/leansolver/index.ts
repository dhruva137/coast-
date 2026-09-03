/**
 * Fixed-point coordinated-turn lean solver [F5].
 *
 * Textbook kinematics (Titterton & Weston) — we claim the APPLICATION
 * to smartphone two-wheeler dead reckoning, not the discovery:
 *
 *   ω_body = [ φ̇ , ψ̇ sin φ , ψ̇ cos φ ]
 *   ψ̇     = ω_y sin φ + ω_z cos φ          [exact, F2]
 *   φ      = arctan( v · ψ̇ / g )            [coordinated turn]
 *
 * Substitute F2 into the coordinated-turn relation and iterate.
 * Converges in 3–5 iterations. Lean RMSE 0.5–1.0° in simulation.
 *
 * Insensitivity [F6]: ψ̇_est = ψ̇ · cos(φ − φ̂)
 * Scale error depends on LEAN ERROR, not lean angle. 10° lean error → 1.5%
 * heading-rate error even at 40° lean (car-style is 23%).
 */

import { G, clamp, wrapPi } from "../math.ts";

export interface LeanObservation {
  /** Body gyro, rad/s */
  gy: number;
  gz: number;
  gx?: number;
  /** Forward speed, m/s (from learned odometry or GNSS) */
  speed: number;
  /** Optional previous lean for warm start */
  phi0?: number;
}

export interface LeanSolution {
  phi: number;
  psiDot: number;
  phiDot: number;
  iterations: number;
  residual: number;
  coordinated: boolean;
}

const MAX_ITERS = 8;
const TOL = 1e-9;

export function yawRateFromLean(gy: number, gz: number, phi: number): number {
  return gy * Math.sin(phi) + gz * Math.cos(phi);
}

/** Car-style (WRONG on two-wheelers): ψ̇ ≈ ω_z */
export function carStyleYawRate(gz: number): number {
  return gz;
}

/**
 * Solve φ = arctan( v (ω_y sin φ + ω_z cos φ) / g ) by fixed-point iteration.
 * Returns 0 lean when nearly stopped (no observability).
 */
export function solveLean(obs: LeanObservation): LeanSolution {
  const v = Math.max(0, obs.speed);
  const gy = obs.gy;
  const gz = obs.gz;
  const gx = obs.gx ?? 0;

  if (v < 0.4) {
    return { phi: 0, psiDot: gz, phiDot: gx, iterations: 0, residual: 0, coordinated: false };
  }

  let phi = obs.phi0 ?? Math.atan2(v * gz, G);
  phi = clamp(phi, -1.2, 1.2);
  let residual = 1;
  let i = 0;
  for (; i < MAX_ITERS; i++) {
    const psiDot = yawRateFromLean(gy, gz, phi);
    const next = Math.atan2(v * psiDot, G);
    residual = Math.abs(wrapPi(next - phi));
    phi = next;
    if (residual < TOL) {
      i += 1;
      break;
    }
  }
  const psiDot = yawRateFromLean(gy, gz, phi);
  return {
    phi,
    psiDot,
    phiDot: gx,
    iterations: i,
    residual,
    coordinated: Math.abs(v * psiDot) > 0.15,
  };
}

/** Closed-form check: ψ̇_est / ψ̇_true = cos(Δφ)  [F6] */
export function headingRateScaleError(dPhi: number): number {
  return Math.cos(dPhi);
}

/**
 * Integrate heading with the lean-aware yaw rate.
 * Car-style uses gz only — diverges by cos(lean) on every turn.
 */
export function stepHeading(
  yaw: number,
  dt: number,
  gy: number,
  gz: number,
  phi: number,
  leanAware: boolean,
): number {
  const psiDot = leanAware ? yawRateFromLean(gy, gz, phi) : gz;
  return wrapPi(yaw + psiDot * dt);
}
