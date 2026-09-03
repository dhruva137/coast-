#include "nav/leansolver.h"

#include "nav/math.h"
#include "nav/types.h"

#include <cmath>

namespace nav {

namespace {
constexpr int kMaxIters = 8;
constexpr double kTol = 1e-9;
} // namespace

double yawRateFromLean(double gy, double gz, double phi) {
  return gy * std::sin(phi) + gz * std::cos(phi);
}

double carStyleYawRate(double gz) { return gz; }

LeanSolution solveLean(const LeanObservation& obs) {
  const double v = obs.speed > 0.0 ? obs.speed : 0.0;
  const double gy = obs.gy;
  const double gz = obs.gz;
  const double gx = obs.gx;

  LeanSolution sol;
  sol.phi_dot = gx;

  if (v < 0.4) {
    sol.phi = 0;
    sol.psi_dot = gz;
    sol.iterations = 0;
    sol.residual = 0;
    sol.coordinated = false;
    return sol;
  }

  double phi = obs.has_phi0 ? obs.phi0 : std::atan2(v * gz, kG);
  phi = clamp(phi, -1.2, 1.2);
  double residual = 1.0;
  int i = 0;
  for (; i < kMaxIters; ++i) {
    const double psi_dot = yawRateFromLean(gy, gz, phi);
    const double next = std::atan2(v * psi_dot, kG);
    residual = std::abs(wrapPi(next - phi));
    phi = next;
    if (residual < kTol) {
      ++i;
      break;
    }
  }
  const double psi_dot = yawRateFromLean(gy, gz, phi);
  sol.phi = phi;
  sol.psi_dot = psi_dot;
  sol.iterations = i;
  sol.residual = residual;
  sol.coordinated = std::abs(v * psi_dot) > 0.15;
  return sol;
}

double headingRateScaleError(double dphi) { return std::cos(dphi); }

double stepHeading(double yaw, double dt, double gy, double gz, double phi,
                   bool lean_aware) {
  const double psi_dot = lean_aware ? yawRateFromLean(gy, gz, phi) : gz;
  return wrapPi(yaw + psi_dot * dt);
}

} // namespace nav
