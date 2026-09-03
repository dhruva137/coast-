#pragma once

// Opportunistic aiding: light-pulse COUNTING (not phase matching) [F11],
// barometer for garage level, acoustic speed proxy.

#include <cstdint>

namespace nav {

struct LightCounterState {
  bool last_bright = false;
  int count = 0;
  std::int64_t last_t_ns = 0;
  double along_track_m = 0;
};

LightCounterState createLightCounter();

// Count rising edges of ambient lux. Phase matching only constrains
// position modulo the lamp spacing (~0% gain). Counting from the portal
// is absolute: 9–21% along-track improvement in simulation.
LightCounterState stepLightCount(const LightCounterState& st, double lux,
                                 std::int64_t t_ns, double spacing_m,
                                 double threshold = 35.0);

/** Standard atmosphere: 1 hPa ≈ 8.43 m near sea level. */
double baroDeltaAlt(double hpa, double hpa_ref);

int garageLevel(double delta_alt, double deck_height = 3.2);

// On-board acoustic speed: tyre/wind noise amplitude ~ v^n.
// `rms` is mic RMS; calibrated at (rms_ref, v_ref).
double acousticSpeed(double rms, double rms_ref, double v_ref, double n = 1.35);

} // namespace nav
