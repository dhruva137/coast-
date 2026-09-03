#include "nav/preprocess.h"

#include "nav/math.h"

#include <algorithm>
#include <cmath>
#include <cstddef>

namespace nav {

Butter2 butter2Lowpass(double fc, double fs) {
  const double k = std::tan((kPi * fc) / fs);
  const double k2 = k * k;
  const double n = 1.0 + std::sqrt(2.0) * k + k2;
  Butter2 c;
  c.b0 = k2 / n;
  c.b1 = 2.0 * c.b0;
  c.b2 = c.b0;
  c.a1 = (2.0 * (k2 - 1.0)) / n;
  c.a2 = (1.0 - std::sqrt(2.0) * k + k2) / n;
  return c;
}

Iir2::Iir2(Butter2 c) : c_(c) {}

double Iir2::step(double x) {
  const double y = c_.b0 * x + c_.b1 * x1_ + c_.b2 * x2_ - c_.a1 * y1_ - c_.a2 * y2_;
  x2_ = x1_;
  x1_ = x;
  y2_ = y1_;
  y1_ = y;
  return y;
}

void Iir2::reset() { x1_ = x2_ = y1_ = y2_ = 0; }

SixAxisFilter::SixAxisFilter(double fc, double fs) {
  const Butter2 c = butter2Lowpass(fc, fs);
  for (auto& ax : axes_) ax = Iir2(c);
}

ISensorFrame SixAxisFilter::apply(const ISensorFrame& f) {
  ISensorFrame o = f;
  o.ax = axes_[0].step(f.ax);
  o.ay = axes_[1].step(f.ay);
  o.az = axes_[2].step(f.az);
  o.gx = axes_[3].step(f.gx);
  o.gy = axes_[4].step(f.gy);
  o.gz = axes_[5].step(f.gz);
  return o;
}

bool isStatic(const ISensorFrame& f, double g) {
  const double w = hypot3(f.gx, f.gy, f.gz);
  const double a = hypot3(f.ax, f.ay, f.az);
  return w < 0.04 && std::abs(a - g) < 0.35;
}

bool zupt(const ISensorFrame& f) { return isStatic(f); }

bool zihr(const ISensorFrame& f) {
  return hypot3(f.gx, f.gy, f.gz) < 0.03 &&
         hypot3(f.ax, f.ay, f.az - kG) < 0.4;
}

void BiasCalibrator::observe(const ISensorFrame& f) {
  if (frozen_ || !isStatic(f)) return;
  ++n_;
  sa_[0] += f.ax;
  sa_[1] += f.ay;
  sa_[2] += f.az - kG;
  sg_[0] += f.gx;
  sg_[1] += f.gy;
  sg_[2] += f.gz;
  if (n_ >= 40) {
    frozen_ = true;
    frozen_val_.ba = {{sa_[0] / n_, sa_[1] / n_, sa_[2] / n_}};
    frozen_val_.bg = {{sg_[0] / n_, sg_[1] / n_, sg_[2] / n_}};
    frozen_val_.samples = n_;
  }
}

Calib BiasCalibrator::get() const {
  if (frozen_) return frozen_val_;
  Calib c;
  c.samples = n_;
  return c;
}

ISensorFrame BiasCalibrator::apply(const ISensorFrame& f) const {
  const Calib c = get();
  ISensorFrame o = f;
  o.ax = f.ax - c.ba[0];
  o.ay = f.ay - c.ba[1];
  o.az = f.az - c.ba[2];
  o.gx = f.gx - c.bg[0];
  o.gy = f.gy - c.bg[1];
  o.gz = f.gz - c.bg[2];
  return o;
}

std::vector<ISensorFrame> resampleLinear(const std::vector<ISensorFrame>& frames,
                                         double hz) {
  if (frames.size() < 2 || hz <= 0.0) return frames;
  const double t0 = static_cast<double>(frames.front().t_ns);
  const double t1 = static_cast<double>(frames.back().t_ns);
  const double dt = 1e9 / hz;
  std::vector<ISensorFrame> out;
  out.reserve(static_cast<std::size_t>((t1 - t0) / dt) + 2);
  std::size_t j = 0;
  for (double t = t0; t <= t1 + 0.5; t += dt) {
    while (j + 1 < frames.size() && static_cast<double>(frames[j + 1].t_ns) < t) {
      ++j;
    }
    const ISensorFrame& a = frames[j];
    const ISensorFrame& b = frames[j + 1 < frames.size() ? j + 1 : frames.size() - 1];
    const double span = std::max(1.0, static_cast<double>(b.t_ns - a.t_ns));
    const double u = (t - static_cast<double>(a.t_ns)) / span;
    auto lerp = [u](double x, double y) { return x + (y - x) * u; };
    ISensorFrame o;
    o.t_ns = static_cast<std::int64_t>(t);
    o.ax = lerp(a.ax, b.ax);
    o.ay = lerp(a.ay, b.ay);
    o.az = lerp(a.az, b.az);
    o.gx = lerp(a.gx, b.gx);
    o.gy = lerp(a.gy, b.gy);
    o.gz = lerp(a.gz, b.gz);
    o.mx = lerp(a.mx, b.mx);
    o.my = lerp(a.my, b.my);
    o.mz = lerp(a.mz, b.mz);
    o.pressure_hpa = lerp(a.pressure_hpa, b.pressure_hpa);
    o.lux = lerp(a.lux, b.lux);
    out.push_back(o);
  }
  return out;
}

int windowForRate(double hz, double seconds) {
  const int w = static_cast<int>(std::round(hz * seconds));
  return w < 4 ? 4 : w;
}

} // namespace nav
