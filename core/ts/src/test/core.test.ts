import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { solveLean, yawRateFromLean, headingRateScaleError, carStyleYawRate } from "../leansolver/index.ts";
import { G } from "../math.ts";
import { simulate, defaultConfigs } from "../sim/simulate.ts";
import { runEngine } from "../engine.ts";
import { summarize, driftPct, pathLength, loopClosureError } from "../metrics/index.ts";
import { campusGraph } from "../sim/campus.ts";

describe("F5 fixed-point lean solver", () => {
  it("recovers coordinated-turn lean to < 1e-6 residual", () => {
    const v = 12;
    const phiTrue = 25 * Math.PI / 180;
    const psiDot = (G * Math.tan(phiTrue)) / v;
    const gy = psiDot * Math.sin(phiTrue);
    const gz = psiDot * Math.cos(phiTrue);
    const sol = solveLean({ gy, gz, speed: v, phi0: 0 });
    assert.ok(sol.residual < 1e-6, `residual ${sol.residual}`);
    assert.ok(Math.abs(sol.phi - phiTrue) < 1e-6, `phi ${sol.phi} vs ${phiTrue}`);
    assert.ok(sol.iterations <= 8);
  });

  it("F6: scale error is cos(Δφ), not cos(φ)", () => {
    const dphi = 10 * Math.PI / 180;
    const s = headingRateScaleError(dphi);
    assert.ok(Math.abs(s - Math.cos(dphi)) < 1e-15);
    const car = Math.cos(40 * Math.PI / 180);
    assert.ok(Math.abs(1 - s) < 0.02, "10° lean error → ~1.5%");
    assert.ok(1 - car > 0.22, "car-style at 40° lean is >22%");
  });

  it("car-style yaw is gz, lean-aware uses F2", () => {
    const phi = 0.4;
    const psiDot = 0.5;
    const gy = psiDot * Math.sin(phi);
    const gz = psiDot * Math.cos(phi);
    assert.equal(carStyleYawRate(gz), gz);
    assert.ok(Math.abs(yawRateFromLean(gy, gz, phi) - psiDot) < 1e-12);
  });
});

describe("campus graph", () => {
  it("has tunnel lights and garage fork", () => {
    const g = campusGraph();
    assert.ok(g.edges.some((e) => e.tunnel && e.light_spacing_m));
    assert.ok(g.nodes.some((n) => n.kind === "junction"));
    assert.ok(g.edges.length >= 20);
  });
});

describe("simulator + engine", () => {
  it("produces IMU/GNSS/truth and a moving estimate", () => {
    const log = simulate({ ...defaultConfigs().act2, hz: 25, speed: 6, leanScale: 1 });
    assert.ok(log.imu.length > 50);
    assert.ok(log.truth.length === log.imu.length);
    const { ours, baseline } = runEngine(log.imu, log.gnss, log.meta, { targetHz: 25 });
    assert.ok(ours.length > 20);
    assert.ok(baseline.length > 20);
    const m = summarize(
      ours,
      log.truth,
      log.meta.loop_closure,
      undefined,
      { est: ours.map((s) => s.lean), gt: log.truth.map((t) => t.lean) },
    );
    assert.ok(m.distance_m > 10);
    assert.ok(Number.isFinite(m.loop_closure_m));
  });
});

describe("metrics", () => {
  it("drift % is error / distance", () => {
    assert.equal(driftPct(10, 1000), 1);
    assert.ok(pathLength([{ lat: 0, lon: 0 }, { lat: 0, lon: 0 }]) === 0);
    const lc = loopClosureError([{ lat: 12.99, lon: 77.55 }], { lat: 12.99, lon: 77.55 });
    assert.ok(lc < 0.01);
  });
});
