#pragma once

// Resample, 2nd-order Butterworth, static bias cal, ZUPT / ZIHR.
// Window math is rate-aware: IO-VNBD is 10 Hz; phone IMU is 50–200 Hz.
// AVNet's 200-sample @ 200 Hz window is WRONG on IO-VNBD.

#include "nav/types.h"

#include <array>
#include <vector>

namespace nav {

struct Calib {
  Vec3 ba{{0, 0, 0}};
  Vec3 bg{{0, 0, 0}};
  int samples = 0;
};

struct Butter2 {
  double a1 = 0, a2 = 0;
  double b0 = 0, b1 = 0, b2 = 0;
};

Butter2 butter2Lowpass(double fc, double fs);

class Iir2 {
 public:
  Iir2() = default;
  explicit Iir2(Butter2 c);
  double step(double x);
  void reset();

 private:
  Butter2 c_{};
  double x1_ = 0, x2_ = 0, y1_ = 0, y2_ = 0;
};

class SixAxisFilter {
 public:
  SixAxisFilter(double fc, double fs);
  ISensorFrame apply(const ISensorFrame& f);

 private:
  std::array<Iir2, 6> axes_{};
};

bool isStatic(const ISensorFrame& f, double g = kG);
bool zupt(const ISensorFrame& f);
bool zihr(const ISensorFrame& f);

class BiasCalibrator {
 public:
  void observe(const ISensorFrame& f);
  Calib get() const;
  ISensorFrame apply(const ISensorFrame& f) const;

 private:
  int n_ = 0;
  double sa_[3]{};
  double sg_[3]{};
  bool frozen_ = false;
  Calib frozen_val_{};
};

std::vector<ISensorFrame> resampleLinear(const std::vector<ISensorFrame>& frames,
                                         double hz);

/** Samples in a `seconds`-long window at `hz`. Floor of 4. */
int windowForRate(double hz, double seconds = 2.0);

} // namespace nav
