#pragma once

// Metrics — implement before any model. Loop closure is the demo metric.
// Branch-decision accuracy [F12] is what the driver feels.

#include "nav/types.h"

#include <string>
#include <utility>
#include <vector>

namespace nav {

double pathLength(const std::vector<Lla>& states);
double loopClosureError(const std::vector<Lla>& states, const Lla& marker);
double driftPct(double error_m, double distance_m);

double ate(const std::vector<Lla>& est, const std::vector<Lla>& gt);
double rte(const std::vector<Lla>& est, const std::vector<Lla>& gt, int window = 100);

double branchAccuracy(const std::vector<std::string>& predicted,
                      const std::vector<std::string>& truth);
double leanRmseDeg(const std::vector<double>& est, const std::vector<double>& gt);

IMetrics summarize(const std::vector<INavState>& est, const std::vector<Lla>& gt,
                   const Lla& marker,
                   const std::vector<std::string>* pred_edges = nullptr,
                   const std::vector<std::string>* truth_edges = nullptr,
                   const std::vector<double>* lean_est = nullptr,
                   const std::vector<double>* lean_gt = nullptr,
                   double latency_ms = 0);

/** True when no GNSS fix is within gap_ns of t_ns. */
bool gnssOutageMask(const std::vector<IGnssFix>& fixes, std::int64_t t_ns,
                    std::int64_t gap_ns = 1500000000LL);

std::vector<Lla> statesToLla(const std::vector<INavState>& states);

} // namespace nav
