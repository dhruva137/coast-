#pragma once

// Practical right-invariant / multiplicative EKF on R, v, p plus biases.
//
// Full SE₂(3) InEKF (Barrau & Bonnabel; Brossard AI-IMU; Qian AVNet) treats
// (R, v, p) as one Lie group. The 15-state filter below is the same error
// coordinates at first order — nav-frame attitude error, ENU velocity /
// position, gyro and accel bias random walk — with IMU mechanization and
// a GNSS position update. Two-wheeler: yaw is integrated with the lean-
// aware rate ψ̇ = ω_y sin φ + ω_z cos φ, not raw ω_z.
//
// Degrade, never freeze: always output a position and a covariance.

#include "nav/math.h"
#include "nav/types.h"

#include <array>
#include <cstdint>

namespace nav {

constexpr int kEkfDim = 15; // δθ(3) + δv(3) + δp(3) + δbg(3) + δba(3)

class InvariantEKF {
 public:
  Lla origin;
  Mat3 R = mat3Ident();
  Vec3 v{{0, 0, 0}}; // ENU m/s
  Vec3 p{{0, 0, 0}}; // ENU m
  Vec3 bg{{0, 0, 0}};
  Vec3 ba{{0, 0, 0}};
  std::array<double, kEkfDim * kEkfDim> P{};
  double lean = 0;
  bool gnss_aided = true;
  bool two_wheeler = true;
  std::int64_t last_t_ns = -1;

  explicit InvariantEKF(const Lla& origin_lla, bool two_wheeler_in = true);

  void seedFromGnss(const IGnssFix& fix);
  void propagate(const ISensorFrame& f);
  void updateGnss(const IGnssFix& fix);
  void markOutage();
  INavState toState(std::int64_t t_ns) const;

 private:
  void initP();
  void pseudoOdo(double speed, double psi_dot, double dt);
};

} // namespace nav
