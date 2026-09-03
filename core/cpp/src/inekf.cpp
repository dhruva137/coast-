#include "nav/inekf.h"

#include "nav/leansolver.h"

#include <cmath>
#include <cstddef>

namespace nav {
namespace {

constexpr int N = kEkfDim;

void matIdent(double* A) {
  for (int i = 0; i < N * N; ++i) A[i] = 0;
  for (int i = 0; i < N; ++i) A[i * N + i] = 1;
}

void matMul(const double* A, const double* B, double* C) {
  for (int i = 0; i < N; ++i) {
    for (int j = 0; j < N; ++j) {
      double s = 0;
      for (int k = 0; k < N; ++k) s += A[i * N + k] * B[k * N + j];
      C[i * N + j] = s;
    }
  }
}

void matTranspose(const double* A, double* AT) {
  for (int i = 0; i < N; ++i)
    for (int j = 0; j < N; ++j) AT[i * N + j] = A[j * N + i];
}

bool inv3(const double* m, double* o) {
  const double det = m[0] * (m[4] * m[8] - m[5] * m[7]) -
                     m[1] * (m[3] * m[8] - m[5] * m[6]) +
                     m[2] * (m[3] * m[7] - m[4] * m[6]);
  if (std::abs(det) < 1e-18) return false;
  const double id = 1.0 / det;
  o[0] = (m[4] * m[8] - m[5] * m[7]) * id;
  o[1] = (m[2] * m[7] - m[1] * m[8]) * id;
  o[2] = (m[1] * m[5] - m[2] * m[4]) * id;
  o[3] = (m[5] * m[6] - m[3] * m[8]) * id;
  o[4] = (m[0] * m[8] - m[2] * m[6]) * id;
  o[5] = (m[2] * m[3] - m[0] * m[5]) * id;
  o[6] = (m[3] * m[7] - m[4] * m[6]) * id;
  o[7] = (m[1] * m[6] - m[0] * m[7]) * id;
  o[8] = (m[0] * m[4] - m[1] * m[3]) * id;
  return true;
}

double wrapSmall(double a) {
  while (a > kPi) a -= 2.0 * kPi;
  while (a < -kPi) a += 2.0 * kPi;
  return a;
}

Mat3 composeYawCorrection(const Mat3& dR, double psi_dot, double gz, double dt) {
  const double dpsi = (psi_dot - gz) * dt;
  if (std::abs(dpsi) < 1e-12) return dR;
  return mat3Mul(dR, so3Exp(0, 0, dpsi));
}

} // namespace

InvariantEKF::InvariantEKF(const Lla& origin_lla, bool two_wheeler_in)
    : origin(origin_lla), two_wheeler(two_wheeler_in) {
  R = mat3Ident();
  initP();
}

void InvariantEKF::initP() {
  P.fill(0);
  const double d[N] = {0.02, 0.02, 0.05, 0.5, 0.5, 0.5, 4, 4, 2,
                       1e-4, 1e-4, 1e-4, 0.02, 0.02, 0.02};
  for (int i = 0; i < N; ++i) P[static_cast<std::size_t>(i * N + i)] = d[i];
}

void InvariantEKF::seedFromGnss(const IGnssFix& fix) {
  const Enu enu = llaToEnu(origin, fix.lat, fix.lon, fix.alt);
  p = {{enu.e, enu.n, enu.u}};
  const double yaw = deg2rad(fix.bearing);
  R = rpyToMat(0, 0, yaw);
  v = {{fix.speed * std::sin(yaw), fix.speed * std::cos(yaw), 0}};
  last_t_ns = fix.t_ns;
  gnss_aided = true;
}

void InvariantEKF::markOutage() { gnss_aided = false; }

void InvariantEKF::propagate(const ISensorFrame& f) {
  if (last_t_ns < 0) {
    last_t_ns = f.t_ns;
    return;
  }
  const double dt = static_cast<double>(f.t_ns - last_t_ns) / 1e9;
  last_t_ns = f.t_ns;
  if (dt <= 0.0 || dt > 0.5) return;

  const double gx = f.gx - bg[0];
  const double gy = f.gy - bg[1];
  const double gz = f.gz - bg[2];
  const double ax = f.ax - ba[0];
  const double ay = f.ay - ba[1];
  const double az = f.az - ba[2];

  const double speed = hypot3(v[0], v[1], v[2]);
  LeanObservation obs;
  obs.gy = gy;
  obs.gz = gz;
  obs.gx = gx;
  obs.speed = speed;
  obs.phi0 = lean;
  obs.has_phi0 = true;
  const LeanSolution lean_sol =
      two_wheeler ? solveLean(obs)
                  : LeanSolution{0, gz, gx, 0, 0, false};
  lean = lean_sol.phi;

  const Mat3 dR_body = so3Exp(gx * dt, gy * dt, gz * dt);
  R = mat3Mul(R, two_wheeler ? composeYawCorrection(dR_body, lean_sol.psi_dot, gz, dt)
                             : dR_body);

  Vec3 acc_nav = mat3Vec(R, Vec3{{ax, ay, az}});
  acc_nav[2] -= kG;
  v[0] += acc_nav[0] * dt;
  v[1] += acc_nav[1] * dt;
  v[2] += acc_nav[2] * dt;
  p[0] += v[0] * dt;
  p[1] += v[1] * dt;
  p[2] += v[2] * dt;

  // Discrete error-state Φ = I + F dt. Nav-frame attitude error:
  //   δθ̇ = −R δbg
  //   δv̇ = −[a_nav×] δθ − R δba
  //   δṗ = δv
  // This is the first-order linearisation of the right-invariant error
  // on SE₂(3) with gravity the only fictitious force (Barrau 2017).
  double Phi[N * N];
  matIdent(Phi);
  for (int i = 0; i < 3; ++i) {
    for (int j = 0; j < 3; ++j) {
      Phi[i * N + (9 + j)] = -R[static_cast<std::size_t>(i * 3 + j)] * dt;
      Phi[(3 + i) * N + (12 + j)] = -R[static_cast<std::size_t>(i * 3 + j)] * dt;
    }
  }
  const Mat3 As = skew(acc_nav[0], acc_nav[1], acc_nav[2]);
  for (int i = 0; i < 3; ++i)
    for (int j = 0; j < 3; ++j)
      Phi[(3 + i) * N + j] = -As[static_cast<std::size_t>(i * 3 + j)] * dt;
  for (int i = 0; i < 3; ++i) Phi[(6 + i) * N + (3 + i)] = dt;

  double FP[N * N], PhiT[N * N], FPFt[N * N];
  matMul(Phi, P.data(), FP);
  matTranspose(Phi, PhiT);
  matMul(FP, PhiT, FPFt);
  for (int i = 0; i < N * N; ++i) P[static_cast<std::size_t>(i)] = FPFt[i];

  const double qg = (gnss_aided ? 2e-5 : 8e-5) * dt;
  const double qa = (gnss_aided ? 4e-3 : 1.5e-2) * dt;
  const double qbg = 1e-8 * dt;
  const double qba = 1e-6 * dt;
  const double q[N] = {qg,
                       qg,
                       qg * (two_wheeler ? 0.4 : 1.2),
                       qa,
                       qa,
                       qa,
                       qa * dt,
                       qa * dt,
                       qa * dt,
                       qbg,
                       qbg,
                       qbg,
                       qba,
                       qba,
                       qba};
  for (int i = 0; i < N; ++i) P[static_cast<std::size_t>(i * N + i)] += q[i];

  pseudoOdo(speed, lean_sol.psi_dot, dt);
}

void InvariantEKF::pseudoOdo(double speed, double psi_dot, double dt) {
  double roll = 0, pitch = 0, yaw = 0;
  matToRpy(R, roll, pitch, yaw);
  const Vec3 v_hat{{speed * std::sin(yaw), speed * std::cos(yaw), 0}};
  const double r_vel = gnss_aided ? 1.2 : 2.8;
  const double k = dt / (dt + 0.35);
  v[0] += k * (v_hat[0] - v[0]) / r_vel;
  v[1] += k * (v_hat[1] - v[1]) / r_vel;
  v[2] *= (1.0 - 0.4 * k);

  if (two_wheeler) {
    const double yaw_inn = wrapSmall(psi_dot * dt);
    const double ky = gnss_aided ? 0.15 : 0.55;
    R = mat3Mul(so3Exp(0, 0, ky * yaw_inn), R);
  }
}

void InvariantEKF::updateGnss(const IGnssFix& fix) {
  const Enu enu = llaToEnu(origin, fix.lat, fix.lon, fix.alt);
  const double inn[3] = {enu.e - p[0], enu.n - p[1], enu.u - p[2]};
  const double r = fix.acc_h > 2.0 ? fix.acc_h : 2.0;

  // z = p, H = [0 0 I 0 0]. S = H P Hᵀ + R = P_pp + σ² I.
  double S[9];
  for (int i = 0; i < 3; ++i)
    for (int j = 0; j < 3; ++j)
      S[i * 3 + j] = P[static_cast<std::size_t>((6 + i) * N + (6 + j))] +
                     (i == j ? r * r : 0.0);

  double Sinv[9];
  if (!inv3(S, Sinv)) {
    // Scalar fallback if S is singular (should not happen).
    const double k = 1.0 / (1.0 + r * r / 25.0);
    p[0] += k * inn[0];
    p[1] += k * inn[1];
    p[2] += k * inn[2];
    gnss_aided = true;
    return;
  }

  // K = P Hᵀ S⁻¹. Hᵀ picks columns 6..8 of P.
  double K[N * 3];
  for (int i = 0; i < N; ++i) {
    for (int j = 0; j < 3; ++j) {
      double s = 0;
      for (int c = 0; c < 3; ++c)
        s += P[static_cast<std::size_t>(i * N + (6 + c))] * Sinv[c * 3 + j];
      K[i * 3 + j] = s;
    }
  }

  double dx[N]{};
  for (int i = 0; i < N; ++i)
    dx[i] = K[i * 3 + 0] * inn[0] + K[i * 3 + 1] * inn[1] + K[i * 3 + 2] * inn[2];

  R = mat3Mul(so3Exp(dx[0], dx[1], dx[2]), R);
  v[0] += dx[3];
  v[1] += dx[4];
  v[2] += dx[5];
  p[0] += dx[6];
  p[1] += dx[7];
  p[2] += dx[8];
  bg[0] += dx[9];
  bg[1] += dx[10];
  bg[2] += dx[11];
  ba[0] += dx[12];
  ba[1] += dx[13];
  ba[2] += dx[14];

  // P ← (I − K H) P
  std::array<double, N * N> Pnew{};
  for (int i = 0; i < N; ++i) {
    for (int j = 0; j < N; ++j) {
      double khp = 0;
      for (int c = 0; c < 3; ++c)
        khp += K[i * 3 + c] * P[static_cast<std::size_t>((6 + c) * N + j)];
      Pnew[static_cast<std::size_t>(i * N + j)] =
          P[static_cast<std::size_t>(i * N + j)] - khp;
    }
  }
  P = Pnew;

  if (fix.speed > 1.0) {
    const double yaw = deg2rad(fix.bearing);
    double roll = 0, pitch = 0, yaw_hat = 0;
    matToRpy(R, roll, pitch, yaw_hat);
    const Mat3 Rz = so3Exp(0, 0, 0.35 * wrapSmall(yaw - yaw_hat));
    R = mat3Mul(Rz, R);
    v = {{fix.speed * std::sin(yaw), fix.speed * std::cos(yaw), v[2] * 0.5}};
  }
  gnss_aided = true;
}

INavState InvariantEKF::toState(std::int64_t t_ns) const {
  const Lla lla = enuToLla(origin, p[0], p[1], p[2]);
  double roll = 0, pitch = 0, yaw = 0;
  matToRpy(R, roll, pitch, yaw);
  const double speed = std::hypot(v[0], v[1]);
  const double pe = std::sqrt(std::max(0.25, P[static_cast<std::size_t>(6 * N + 6)]));
  const double pn = std::sqrt(std::max(0.25, P[static_cast<std::size_t>(7 * N + 7)]));
  const double pu = std::sqrt(std::max(0.25, P[static_cast<std::size_t>(8 * N + 8)]));

  INavState s;
  s.t_ns = t_ns;
  s.lat = lla.lat;
  s.lon = lla.lon;
  s.alt = lla.alt;
  s.ve = v[0];
  s.vn = v[1];
  s.vu = v[2];
  s.roll = roll;
  s.pitch = pitch;
  s.yaw = yaw;
  s.lean = lean;
  s.speed = speed;
  s.P_pos = {{pe * pe, 0, 0, 0, pn * pn, 0, 0, 0, pu * pu}};
  s.gnss_aided = gnss_aided;
  s.mode = gnss_aided ? "gnss" : "ins";
  return s;
}

} // namespace nav
