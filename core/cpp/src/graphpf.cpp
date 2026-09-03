#include "nav/graphpf.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <map>
#include <utility>

namespace nav {
namespace {

double clamp01(double x) { return clamp(x, 0.0, 1.0); }

double circDiff(double a, double b) {
  double d = wrap360(a) - wrap360(b);
  if (d > 180.0) d -= 360.0;
  if (d < -180.0) d += 360.0;
  return std::abs(d);
}

double lightCountLikelihood(double along, double spacing, double lux) {
  // Count pulses from the portal — do NOT phase-match [F11].
  if (spacing <= 0.0) return 1.0;
  const int expected = static_cast<int>(std::floor(along / spacing));
  const bool bright = lux > 40.0;
  if (bright) return 1.05;
  return expected > 0 ? 0.98 : 1.0;
}

double baroLikelihood(const IRoadGraph& graph, const IGraphEdge& edge, double hpa) {
  const IGraphNode* from = nodeById(graph, edge.from);
  if (!from) return 1.0;
  const double expected = 1013.25 * std::exp(-from->alt / 8435.0);
  const double dh = (hpa - expected) * 8.435;
  return std::exp(-0.5 * (dh / 3.0) * (dh / 3.0));
}

} // namespace

const IGraphEdge* edgeById(const IRoadGraph& g, const std::string& id) {
  for (const auto& e : g.edges) {
    if (e.id == id) return &e;
  }
  return nullptr;
}

const IGraphNode* nodeById(const IRoadGraph& g, const std::string& id) {
  for (const auto& n : g.nodes) {
    if (n.id == id) return &n;
  }
  return nullptr;
}

std::vector<IGraphEdge> outgoing(const IRoadGraph& g, const std::string& node_id) {
  std::vector<IGraphEdge> out;
  for (const auto& e : g.edges) {
    if (e.from == node_id) out.push_back(e);
  }
  return out;
}

Lla interpolateEdge(const IRoadGraph& g, const IGraphEdge& e, double s) {
  const IGraphNode* a = nodeById(g, e.from);
  const IGraphNode* b = nodeById(g, e.to);
  Lla o;
  if (!a || !b) return o;
  const double u = clamp01(s);
  o.lat = a->lat + (b->lat - a->lat) * u;
  o.lon = a->lon + (b->lon - a->lon) * u;
  o.alt = a->alt + (b->alt - a->alt) * u;
  return o;
}

double projectS(const IRoadGraph& g, const IGraphEdge& e, double lat, double lon) {
  const IGraphNode* a = nodeById(g, e.from);
  const IGraphNode* b = nodeById(g, e.to);
  if (!a || !b) return 0;
  const Enu pa = llaToEnu(g.origin, a->lat, a->lon, a->alt);
  const Enu pb = llaToEnu(g.origin, b->lat, b->lon, b->alt);
  const Enu pq = llaToEnu(g.origin, lat, lon, a->alt);
  const double vx = pb.e - pa.e, vy = pb.n - pa.n;
  const double wx = pq.e - pa.e, wy = pq.n - pa.n;
  const double den = vx * vx + vy * vy;
  return clamp01((wx * vx + wy * vy) / (den > 0.0 ? den : 1.0));
}

std::vector<IGraphEdge> nearestEdges(const IRoadGraph& g, double lat, double lon, int k) {
  struct Scored {
    IGraphEdge e;
    double d;
  };
  std::vector<Scored> scored;
  scored.reserve(g.edges.size());
  for (const auto& e : g.edges) {
    const double s = projectS(g, e, lat, lon);
    const Lla p = interpolateEdge(g, e, s);
    scored.push_back({e, haversineM(lat, lon, p.lat, p.lon)});
  }
  std::sort(scored.begin(), scored.end(),
            [](const Scored& a, const Scored& b) { return a.d < b.d; });
  std::vector<IGraphEdge> out;
  const int n = std::min(k, static_cast<int>(scored.size()));
  for (int i = 0; i < n; ++i) out.push_back(scored[static_cast<std::size_t>(i)].e);
  return out;
}

double adaptiveHorizon(const IGraphEdge& edge, double speed) {
  // [F10] spend heading compute near junctions. Horizon grows with speed.
  double h = 6.0 + speed * 0.8;
  if (h < 8.0) h = 8.0;
  if (h > 28.0) h = 28.0;
  return h * (edge.tunnel ? 1.2 : 1.0);
}

IRoadGraph defaultCampusGraph() {
  IRoadGraph g;
  g.name = "campus";
  g.origin = {12.9912, 77.5523, 920.0};

  auto add_node = [&](const char* id, double e, double n, double u, const char* kind) {
    IGraphNode node;
    node.id = id;
    const Lla lla = enuToLla(g.origin, e, n, u);
    node.lat = lla.lat;
    node.lon = lla.lon;
    node.alt = lla.alt;
    node.kind = kind;
    g.nodes.push_back(node);
  };

  add_node("gate", 0, 0, 0, "outdoor");
  add_node("quad", 40, 80, 0, "outdoor");
  add_node("portal_in", 200, 80, 0, "portal");
  add_node("tun_mid", 520, 80, -2, "tunnel");
  add_node("portal_out", 840, 80, 0, "portal");
  add_node("exit_true", 840, 140, 0, "junction");
  add_node("exit_wrong", 840, 20, 0, "junction");
  add_node("xmark", 40, 20, 0, "outdoor");

  auto add_edge = [&](const char* id, const char* from, const char* to, bool tunnel,
                      double lights) {
    const IGraphNode* a = nodeById(g, from);
    const IGraphNode* b = nodeById(g, to);
    if (!a || !b) return;
    IGraphEdge e;
    e.id = id;
    e.from = from;
    e.to = to;
    double m_lat = 1, m_lon = 1;
    metersPerDeg(a->lat, m_lat, m_lon);
    const double dE = (b->lon - a->lon) * m_lon;
    const double dN = (b->lat - a->lat) * m_lat;
    e.length_m = std::hypot(dE, dN);
    if (e.length_m < 1e-3) e.length_m = 1e-3;
    e.heading_deg = wrap360(rad2deg(std::atan2(dE, dN)));
    e.tunnel = tunnel;
    e.light_spacing_m = lights;
    e.grade = (b->alt - a->alt) / e.length_m;
    g.edges.push_back(e);
  };

  add_edge("e_gate_quad", "gate", "quad", false, 0);
  add_edge("e_quad_portal", "quad", "portal_in", false, 0);
  add_edge("e_tun_a", "portal_in", "tun_mid", true, 12.0);
  add_edge("e_tun_b", "tun_mid", "portal_out", true, 12.0);
  add_edge("e_exit_true", "portal_out", "exit_true", false, 0);
  add_edge("e_exit_wrong", "portal_out", "exit_wrong", false, 0);
  add_edge("e_quad_x", "quad", "xmark", false, 0);
  add_edge("e_x_gate", "xmark", "gate", false, 0);
  return g;
}

GraphParticleFilter::GraphParticleFilter(IRoadGraph g, GraphPfConfig cfg)
    : graph(std::move(g)), n_(cfg.n), rng_(cfg.seed) {}

void GraphParticleFilter::seed(double lat, double lon, double yaw_deg) {
  const auto nearest = nearestEdges(graph, lat, lon, 8);
  particles.clear();
  const double w = 1.0 / std::max(1, static_cast<int>(nearest.size()));
  const int nnear = std::max(1, static_cast<int>(nearest.size()));
  for (int i = 0; i < n_; ++i) {
    if (nearest.empty()) break;
    const IGraphEdge& e = nearest[static_cast<std::size_t>(i % nnear)];
    IParticle p;
    p.edge_id = e.id;
    p.s = 0.15 + 0.7 * rng_.next();
    p.weight = w / (static_cast<double>(n_) / nnear);
    p.heading = e.heading_deg;
    particles.push_back(p);
  }
  if (particles.empty() && !graph.edges.empty()) {
    const IGraphEdge& e0 = graph.edges.front();
    for (int i = 0; i < n_; ++i) {
      IParticle p;
      p.edge_id = e0.id;
      p.s = rng_.next();
      p.weight = 1.0 / n_;
      p.heading = yaw_deg;
      particles.push_back(p);
    }
  }
  normalize();
}

void GraphParticleFilter::step(double dt, double speed, double yaw_deg, double lux,
                               double baro_hpa) {
  const double dist = std::max(0.0, speed) * dt;
  std::vector<IParticle> next;
  next.reserve(particles.size());
  for (const IParticle& p : particles) {
    const IGraphEdge* edge = edgeById(graph, p.edge_id);
    if (!edge) continue;
    double s = p.s + dist / std::max(1e-3, edge->length_m);
    double heading = p.heading;
    std::string id = p.edge_id;
    double w = p.weight;

    const double remaining = 1.0 - p.s;
    const double metres_to_node = remaining * edge->length_m;
    const bool approaching = metres_to_node < adaptiveHorizon(*edge, speed);

    if (s >= 1.0) {
      const auto outs = outgoing(graph, edge->to);
      if (outs.empty()) {
        s = 1.0;
      } else {
        struct Scored {
          IGraphEdge o;
          double lh;
        };
        std::vector<Scored> scored;
        double sum = 0;
        for (const auto& o : outs) {
          const double dH = circDiff(o.heading_deg, yaw_deg);
          const double sigma = outs.size() <= 2 ? 18.0 : 12.0;
          const double lh = std::exp(-0.5 * (dH / sigma) * (dH / sigma));
          scored.push_back({o, lh});
          sum += lh;
        }
        if (sum <= 0.0) sum = 1.0;
        double u = rng_.next() * sum;
        IGraphEdge chosen = scored.front().o;
        for (const auto& sc : scored) {
          u -= sc.lh;
          if (u <= 0.0) {
            chosen = sc.o;
            break;
          }
        }
        const double leftover = (s - 1.0) * edge->length_m;
        id = chosen.id;
        s = leftover / std::max(1e-3, chosen.length_m);
        heading = chosen.heading_deg;
        const double dH = circDiff(chosen.heading_deg, yaw_deg);
        w *= std::exp(-0.5 * (dH / 14.0) * (dH / 14.0));
      }
    } else {
      const double dH = circDiff(edge->heading_deg, yaw_deg);
      const double sigma = approaching ? 10.0 : 28.0;
      w *= std::exp(-0.5 * (dH / sigma) * (dH / sigma));
      heading = edge->heading_deg;
      if (edge->tunnel && edge->light_spacing_m > 0.0) {
        w *= lightCountLikelihood(s * edge->length_m, edge->light_spacing_m, lux);
      }
      if (edge->garage) {
        w *= baroLikelihood(graph, *edge, baro_hpa);
      }
    }
    IParticle np;
    np.edge_id = id;
    np.s = clamp01(s);
    if (np.s > 0.999) np.s = 0.999;
    np.weight = std::max(1e-12, w);
    np.heading = heading;
    next.push_back(np);
    junction_boost = approaching;
  }
  particles = std::move(next);
  normalize();
  if (ess() < n_ * 0.35) resample();
}

INavState GraphParticleFilter::estimate(INavState state) {
  if (particles.empty()) {
    state.mode = "ins";
    return state;
  }
  std::map<std::string, double> by_edge;
  for (const auto& p : particles) by_edge[p.edge_id] += p.weight;
  std::string best_id = particles.front().edge_id;
  double best_w = -1;
  for (const auto& kv : by_edge) {
    if (kv.second > best_w) {
      best_w = kv.second;
      best_id = kv.first;
    }
  }
  const IGraphEdge* edge = edgeById(graph, best_id);
  state.branch_posteriors = by_edge;
  if (!edge) {
    state.mode = "ins";
    return state;
  }
  double mean_s = 0;
  for (const auto& p : particles) {
    if (p.edge_id == best_id) mean_s += p.s * p.weight;
  }
  mean_s /= std::max(1e-9, best_w);
  const Lla ll = interpolateEdge(graph, *edge, mean_s);
  last_edge_ = best_id;
  state.lat = ll.lat;
  state.lon = ll.lon;
  state.alt = ll.alt;
  state.edge_id = best_id;
  state.mode = state.gnss_aided ? "gnss" : "graph";
  state.yaw = deg2rad(edge->heading_deg);
  return state;
}

MapProject GraphParticleFilter::mapProject(double lat, double lon, double yaw_deg) const {
  MapProject out;
  out.lat = lat;
  out.lon = lon;
  const auto cands = nearestEdges(graph, lat, lon, 5);
  int best_i = -1;
  double best_score = 1e300;
  for (int i = 0; i < static_cast<int>(cands.size()); ++i) {
    const IGraphEdge& e = cands[static_cast<std::size_t>(i)];
    const double dH = circDiff(e.heading_deg, yaw_deg);
    const Lla p = interpolateEdge(graph, e, projectS(graph, e, lat, lon));
    const double d = haversineM(lat, lon, p.lat, p.lon);
    const double score = d + 0.15 * dH;
    if (score < best_score) {
      best_score = score;
      best_i = i;
    }
  }
  if (best_i < 0) return out;
  const IGraphEdge& e = cands[static_cast<std::size_t>(best_i)];
  const double s = projectS(graph, e, lat, lon);
  const Lla p = interpolateEdge(graph, e, s);
  out.lat = p.lat;
  out.lon = p.lon;
  out.edge_id = e.id;
  out.residual_m = haversineM(lat, lon, p.lat, p.lon);
  return out;
}

void GraphParticleFilter::normalize() {
  double s = 0;
  for (const auto& p : particles) s += p.weight;
  if (s <= 0.0) s = 1.0;
  for (auto& p : particles) p.weight /= s;
}

double GraphParticleFilter::ess() const {
  double ss = 0;
  for (const auto& p : particles) ss += p.weight * p.weight;
  return ss > 0.0 ? 1.0 / ss : 0.0;
}

void GraphParticleFilter::resample() {
  const int n = static_cast<int>(particles.size());
  if (n <= 0) return;
  std::vector<double> cdf;
  cdf.reserve(static_cast<std::size_t>(n));
  double acc = 0;
  for (const auto& p : particles) {
    acc += p.weight;
    cdf.push_back(acc);
  }
  std::vector<IParticle> out;
  out.reserve(static_cast<std::size_t>(n));
  int i = 0;
  const double u0 = rng_.next() / n;
  for (int j = 0; j < n; ++j) {
    const double u = u0 + static_cast<double>(j) / n;
    while (i < n - 1 && cdf[static_cast<std::size_t>(i)] < u) ++i;
    IParticle src = particles[static_cast<std::size_t>(i)];
    src.weight = 1.0 / n;
    src.s = clamp01(src.s + 0.002 * gauss(rng_));
    out.push_back(src);
  }
  particles = std::move(out);
}

} // namespace nav
