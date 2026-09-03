#include "nav/metrics.h"

#include "nav/math.h"

#include <algorithm>
#include <cmath>
#include <cstddef>

namespace nav {

std::vector<Lla> statesToLla(const std::vector<INavState>& states) {
  std::vector<Lla> out;
  out.reserve(states.size());
  for (const auto& s : states) out.push_back({s.lat, s.lon, s.alt});
  return out;
}

double pathLength(const std::vector<Lla>& states) {
  double d = 0;
  for (std::size_t i = 1; i < states.size(); ++i) {
    d += haversineM(states[i - 1].lat, states[i - 1].lon, states[i].lat, states[i].lon);
  }
  return d;
}

double loopClosureError(const std::vector<Lla>& states, const Lla& marker) {
  if (states.empty()) return 1e300;
  const Lla& last = states.back();
  return haversineM(last.lat, last.lon, marker.lat, marker.lon);
}

double driftPct(double error_m, double distance_m) {
  if (distance_m < 1.0) return 0;
  return (100.0 * error_m) / distance_m;
}

double ate(const std::vector<Lla>& est, const std::vector<Lla>& gt) {
  const std::size_t n = est.size() < gt.size() ? est.size() : gt.size();
  if (n == 0) return 0;
  double s = 0;
  for (std::size_t i = 0; i < n; ++i)
    s += haversineM(est[i].lat, est[i].lon, gt[i].lat, gt[i].lon);
  return s / static_cast<double>(n);
}

double rte(const std::vector<Lla>& est, const std::vector<Lla>& gt, int window) {
  const int n = static_cast<int>(est.size() < gt.size() ? est.size() : gt.size());
  if (n < window + 1) return ate(est, gt);
  double s = 0;
  int c = 0;
  const int step = std::max(1, window / 4);
  for (int i = 0; i + window < n; i += step) {
    const int j = i + window;
    s += haversineM(est[static_cast<std::size_t>(j)].lat, est[static_cast<std::size_t>(j)].lon,
                    gt[static_cast<std::size_t>(j)].lat, gt[static_cast<std::size_t>(j)].lon);
    ++c;
  }
  return c ? s / c : 0;
}

double branchAccuracy(const std::vector<std::string>& predicted,
                      const std::vector<std::string>& truth) {
  const std::size_t n = predicted.size() < truth.size() ? predicted.size() : truth.size();
  if (n == 0) return 0;
  std::size_t ok = 0;
  for (std::size_t i = 0; i < n; ++i)
    if (predicted[i] == truth[i]) ++ok;
  return static_cast<double>(ok) / static_cast<double>(n);
}

double leanRmseDeg(const std::vector<double>& est, const std::vector<double>& gt) {
  const std::size_t n = est.size() < gt.size() ? est.size() : gt.size();
  if (n == 0) return 0;
  double s = 0;
  for (std::size_t i = 0; i < n; ++i) {
    const double d = (est[i] - gt[i]) * kRad;
    s += d * d;
  }
  return std::sqrt(s / static_cast<double>(n));
}

IMetrics summarize(const std::vector<INavState>& est, const std::vector<Lla>& gt,
                   const Lla& marker, const std::vector<std::string>* pred_edges,
                   const std::vector<std::string>* truth_edges,
                   const std::vector<double>* lean_est, const std::vector<double>* lean_gt,
                   double latency_ms) {
  const std::vector<Lla> est_ll = statesToLla(est);
  const double dist = pathLength(gt.empty() ? est_ll : gt);
  const double lc = loopClosureError(est_ll, marker);
  IMetrics m;
  m.loop_closure_m = lc;
  m.distance_m = dist;
  m.drift_pct = driftPct(lc, dist);
  m.ate_m = ate(est_ll, gt);
  m.rte_m = rte(est_ll, gt);
  m.branch_accuracy = (pred_edges && truth_edges) ? branchAccuracy(*pred_edges, *truth_edges) : 0;
  m.lean_rmse_deg = (lean_est && lean_gt) ? leanRmseDeg(*lean_est, *lean_gt) : 0;
  m.latency_ms = latency_ms;
  return m;
}

bool gnssOutageMask(const std::vector<IGnssFix>& fixes, std::int64_t t_ns,
                    std::int64_t gap_ns) {
  if (fixes.empty()) return true;
  std::int64_t nearest = 9223372036854775807LL;
  for (const auto& f : fixes) {
    const std::int64_t d = f.t_ns > t_ns ? f.t_ns - t_ns : t_ns - f.t_ns;
    if (d < nearest) nearest = d;
  }
  return nearest > gap_ns;
}

} // namespace nav
