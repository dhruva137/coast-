#include "nav/engine.h"

#include "nav/aiding.h"
#include "nav/graphpf.h"
#include "nav/inekf.h"
#include "nav/inference.h"
#include "nav/leansolver.h"
#include "nav/math.h"
#include "nav/metrics.h"
#include "nav/preprocess.h"

#include <algorithm>
#include <cmath>

namespace nav {
namespace {

std::vector<INavState> runOne(const std::vector<ISensorFrame>& frames,
                              const std::vector<IGnssFix>& gnss, const IRoadGraph& graph,
                              bool lean_aware, bool two_wheeler, double hz) {
  SixAxisFilter filt(8.0, hz > 1.0 ? hz : 50.0);
  BiasCalibrator cal;
  FrequencyDecoupledOdo odo(hz > 1.0 ? hz : 50.0);
  InvariantEKF ekf(graph.origin, lean_aware && two_wheeler);
  GraphParticleFilter pf(graph, GraphPfConfig{180, lean_aware ? 1u : 2u});
  LightCounterState light = createLightCounter();

  if (!gnss.empty()) {
    ekf.seedFromGnss(gnss.front());
  } else if (!frames.empty()) {
    IGnssFix seed;
    seed.t_ns = frames.front().t_ns;
    seed.lat = graph.origin.lat;
    seed.lon = graph.origin.lon;
    seed.alt = graph.origin.alt;
    seed.acc_h = 5;
    seed.acc_v = 8;
    ekf.seedFromGnss(seed);
  }
  {
    const INavState s0 = ekf.toState(0);
    pf.seed(s0.lat, s0.lon, 0);
  }

  std::vector<INavState> out;
  out.reserve(frames.size());
  std::size_t gi = 0;
  std::int64_t last_t = frames.empty() ? 0 : frames.front().t_ns;

  for (const ISensorFrame& raw : frames) {
    cal.observe(raw);
    const ISensorFrame f = filt.apply(cal.apply(raw));
    const bool denied = gnssOutageMask(gnss, f.t_ns);
    if (denied) ekf.markOutage();

    while (gi < gnss.size() && gnss[gi].t_ns <= f.t_ns) {
      std::vector<IGnssFix> one{gnss[gi]};
      if (!gnssOutageMask(one, f.t_ns, 800000000LL)) ekf.updateGnss(gnss[gi]);
      ++gi;
    }

    const IGnssFix* last_fix = gi > 0 ? &gnss[gi - 1] : nullptr;
    if (!denied && last_fix) odo.setSpeed(last_fix->speed);
    const OdoEstimate o = odo.push(f);
    if (!denied && last_fix) odo.setSpeed(last_fix->speed);

    ekf.propagate(f);
    const double dt = static_cast<double>(f.t_ns - last_t) / 1e9;
    last_t = f.t_ns;
    if (!lean_aware) {
      ekf.lean = 0;
    } else {
      LeanObservation obs;
      obs.gy = f.gy;
      obs.gz = f.gz;
      obs.gx = f.gx;
      obs.speed = o.speed > 0.0 ? o.speed : ekf.toState(f.t_ns).speed;
      obs.phi0 = ekf.lean;
      obs.has_phi0 = true;
      ekf.lean = solveLean(obs).phi;
    }

    INavState st = ekf.toState(f.t_ns);
    if (denied) {
      const IGraphEdge* edge = edgeById(graph, st.edge_id);
      if (!edge) {
        for (const auto& e : graph.edges) {
          if (e.tunnel) {
            edge = &e;
            break;
          }
        }
      }
      if (edge && edge->light_spacing_m > 0.0) {
        light = stepLightCount(light, f.lux, f.t_ns, edge->light_spacing_m);
      }
      pf.step(std::max(0.001, dt), st.speed, rad2deg(st.yaw), f.lux, f.pressure_hpa);
      st = pf.estimate(st);
    } else {
      const MapProject proj = pf.mapProject(st.lat, st.lon, rad2deg(st.yaw));
      pf.seed(proj.lat, proj.lon, rad2deg(st.yaw));
      st.edge_id = proj.edge_id;
      st.mode = "gnss";
    }
    out.push_back(st);
  }
  return out;
}

} // namespace

EngineResult runEngine(const std::vector<ISensorFrame>& imu,
                       const std::vector<IGnssFix>& gnss, const ILogMeta& meta,
                       const RunOpts& opts) {
  const double hz = opts.target_hz > 0.0
                        ? opts.target_hz
                        : std::min(50.0, meta.imu_hz > 0.0 ? meta.imu_hz : 50.0);
  const std::vector<ISensorFrame> frames = resampleLinear(imu, hz);
  const IRoadGraph graph = opts.has_graph ? opts.graph : defaultCampusGraph();
  bool two_wheeler = opts.two_wheeler;
  if (meta.vehicle == "car") two_wheeler = false;
  if (meta.leans) two_wheeler = true;

  EngineResult r;
  r.meta = meta;
  r.ours = runOne(frames, gnss, graph, true, two_wheeler, hz);
  r.baseline = runOne(frames, gnss, graph, false, false, hz);
  return r;
}

} // namespace nav
