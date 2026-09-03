#pragma once

// Frequency-decoupled odometry stand-in [F7].
// Vehicle-motion power lives below 2 Hz; above 10 Hz is vibration.
// A trained ONNX model replaces this physics fallback on-device.

#include "nav/types.h"

#include <vector>

namespace nav {

struct OdoEstimate {
  double speed = 0;
  double speed_var = 4;
  double yaw_rate = 0;
  double accel_fwd = 0;
};

class FrequencyDecoupledOdo {
 public:
  explicit FrequencyDecoupledOdo(double hz = 10);
  OdoEstimate push(const ISensorFrame& f);
  void setSpeed(double v);

 private:
  OdoEstimate infer() const;

  std::vector<ISensorFrame> buf_;
  double hz_ = 10;
  int win_ = 20;
  mutable double speed_ = 0;
};

} // namespace nav
