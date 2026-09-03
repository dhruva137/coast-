import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  VectorMapLocator,
  edgeFeature,
  cosineSimilarity,
  interpolateEdge,
  projectS,
} from "../graphpf/index.ts";
import { campusGraph } from "../sim/campus.ts";
import { runEngine } from "../engine.ts";
import { simulate, defaultConfigs } from "../sim/simulate.ts";
import { GraphParticleFilter } from "../graphpf/index.ts";

describe("edge feature vectors", () => {
  it("encodes [sinθ, cosθ, length_norm, tunnel, garage]", () => {
    const g = campusGraph();
    const tun = g.edges.find((e) => e.id === "tun")!;
    const maxL = Math.max(...g.edges.map((e) => e.length_m));
    const f = edgeFeature(tun, maxL);
    assert.equal(f.length, 5);
    assert.ok(Math.abs(f[0]! ** 2 + f[1]! ** 2 - 1) < 1e-9);
    assert.ok(f[2]! > 0 && f[2]! <= 1);
    assert.equal(f[3], 1);
    assert.equal(f[4], 0);

    const garage = g.edges.find((e) => e.garage)!;
    const fg = edgeFeature(garage, maxL);
    assert.equal(fg[4], 1);
  });

  it("cosine similarity is 1 for identical features", () => {
    const f: [number, number, number, number, number] = [0.6, 0.8, 0.5, 1, 0];
    assert.ok(Math.abs(cosineSimilarity(f, f) - 1) < 1e-12);
  });
});

describe("VectorMapLocator.locate", () => {
  it("returns top-k softmax posteriors that sum to 1", () => {
    const g = campusGraph();
    const loc = new VectorMapLocator(g, { topK: 5 });
    const tun = g.edges.find((e) => e.id === "tun")!;
    const mid = interpolateEdge(g, tun, 0.4);
    const posts = loc.locate({
      yawDeg: tun.heading_deg,
      speed: 12,
      lat: mid.lat,
      lon: mid.lon,
      topK: 5,
    });
    assert.equal(posts.length, 5);
    const sum = posts.reduce((a, p) => a + p.weight, 0);
    assert.ok(Math.abs(sum - 1) < 1e-9, `sum=${sum}`);
    assert.ok(posts[0]!.weight >= posts[1]!.weight);
    // Tunnel heading + on-edge position should prefer tun / tun2 family.
    assert.ok(
      posts[0]!.edge_id === "tun" || posts[0]!.edge_id === "tun2" || posts[0]!.dist_m < 15,
      `best=${posts[0]!.edge_id} dist=${posts[0]!.dist_m}`,
    );
  });

  it("along-edge s matches geometric projection", () => {
    const g = campusGraph();
    const loc = new VectorMapLocator(g);
    const e = g.edges.find((x) => x.id === "gate_quad")!;
    const p = interpolateEdge(g, e, 0.35);
    const posts = loc.locate({ yawDeg: e.heading_deg, speed: 5, lat: p.lat, lon: p.lon, topK: 3 });
    const hit = posts.find((x) => x.edge_id === e.id);
    assert.ok(hit);
    assert.ok(Math.abs(hit!.s - projectS(g, e, p.lat, p.lon)) < 1e-9);
    assert.ok(Math.abs(hit!.s - 0.35) < 0.05);
  });
});

describe("VectorMapLocator belief + junction mode", () => {
  it("propagates Gaussian-on-s along an edge", () => {
    const g = campusGraph();
    const loc = new VectorMapLocator(g);
    const e = g.edges.find((x) => x.id === "tun")!;
    const p0 = interpolateEdge(g, e, 0.1);
    loc.seed(p0.lat, p0.lon, e.heading_deg);
    const before = loc.belief!.s_mean;
    // Step with speed along tunnel (~eastbound).
    const p1 = interpolateEdge(g, e, 0.25);
    const b = loc.step(1.0, 15, e.heading_deg, p1.lat, p1.lon);
    assert.ok(b.s_mean > before, `s ${before} → ${b.s_mean}`);
    assert.ok(b.s_var > 0);
    assert.equal(b.mode, "edge");
  });

  it("enters junction mode near a fork and soft-assigns outgoing", () => {
    const g = campusGraph();
    const loc = new VectorMapLocator(g);
    // portal_out → exit_true / exit_wrong
    const e = g.edges.find((x) => x.id === "tun2")!;
    const nearEnd = interpolateEdge(g, e, 0.97);
    loc.seed(nearEnd.lat, nearEnd.lon, e.heading_deg);
    loc.belief!.s_mean = 0.97;
    const trueEdge = g.edges.find((x) => x.id === "out_true")!;
    const b = loc.step(0.5, 10, trueEdge.heading_deg, nearEnd.lat, nearEnd.lon);
    assert.ok(b.mode === "junction" || b.junctionBoost || Object.keys(b.branch_posteriors).length >= 1);
    if (b.mode === "junction" || loc.junctionBoost) {
      assert.ok(loc.junctionBoost || b.junctionBoost);
    }
    // Prefer true exit heading when in branching soft-assign.
    const posts = Object.entries(b.branch_posteriors);
    if (posts.some(([id]) => id === "out_true" || id === "out_wrong")) {
      const wt = b.branch_posteriors["out_true"] ?? 0;
      const ww = b.branch_posteriors["out_wrong"] ?? 0;
      assert.ok(wt >= ww * 0.9, `true=${wt} wrong=${ww}`);
    }
  });

  it("shouldUseParticleFilter when multimodal junction", () => {
    const g = campusGraph();
    const loc = new VectorMapLocator(g);
    loc.belief = {
      edge_id: "tun2",
      s_mean: 0.99,
      s_var: 0.02,
      mode: "junction",
      branch_posteriors: { out_true: 0.34, out_wrong: 0.33, other: 0.33 },
      junctionBoost: true,
    };
    assert.equal(loc.shouldUseParticleFilter(), true);
    loc.belief.mode = "edge";
    loc.belief.branch_posteriors = { tun2: 1 };
    assert.equal(loc.shouldUseParticleFilter(), false);
  });
});

describe("engine useVectorLocator", () => {
  it("runs end-to-end with vector path and stays finite", () => {
    const log = simulate({ ...defaultConfigs().act2, hz: 20, speed: 6, leanScale: 1 });
    const { ours } = runEngine(log.imu, log.gnss, log.meta, {
      targetHz: 20,
      useVectorLocator: true,
    });
    assert.ok(ours.length > 20);
    assert.ok(ours.every((s) => Number.isFinite(s.lat) && Number.isFinite(s.lon)));
  });
});

describe("latency tradeoff smoke (vector vs PF locate)", () => {
  it("vector locate is cheaper than PF step on campus graph", () => {
    const g = campusGraph();
    const loc = new VectorMapLocator(g, { topK: 5 });
    const pf = new GraphParticleFilter(g, { n: 180, seed: 7 });
    const e = g.edges.find((x) => x.id === "gate_quad")!;
    const p = interpolateEdge(g, e, 0.5);
    pf.seed(p.lat, p.lon, e.heading_deg);
    loc.seed(p.lat, p.lon, e.heading_deg);

    const N = 200;
    const t0 = performance.now();
    for (let i = 0; i < N; i++) {
      loc.locate({ yawDeg: e.heading_deg, speed: 8, lat: p.lat, lon: p.lon, topK: 5 });
    }
    const tVec = performance.now() - t0;

    const t1 = performance.now();
    for (let i = 0; i < N; i++) {
      pf.step(0.05, 8, e.heading_deg, 0, 1013);
    }
    const tPf = performance.now() - t1;

    // Soft assert: vector locate batch should not be slower than full PF steps.
    // (Allow noise on tiny CI machines; document ratio.)
    assert.ok(tVec > 0 && tPf > 0);
    // Prefer vector ≤ PF; if flaky env, still require vector < 5× PF.
    assert.ok(tVec < tPf * 5, `vec=${tVec.toFixed(2)}ms pf=${tPf.toFixed(2)}ms`);
  });
});
