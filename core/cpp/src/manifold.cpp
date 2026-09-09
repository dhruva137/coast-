#include "nav/manifold.h"

#include "nav/graphpf.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <sstream>

namespace nav {
namespace {

double circDiffAbs(double a, double b) {
  double d = wrap360(a) - wrap360(b);
  if (d > 180.0) d -= 360.0;
  if (d < -180.0) d += 360.0;
  return std::abs(d);
}

}  // namespace

// ---------------------------------------------------------------------------
// RoadGraphManifold — thin wrap over existing graphpf free functions
// ---------------------------------------------------------------------------

RoadGraphManifold::RoadGraphManifold(IRoadGraph graph) : graph_(std::move(graph)) {}

ManifoldState RoadGraphManifold::project(const ManifoldState& state) const {
  ManifoldState out = state;
  const auto cands = nearestEdges(graph_, state.lat, state.lon, 5);
  if (cands.empty()) return out;

  int best_i = -1;
  double best_score = 1e300;
  for (int i = 0; i < static_cast<int>(cands.size()); ++i) {
    const IGraphEdge& e = cands[static_cast<std::size_t>(i)];
    const double dH = circDiffAbs(e.heading_deg, state.yaw_deg);
    const Lla p = interpolateEdge(graph_, e, projectS(graph_, e, state.lat, state.lon));
    const double d = haversineM(state.lat, state.lon, p.lat, p.lon);
    const double score = d + 0.15 * dH;
    if (score < best_score) {
      best_score = score;
      best_i = i;
    }
  }
  if (best_i < 0) return out;
  const IGraphEdge& e = cands[static_cast<std::size_t>(best_i)];
  const double s = projectS(graph_, e, state.lat, state.lon);
  const Lla p = interpolateEdge(graph_, e, s);
  out.lat = p.lat;
  out.lon = p.lon;
  out.alt = p.alt;
  out.edge_id = e.id;
  out.s = s;
  out.yaw_deg = e.heading_deg;
  out.lateral_m = 0.0;
  return out;
}

std::vector<ManifoldState> RoadGraphManifold::neighbours(const ManifoldState& state,
                                                         double distance_m) const {
  std::vector<ManifoldState> out;
  const IGraphEdge* edge = edgeById(graph_, state.edge_id);
  if (!edge) {
    // Seed from geometry if edge unknown.
    const auto near = nearestEdges(graph_, state.lat, state.lon, 8);
    for (const auto& e : near) {
      ManifoldState n;
      n.edge_id = e.id;
      n.s = 0.0;
      n.yaw_deg = e.heading_deg;
      const Lla p = interpolateEdge(graph_, e, 0.0);
      n.lat = p.lat;
      n.lon = p.lon;
      n.alt = p.alt;
      out.push_back(n);
    }
    return out;
  }

  const double remain_m = (1.0 - state.s) * edge->length_m;
  if (remain_m >= distance_m) {
    ManifoldState n = state;
    n.s = clamp(state.s + distance_m / std::max(1e-3, edge->length_m), 0.0, 0.999);
    const Lla p = interpolateEdge(graph_, *edge, n.s);
    n.lat = p.lat;
    n.lon = p.lon;
    n.alt = p.alt;
    n.yaw_deg = edge->heading_deg;
    out.push_back(n);
    return out;
  }

  const auto outs = outgoing(graph_, edge->to);
  for (const auto& o : outs) {
    ManifoldState n;
    n.edge_id = o.id;
    n.s = 0.0;
    n.yaw_deg = o.heading_deg;
    const Lla p = interpolateEdge(graph_, o, 0.0);
    n.lat = p.lat;
    n.lon = p.lon;
    n.alt = p.alt;
    out.push_back(n);
  }
  if (out.empty()) {
    ManifoldState n = state;
    n.s = 0.999;
    const Lla p = interpolateEdge(graph_, *edge, n.s);
    n.lat = p.lat;
    n.lon = p.lon;
    n.alt = p.alt;
    out.push_back(n);
  }
  return out;
}

double RoadGraphManifold::transition_cost(const ManifoldState& a,
                                          const ManifoldState& b) const {
  const double dist = haversineM(a.lat, a.lon, b.lat, b.lon);
  const double dH = circDiffAbs(a.yaw_deg, b.yaw_deg);
  return dist + 0.05 * dH;
}

// ---------------------------------------------------------------------------
// CorridorManifold
// ---------------------------------------------------------------------------

CorridorManifold::CorridorManifold(std::vector<Lla> polyline, double lateral_tol_m, Lla origin)
    : poly_(std::move(polyline)), lateral_tol_m_(std::max(0.1, lateral_tol_m)), origin_(origin) {
  if (poly_.size() < 2) return;
  if (origin_.lat == 0.0 && origin_.lon == 0.0) {
    origin_ = poly_.front();
  }
  segs_.reserve(poly_.size() - 1);
  double cum = 0;
  for (std::size_t i = 0; i + 1 < poly_.size(); ++i) {
    Seg s;
    s.a = poly_[i];
    s.b = poly_[i + 1];
    s.len_m = haversineM(s.a.lat, s.a.lon, s.b.lat, s.b.lon);
    if (s.len_m < 1e-6) s.len_m = 1e-6;
    cum += s.len_m;
    s.cum_m = cum;
    s.heading_deg = headingBetween(s.a.lat, s.a.lon, s.b.lat, s.b.lon);
    segs_.push_back(s);
  }
  total_m_ = cum;
}

Lla CorridorManifold::pointAt(double s_m) const {
  if (segs_.empty()) return origin_;
  s_m = clamp(s_m, 0.0, total_m_);
  for (const auto& seg : segs_) {
    const double start = seg.cum_m - seg.len_m;
    if (s_m <= seg.cum_m || &seg == &segs_.back()) {
      const double u = (s_m - start) / seg.len_m;
      Lla p;
      p.lat = seg.a.lat + (seg.b.lat - seg.a.lat) * u;
      p.lon = seg.a.lon + (seg.b.lon - seg.a.lon) * u;
      p.alt = seg.a.alt + (seg.b.alt - seg.a.alt) * u;
      return p;
    }
  }
  return poly_.back();
}

ManifoldState CorridorManifold::project(const ManifoldState& state) const {
  ManifoldState out = state;
  if (segs_.empty()) return out;

  double best_d = std::numeric_limits<double>::infinity();
  double best_s_m = 0;
  double best_lat_err = 0;
  double best_heading = 0;
  std::size_t best_seg = 0;

  for (std::size_t i = 0; i < segs_.size(); ++i) {
    const Seg& seg = segs_[i];
    const Enu pa = llaToEnu(origin_, seg.a.lat, seg.a.lon, seg.a.alt);
    const Enu pb = llaToEnu(origin_, seg.b.lat, seg.b.lon, seg.b.alt);
    const Enu pq = llaToEnu(origin_, state.lat, state.lon, seg.a.alt);
    const double vx = pb.e - pa.e, vy = pb.n - pa.n;
    const double wx = pq.e - pa.e, wy = pq.n - pa.n;
    const double den = vx * vx + vy * vy;
    const double t = clamp((wx * vx + wy * vy) / (den > 0.0 ? den : 1.0), 0.0, 1.0);
    const double cx = pa.e + t * vx, cy = pa.n + t * vy;
    // Signed left-of-track lateral (ENU 2D cross / segment length).
    const double lat_m = (wx * (-vy) + wy * vx) / std::max(std::sqrt(den), 1e-9);
    const double dx = pq.e - cx, dy = pq.n - cy;
    const double d = std::hypot(dx, dy);
    if (d < best_d) {
      best_d = d;
      best_s_m = (seg.cum_m - seg.len_m) + t * seg.len_m;
      best_lat_err = lat_m;
      best_heading = seg.heading_deg;
      best_seg = i;
    }
  }

  const double clamped_lat = clamp(best_lat_err, -lateral_tol_m_, lateral_tol_m_);
  const Lla centre = pointAt(best_s_m);
  // Offset laterally within tolerance (unit left normal in ENU).
  const Seg& seg = segs_[best_seg];
  const Enu pa = llaToEnu(origin_, seg.a.lat, seg.a.lon, seg.a.alt);
  const Enu pb = llaToEnu(origin_, seg.b.lat, seg.b.lon, seg.b.alt);
  const double vx = pb.e - pa.e, vy = pb.n - pa.n;
  const double len = std::hypot(vx, vy);
  const double nx = len > 0 ? -vy / len : 0;
  const double ny = len > 0 ? vx / len : 0;
  const Enu c = llaToEnu(origin_, centre.lat, centre.lon, centre.alt);
  const Lla snapped = enuToLla(origin_, c.e + nx * clamped_lat, c.n + ny * clamped_lat, c.u);

  out.lat = snapped.lat;
  out.lon = snapped.lon;
  out.alt = snapped.alt;
  out.yaw_deg = best_heading;
  out.s = total_m_ > 0 ? best_s_m / total_m_ : 0;
  out.lateral_m = clamped_lat;
  std::ostringstream id;
  id << best_seg;
  out.edge_id = id.str();
  return out;
}

std::vector<ManifoldState> CorridorManifold::neighbours(const ManifoldState& state,
                                                        double distance_m) const {
  std::vector<ManifoldState> out;
  if (segs_.empty()) return out;
  const double s0 = clamp(state.s, 0.0, 1.0) * total_m_;
  for (double ds : {-distance_m, distance_m}) {
    ManifoldState probe = state;
    const Lla p = pointAt(s0 + ds);
    probe.lat = p.lat;
    probe.lon = p.lon;
    probe.alt = p.alt;
    probe.s = total_m_ > 0 ? clamp(s0 + ds, 0.0, total_m_) / total_m_ : 0;
    out.push_back(project(probe));
  }
  return out;
}

double CorridorManifold::transition_cost(const ManifoldState& a, const ManifoldState& b) const {
  const double along = std::abs(a.s - b.s) * total_m_;
  const double lat = std::abs(a.lateral_m - b.lateral_m);
  return along + 0.5 * lat;
}

// ---------------------------------------------------------------------------
// ManifoldParticleFilter (synthetic regression harness)
// ---------------------------------------------------------------------------

ManifoldParticleFilter::ManifoldParticleFilter(const ConstraintManifold& manifold,
                                               ManifoldFilterConfig cfg)
    : m_(manifold), cfg_(cfg), rng_(cfg.seed) {}

void ManifoldParticleFilter::seed(double lat, double lon, double yaw_deg) {
  particles_.clear();
  weights_.clear();
  ManifoldState probe;
  probe.lat = lat;
  probe.lon = lon;
  probe.yaw_deg = yaw_deg;
  const ManifoldState base = m_.project(probe);
  const auto nbrs = m_.neighbours(base, 5.0);
  const int n = std::max(1, cfg_.n);
  for (int i = 0; i < n; ++i) {
    ManifoldState p = nbrs.empty() ? base : nbrs[static_cast<std::size_t>(i % nbrs.size())];
    p.s = clamp(p.s + 0.02 * (rng_.next() - 0.5), 0.0, 1.0);
    particles_.push_back(m_.project(p));
    weights_.push_back(1.0 / n);
  }
}

void ManifoldParticleFilter::step(double dt, double speed_mps, double yaw_deg) {
  const double dist = std::max(0.0, speed_mps) * dt;
  for (std::size_t i = 0; i < particles_.size(); ++i) {
    ManifoldState& p = particles_[i];
    p.yaw_deg = yaw_deg;
    auto cands = m_.neighbours(p, dist);
    if (cands.empty()) {
      p = m_.project(p);
      continue;
    }
    // Pick lowest transition cost that also matches yaw.
    double best = 1e300;
    ManifoldState chosen = cands.front();
    for (const auto& c : cands) {
      const double cost = m_.transition_cost(p, c) + 0.1 * circDiffAbs(c.yaw_deg, yaw_deg);
      if (cost < best) {
        best = cost;
        chosen = c;
      }
    }
    weights_[i] *= std::exp(-0.05 * best);
    particles_[i] = m_.project(chosen);
  }
  double sum = 0;
  for (double w : weights_) sum += w;
  if (sum <= 0) sum = 1;
  for (double& w : weights_) w /= sum;
}

ManifoldState ManifoldParticleFilter::estimate() const {
  if (particles_.empty()) return {};
  std::size_t best = 0;
  for (std::size_t i = 1; i < weights_.size(); ++i) {
    if (weights_[i] > weights_[best]) best = i;
  }
  return particles_[best];
}

double ManifoldParticleFilter::lateralErrorM(double lat, double lon) const {
  ManifoldState probe;
  probe.lat = lat;
  probe.lon = lon;
  const ManifoldState proj = m_.project(probe);
  return haversineM(lat, lon, proj.lat, proj.lon);
}

}  // namespace nav
