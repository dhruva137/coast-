#pragma once

// Fixed-point coordinated-turn lean solver [F5].
//
// Textbook kinematics (Titterton & Weston) — we claim the APPLICATION
// to smartphone two-wheeler dead reckoning, not the discovery:
//
//   ω_body = [ φ̇ , ψ̇ sin φ , ψ̇ cos φ ]
//   ψ̇     = ω_y sin φ + ω_z cos φ          [exact, F2]
//   φ      = atan2( v · ψ̇ , g )             [coordinated turn]
//
// Substitute F2 into the coordinated-turn law and iterate:
//   φ = atan2( v (ω_y sin φ + ω_z cos φ), g )
// Converges in 3–5 iterations. Lean RMSE 0.5–1.0° in simulation.
//
// Insensitivity [F6]: ψ̇_est = ψ̇ · cos(φ − φ̂)
// Scale error depends on LEAN ERROR, not lean angle.

namespace nav {

struct LeanObservation {
  double gy = 0;     // body gyro, rad/s
  double gz = 0;
  double gx = 0;
  double speed = 0;  // forward speed, m/s
  double phi0 = 0;   // warm start, rad
  bool has_phi0 = false;
};

struct LeanSolution {
  double phi = 0;
  double psi_dot = 0;
  double phi_dot = 0;
  int iterations = 0;
  double residual = 0;
  bool coordinated = false;
};

double yawRateFromLean(double gy, double gz, double phi);

/** Car-style (WRONG on two-wheelers): ψ̇ ≈ ω_z */
double carStyleYawRate(double gz);

LeanSolution solveLean(const LeanObservation& obs);

/** Closed-form [F6]: ψ̇_est / ψ̇_true = cos(Δφ) */
double headingRateScaleError(double dphi);

double stepHeading(double yaw, double dt, double gy, double gz, double phi,
                   bool lean_aware);

} // namespace nav
