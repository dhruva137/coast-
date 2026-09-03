#pragma once

// Particle filter on the road graph [F9, F10].
// Along an edge, map projection annihilates heading error.
// Heading value is concentrated at junctions — adaptive horizon.

#include "nav/math.h"
#include "nav/types.h"

#include <cstddef>
#include <string>
#include <vector>

namespace nav {

struct GraphPfConfig {
  int n = 256;
  std::uint32_t seed = 26168u;
};

struct MapProject {
  double lat = 0, lon = 0;
  std::string edge_id;
  double residual_m = 0;
};

class GraphParticleFilter {
 public:
  IRoadGraph graph;
  std::vector<IParticle> particles;
  bool junction_boost = false;

  explicit GraphParticleFilter(IRoadGraph g, GraphPfConfig cfg = {});

  void seed(double lat, double lon, double yaw_deg);
  void step(double dt, double speed, double yaw_deg, double lux, double baro_hpa);
  INavState estimate(INavState state);
  MapProject mapProject(double lat, double lon, double yaw_deg) const;

 private:
  void normalize();
  double ess() const;
  void resample();

  int n_ = 256;
  Rng32 rng_;
  std::string last_edge_;
};

IRoadGraph defaultCampusGraph();

const IGraphEdge* edgeById(const IRoadGraph& g, const std::string& id);
const IGraphNode* nodeById(const IRoadGraph& g, const std::string& id);
std::vector<IGraphEdge> outgoing(const IRoadGraph& g, const std::string& node_id);
std::vector<IGraphEdge> nearestEdges(const IRoadGraph& g, double lat, double lon, int k);
Lla interpolateEdge(const IRoadGraph& g, const IGraphEdge& e, double s);
double projectS(const IRoadGraph& g, const IGraphEdge& e, double lat, double lon);
double adaptiveHorizon(const IGraphEdge& edge, double speed);

} // namespace nav
