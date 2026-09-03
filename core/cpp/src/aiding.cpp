#include "nav/aiding.h"

#include <cmath>

namespace nav {

LightCounterState createLightCounter() { return LightCounterState{}; }

LightCounterState stepLightCount(const LightCounterState& st, double lux,
                                 std::int64_t t_ns, double spacing_m,
                                 double threshold) {
  const bool bright = lux > threshold;
  int count = st.count;
  if (bright && !st.last_bright && spacing_m > 0.0) ++count;
  LightCounterState out;
  out.last_bright = bright;
  out.count = count;
  out.last_t_ns = t_ns;
  out.along_track_m = static_cast<double>(count) * spacing_m;
  return out;
}

double baroDeltaAlt(double hpa, double hpa_ref) { return (hpa_ref - hpa) * 8.435; }

int garageLevel(double delta_alt, double deck_height) {
  if (deck_height <= 0.0) return 0;
  return static_cast<int>(std::lround(delta_alt / deck_height));
}

double acousticSpeed(double rms, double rms_ref, double v_ref, double n) {
  if (rms_ref <= 1e-9) return 0;
  const double r = rms > 0.0 ? rms : 0.0;
  return v_ref * std::pow(r / rms_ref, 1.0 / n);
}

} // namespace nav
