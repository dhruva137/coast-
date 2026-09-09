#pragma once

// ConstraintManifold: map constraint as a plug-in [Phase 2 / F2].
// RoadGraphManifold wraps the shipping road-graph geometry (bit-identical helpers).
// CorridorManifold is a synthetic 1-D polyline + lateral tolerance demo only.

#include "nav/math.h"
#include "nav/types.h"

#include <cstdint>
#include <string>
#include <vector>

namespace nav {

/** Continuous pose + discrete along-track coordinates on a constraint. */
struct ManifoldState {
  double lat = 0;
  double lon = 0;
  double alt = 0;
  double yaw_deg = 0;
  std::string edge_id;  // road edge id, or corridor segment index as string
  double s = 0;         // arc-length fraction along element, [0, 1]
  double lateral_m = 0; // signed lateral offset (corridor); 0 on road centreline
};

class ConstraintManifold {
 public:
  virtual ~ConstraintManifold() = default;

  /** Nearest valid state on the manifold. */
  virtual ManifoldState project(const ManifoldState& state) const = 0;

  /** Reachable candidate states within ``distance_m`` along the manifold. */
  virtual std::vector<ManifoldState> neighbours(const ManifoldState& state,
                                                double distance_m) const = 0;

  /** Non-negative motion cost from ``a`` to ``b`` (metres-ish). */
  virtual double transition_cost(const ManifoldState& a, const ManifoldState& b) const = 0;

  /** Intrinsic dimension of the constraint (1 = along-track). */
  virtual int dim() const = 0;
};

/** Existing campus / OSM road-graph geometry behind the interface. */
class RoadGraphManifold final : public ConstraintManifold {
 public:
  explicit RoadGraphManifold(IRoadGraph graph);

  const IRoadGraph& graph() const { return graph_; }

  ManifoldState project(const ManifoldState& state) const override;
  std::vector<ManifoldState> neighbours(const ManifoldState& state,
                                        double distance_m) const override;
  double transition_cost(const ManifoldState& a, const ManifoldState& b) const override;
  int dim() const override { return 1; }

 private:
  IRoadGraph graph_;
};

/**
 * 1-D polyline with a hard lateral tolerance (rail / channel / tunnel bore).
 * SYNTHETIC DEMO ONLY — not field-validated for rail, undersea, or planetary use.
 */
class CorridorManifold final : public ConstraintManifold {
 public:
  CorridorManifold(std::vector<Lla> polyline, double lateral_tol_m, Lla origin = {});

  double lateral_tol_m() const { return lateral_tol_m_; }
  const std::vector<Lla>& polyline() const { return poly_; }

  ManifoldState project(const ManifoldState& state) const override;
  std::vector<ManifoldState> neighbours(const ManifoldState& state,
                                        double distance_m) const override;
  double transition_cost(const ManifoldState& a, const ManifoldState& b) const override;
  int dim() const override { return 1; }

  /** Along-track arc length of the full polyline (m). */
  double length_m() const { return total_m_; }

  /** Sample centreline at arc length ``s_m`` (clamped). */
  Lla pointAt(double s_m) const;

 private:
  struct Seg {
    Lla a, b;
    double len_m = 0;
    double cum_m = 0;  // arc length at end of segment
    double heading_deg = 0;
  };

  std::vector<Lla> poly_;
  std::vector<Seg> segs_;
  double lateral_tol_m_ = 2.0;
  Lla origin_{};
  double total_m_ = 0;
};

/** Tiny manifold-only particle cloud for regression (not the production GraphPF). */
struct ManifoldFilterConfig {
  int n = 64;
  std::uint32_t seed = 26168u;
};

class ManifoldParticleFilter {
 public:
  ManifoldParticleFilter(const ConstraintManifold& manifold, ManifoldFilterConfig cfg = {});

  void seed(double lat, double lon, double yaw_deg);
  void step(double dt, double speed_mps, double yaw_deg);
  ManifoldState estimate() const;

  /** Max |lateral| of a free position vs manifold centreline after project. */
  double lateralErrorM(double lat, double lon) const;

 private:
  const ConstraintManifold& m_;
  ManifoldFilterConfig cfg_;
  Rng32 rng_;
  std::vector<ManifoldState> particles_;
  std::vector<double> weights_;
};

}  // namespace nav
