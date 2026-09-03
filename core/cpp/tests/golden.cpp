// Golden-vector tests for the C++17 navigation core.
// No external test framework — return 0 on success.

#include "nav/engine.h"
#include "nav/inekf.h"
#include "nav/leansolver.h"
#include "nav/math.h"
#include "nav/metrics.h"
#include "nav/types.h"

#include <cmath>
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

namespace {

int g_fails = 0;

void check(bool cond, const char* msg) {
  if (!cond) {
    std::cerr << "FAIL: " << msg << "\n";
    ++g_fails;
  } else {
    std::cout << "ok   " << msg << "\n";
  }
}

void test_lean_solver() {
  const double v = 12.0;
  const double phi_true = 25.0 * nav::kDeg;
  const double psi_dot = (nav::kG * std::tan(phi_true)) / v;
  const double gy = psi_dot * std::sin(phi_true);
  const double gz = psi_dot * std::cos(phi_true);

  nav::LeanObservation obs;
  obs.gy = gy;
  obs.gz = gz;
  obs.speed = v;
  obs.phi0 = 0;
  obs.has_phi0 = true;

  const nav::LeanSolution sol = nav::solveLean(obs);
  check(sol.residual < 1e-6, "F5 coordinated-turn residual < 1e-6");
  check(std::abs(sol.phi - phi_true) < 1e-6, "F5 recovered lean within 1e-6 rad");
  check(sol.iterations <= 8, "F5 converged within 8 iterations");
  check(std::abs(nav::yawRateFromLean(gy, gz, phi_true) - psi_dot) < 1e-12,
        "F2 yawRateFromLean recovers psi_dot");
  check(nav::carStyleYawRate(gz) == gz, "car-style yaw is raw gz");
}

void test_f6_identity() {
  const double dphi = 10.0 * nav::kDeg;
  const double s = nav::headingRateScaleError(dphi);
  check(std::abs(s - std::cos(dphi)) < 1e-15, "F6 headingRateScaleError == cos(dphi)");

  // Kinematic identity: psi_est / psi_true = cos(phi - phi_hat)
  const double phi = 40.0 * nav::kDeg;
  const double phi_hat = phi - dphi;
  const double psi = 0.7;
  const double gy = psi * std::sin(phi);
  const double gz = psi * std::cos(phi);
  const double psi_est = nav::yawRateFromLean(gy, gz, phi_hat);
  check(std::abs(psi_est / psi - std::cos(dphi)) < 1e-12,
        "F6 kinematic identity psi_est = psi * cos(dphi)");

  const double car = std::cos(40.0 * nav::kDeg);
  check(std::abs(1.0 - s) < 0.02, "F6 10 deg lean error is ~1.5% heading-rate error");
  check(1.0 - car > 0.22, "car-style at 40 deg lean is >22% error");
}

void test_tiny_imu() {
  const nav::Lla origin{12.9912, 77.5523, 920.0};
  nav::InvariantEKF ekf(origin, true);

  nav::IGnssFix fix;
  fix.t_ns = 0;
  fix.lat = origin.lat;
  fix.lon = origin.lon;
  fix.alt = origin.alt;
  fix.speed = 8.0;
  fix.bearing = 90.0;
  fix.acc_h = 3.0;
  fix.n_sats = 8;
  ekf.seedFromGnss(fix);

  const double v = 8.0;
  const double phi = 20.0 * nav::kDeg;
  const double psi_dot = (nav::kG * std::tan(phi)) / v;
  const std::int64_t dt_ns = 20000000; // 50 Hz

  std::vector<nav::ISensorFrame> imu;
  imu.reserve(40);
  for (int i = 0; i < 40; ++i) {
    nav::ISensorFrame f;
    f.t_ns = static_cast<std::int64_t>(i) * dt_ns;
    f.ax = 0.05;
    f.ay = 0.0;
    f.az = nav::kG / std::cos(phi);
    f.gx = 0.0;
    f.gy = psi_dot * std::sin(phi);
    f.gz = psi_dot * std::cos(phi);
    f.pressure_hpa = 1013.25;
    f.lux = 80.0;
    imu.push_back(f);
    ekf.propagate(f);
  }

  const nav::INavState st = ekf.toState(imu.back().t_ns);
  check(std::isfinite(st.lat) && std::isfinite(st.lon), "InEKF tiny IMU: finite lat/lon");
  check(std::isfinite(st.alt) && std::isfinite(st.speed), "InEKF tiny IMU: finite alt/speed");
  check(std::abs(st.lat) <= 90.0 && std::abs(st.lon) <= 180.0, "InEKF lat/lon in range");

  nav::ILogMeta meta;
  meta.phone_model = "golden";
  meta.mount_type = "handlebar";
  meta.vehicle = "scooter";
  meta.leans = true;
  meta.imu_hz = 50;
  meta.loop_closure = origin;

  nav::RunOpts opts;
  opts.two_wheeler = true;
  opts.target_hz = 50;
  const nav::EngineResult r = nav::runEngine(imu, std::vector<nav::IGnssFix>{fix}, meta, opts);
  check(!r.ours.empty(), "engine produced a trajectory");
  bool finite = true;
  for (const auto& s : r.ours) {
    if (!std::isfinite(s.lat) || !std::isfinite(s.lon)) finite = false;
  }
  check(finite, "engine tiny IMU: all lat/lon finite");
  check(nav::driftPct(10.0, 1000.0) == 1.0, "drift% = error / distance");
}

} // namespace

int main() {
  test_lean_solver();
  test_f6_identity();
  test_tiny_imu();
  if (g_fails) {
    std::cerr << g_fails << " golden check(s) failed\n";
    return 1;
  }
  std::cout << "nav_golden: all checks passed\n";
  return 0;
}
