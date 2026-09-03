#include "nav/inference.h"

#include "nav/math.h"
#include "nav/preprocess.h"

#include <algorithm>
#include <cmath>
#include <cstddef>

namespace nav {

FrequencyDecoupledOdo::FrequencyDecoupledOdo(double hz)
    : hz_(hz), win_(windowForRate(hz, 2.0)) {}

OdoEstimate FrequencyDecoupledOdo::push(const ISensorFrame& f) {
  buf_.push_back(f);
  if (static_cast<int>(buf_.size()) > win_) buf_.erase(buf_.begin());
  return infer();
}

void FrequencyDecoupledOdo::setSpeed(double v) {
  speed_ = v > 0.0 ? v : 0.0;
}

OdoEstimate FrequencyDecoupledOdo::infer() const {
  OdoEstimate o;
  o.speed = speed_;
  if (buf_.size() < 4) {
    o.speed_var = 4;
    return o;
  }

  double low_ax = 0, low_ay = 0, high_e = 0, yaw = 0;
  const int n = static_cast<int>(buf_.size());
  for (int i = 0; i < n; ++i) {
    const ISensorFrame& f = buf_[static_cast<std::size_t>(i)];
    low_ax += f.ax;
    low_ay += f.ay;
    yaw += f.gz;
    if (i > 0) {
      const ISensorFrame& p = buf_[static_cast<std::size_t>(i - 1)];
      const double dax = f.ax - p.ax;
      const double day = f.ay - p.ay;
      const double daz = f.az - p.az;
      high_e += dax * dax + day * day + daz * daz;
    }
  }
  low_ax /= n;
  low_ay /= n;
  yaw /= n;
  (void)low_ay;
  o.accel_fwd = low_ax;
  const double dt = 1.0 / hz_;
  speed_ = speed_ + o.accel_fwd * dt;
  if (speed_ < 0.0) speed_ = 0.0;

  double a_mean = 0;
  for (const auto& f : buf_) a_mean += hypot3(f.ax, f.ay, f.az);
  a_mean /= n;
  if (a_mean < 10.4 && std::abs(yaw) < 0.05) speed_ *= 0.995;

  const double high_rms = std::sqrt(high_e / std::max(1, n - 1));
  o.speed = speed_;
  o.speed_var = 0.4 + 3.2 * high_rms;
  o.yaw_rate = yaw;
  return o;
}

} // namespace nav
