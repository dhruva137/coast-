import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { enuToLla } from "../math.ts";
import { campusGraph } from "../sim/campus.ts";
import {
  CorridorManifold,
  GraphParticleFilter,
  ManifoldParticleFilter,
  RoadGraphManifold,
  edgeById,
  interpolateEdge,
} from "../graphpf/index.ts";

describe("ConstraintManifold", () => {
  it("CorridorManifold clamps lateral offset and bounds filter error", () => {
    const origin = { lat: 12.9912, lon: 77.5523, alt: 920 };
    const poly = Array.from({ length: 11 }, (_, i) => enuToLla(origin, i * 20, 0, 0));
    const corridor = new CorridorManifold(poly, 3, origin);
    assert.equal(corridor.dim(), 1);
    assert.ok(corridor.length_m() > 190 && corridor.length_m() < 210);

    const off = enuToLla(origin, 100, 8, 0);
    const snapped = corridor.project({
      lat: off.lat,
      lon: off.lon,
      alt: 0,
      yaw_deg: 90,
      edge_id: "",
      s: 0,
      lateral_m: 0,
    });
    const residual = Math.hypot(
      (off.lat - snapped.lat) * 111132.92,
      (off.lon - snapped.lon) * 111412.84 * Math.cos((origin.lat * Math.PI) / 180),
    );
    assert.ok(residual > 4.5 && residual < 5.5, `residual=${residual}`);
    assert.ok(Math.abs(snapped.lateral_m) <= 3 + 1e-9);

    const pf = new ManifoldParticleFilter(corridor, { n: 48, seed: 7 });
    pf.seed(poly[0]!.lat, poly[0]!.lon, 90);
    let maxLat = 0;
    for (let k = 0; k < 40; k++) {
      pf.step(0.5, 10, 90);
      const est = pf.estimate();
      maxLat = Math.max(maxLat, pf.lateralErrorM(est.lat, est.lon));
    }
    assert.ok(maxLat < 3.5, `maxLat=${maxLat}`);
  });

  it("same filter on RoadGraphManifold and CorridorManifold bounds lateral error", () => {
    const g = campusGraph();
    const road = new RoadGraphManifold(g);
    assert.equal(road.dim(), 1);

    const tun = edgeById(g, "tun");
    assert.ok(tun);
    const poly = Array.from({ length: 9 }, (_, i) => interpolateEdge(g, tun!, i / 8));
    const corridor = new CorridorManifold(poly, 4, g.origin);

    const start = poly[0]!;
    const roadPf = new ManifoldParticleFilter(road, { n: 32, seed: 11 });
    const corrPf = new ManifoldParticleFilter(corridor, { n: 32, seed: 11 });
    roadPf.seed(start.lat, start.lon, tun!.heading_deg);
    corrPf.seed(start.lat, start.lon, tun!.heading_deg);

    let maxRoad = 0;
    let maxCorr = 0;
    let maxCorrLat = 0;
    for (let k = 0; k < 30; k++) {
      // Free point drifts north of the tunnel centreline (portal_in ≈ E200 N80).
      const free = enuToLla(g.origin, 200 + 8 * k, 80 + 5 + 0.2 * k, -1);
      roadPf.step(0.4, 12, tun!.heading_deg);
      corrPf.step(0.4, 12, tun!.heading_deg);
      maxRoad = Math.max(maxRoad, roadPf.lateralErrorM(roadPf.estimate().lat, roadPf.estimate().lon));
      maxCorr = Math.max(maxCorr, corrPf.lateralErrorM(corrPf.estimate().lat, corrPf.estimate().lon));
      const cp = corridor.project({
        lat: free.lat,
        lon: free.lon,
        alt: 0,
        yaw_deg: tun!.heading_deg,
        edge_id: "",
        s: 0,
        lateral_m: 0,
      });
      maxCorrLat = Math.max(maxCorrLat, Math.abs(cp.lateral_m));
    }
    assert.ok(maxRoad < 1.0, `maxRoad=${maxRoad}`);
    assert.ok(maxCorr < 4.5, `maxCorr=${maxCorr}`);
    assert.ok(maxCorrLat <= 4 + 1e-6, `maxCorrLat=${maxCorrLat}`);
  });

  it("GraphParticleFilter.mapProject matches RoadGraphManifold.project", () => {
    const g = campusGraph();
    const pf = new GraphParticleFilter(g, { n: 64, seed: 3 });
    const m = new RoadGraphManifold(g);
    const q = enuToLla(g.origin, 100, 85, 0);
    const a = pf.mapProject(q.lat, q.lon, 90);
    const b = m.project({
      lat: q.lat,
      lon: q.lon,
      alt: 0,
      yaw_deg: 90,
      edge_id: "",
      s: 0,
      lateral_m: 0,
    });
    assert.equal(a.edge_id, b.edge_id);
    assert.ok(Math.abs(a.lat - b.lat) < 1e-12);
    assert.ok(Math.abs(a.lon - b.lon) < 1e-12);
  });
});
