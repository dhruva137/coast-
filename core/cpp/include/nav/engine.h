#pragma once

// Replay engine: preprocess → odo → lean → InEKF → graph PF.
// Also runs a car-style baseline (ψ̇ = ω_z) on the same log for Act 2.

#include "nav/types.h"

#include <vector>

namespace nav {

struct EngineResult {
  std::vector<INavState> ours;
  std::vector<INavState> baseline;
  ILogMeta meta;
};

struct RunOpts {
  bool two_wheeler = true;
  bool has_graph = false;
  IRoadGraph graph;
  double target_hz = 50;
};

EngineResult runEngine(const std::vector<ISensorFrame>& imu,
                       const std::vector<IGnssFix>& gnss, const ILogMeta& meta,
                       const RunOpts& opts = {});

} // namespace nav
