# SIH26168 Navigation SDK — Commercial Integration Guide

**Package versions:** workspace `0.2.0` · `@sih26168/nav-core` `0.2.0` · `@sih26168/web` `0.2.0` · Android `versionName 0.2.0`

**Honest scope.** This SDK is a **GNSS-denied dead-reckoning fallback** for leaning single-track vehicles (motorcycles / scooters) with an optional **map-aided product mode**. Real IO-VNBD logs used for regression are **cars**. Two-wheeler field proof requires bicycle / motorcycle logs — do not claim it from car data alone.

---

## Modes

| Mode | What it does | When to sell / use |
|---|---|---|
| **Open-loop DR** | Bias-calibrated gyro + speed hold (car-style or lean-aware yaw). No map. | Debug, telemetry, demos. Expect FAIL on 40–60 s phone-gyro outages (physics). |
| **Map-aided product** | Gyro-bias cal on GNSS seed → DR with per-step snap to a **known-route polyline** → blend heading toward segment tangent. | Production fallback when the app already has a route / fleet corridor / OSM edge. Cross-track dies; along-track residual remains. |
| **Map-blind (lab)** | Map built from GNSS *outside* the outage only. | Stress honesty check — not the primary product claim. |

The prototype gate requires injected adversarial TW `PASS_CLAIM`, car lean≈car sanity, and ≥1 map-aided 60 s scenario at `PASS_COMPETITIVE+`. It can emit only `RESEARCH_PROTOTYPE_PASS`, explicitly not deployment readiness. The deployment gate is separate and stricter; it is the default.

---

## Latency budget (on-device)

| Stage | Target | Notes |
|---|---:|---|
| IMU sample → lean / yaw-rate | **&lt; 2 ms** | Fixed-point lean solver (~3–8 iters); no network. |
| Pose integrate (open-loop) | **&lt; 0.5 ms** | Heading + speed step. |
| Map project + heading blend | **&lt; 1 ms** | Local window around last segment (~±48 verts). |
| End-to-end tick @ 10–50 Hz | **&lt; 5 ms** p99 | Leaves headroom for UI / GNSS. |

Web (TypeScript) and Android (Kotlin) share the same lean kinematics; map corridor helpers live in the stress lab Python today and should be ported 1:1 for production (see `lab/stress/map_aid.py`).

---

## Web integration (`@sih26168/nav-core` + `@sih26168/web`)

```bash
npm install
npm run build -w @sih26168/nav-core
npm run dev -w @sih26168/web
```

1. Feed phone IMU (`gx, gy, gz`) and scalar speed (GNSS or learned odometry).
2. Call the lean-aware yaw-rate solver each tick (open-loop mode).
3. On GNSS deny: freeze last-good speed; keep integrating with **bias-corrected** `gz` / lean yaw.
4. If a route polyline is available (ENU or LLA→ENU): switch to **map-aided product mode** — snap + blend heading to tangent.
5. Render trail with MapLibre (`web/`); do not treat open-loop position as truth after ~20 s without a map.

**API surface (conceptual):** `solveLean(gy, gz, speed, gx?)` → `{ phi, psiDot }` · `integrate(dt, speed, yawRate, pose)` · `mapAid.step(pose, yaw, mapPrior)`.

---

## Android integration

App module: `android/` · `versionName = "0.2.0"`.

1. Use `LeanSolver.kt` for on-device lean / yaw-rate (mirrors TypeScript / Python).
2. `RecordService` / GNSS hub already collect IMU + GPS for field logs — keep logging during trials.
3. Product path: when navigation has an active route corridor, enable map snap + heading blend; otherwise stay open-loop and surface uncertainty (do not silently claim lane-level fix).
4. Background: respect OS location / sensor limits; DR tick should stay on a single sensor thread.

---

## Bias calibration (required for product mode)

Estimate constant `gz` bias only on the **GNSS-available seed window** (GPS yaw rate vs phone `gz`), then **freeze** it for the outage. Never re-estimate bias from held-out GT inside the gap. See `lab/stress/hardened_outage.py` → `estimate_gyro_bias_z`.

---

## Evaluation & gates

```bash
# Real LFS CSVs only (>1 MB under data/raw/IO-VNBD)
python lab/stress/run_hardened_battery.py
npm run gate:prototype    # RESEARCH_PROTOTYPE_PASS possible; not deployment
npm run gate:deployment   # default strength; currently DEPLOYMENT_READY_FAIL
# equivalents: python lab/stress/product_gate.py --level {prototype|deployment}
```

Artifacts: `lab/stress/results/hardened_report.json`, `hardened_summary.md`.

Verdict labels: `PASS_ISRO` (drift &lt;10% and &lt;100 m/km) · `PASS_COMPETITIVE` · `FAIL`. No soft green.

Deployment requires corrected alignment on at least two files, at least 80% of
real 60 s mid/high-speed trials meeting both ISRO bars, nominal-95% covariance
coverage of at least 90% (or a documented explicit calibrated target), and at
least 10 qualifying real two-wheeler field logs. Current status:
`DEPLOYMENT_READY_FAIL`.

---

## What you can claim vs cannot

| Claim | Status |
|---|---|
| Lean-aware kinematics reduce same-direction turn error vs car-style `gz` (adversarial TW) | Supported in lab injection (`PASS_CLAIM`) |
| On cars, lean ≈ car (sanity) | Supported on real IO-VNBD |
| Map-aided 60 s corridor mode can be competitive on real phone logs | Research prototype evidence only; one low-speed scenario / three methods |
| Open-loop phone gyro meets ISRO 60 s bars without map | **Do not claim** — consistently FAIL |
| Two-wheeler field proof on real bikes | **Blocker** — need bicycle / motorcycle logs |

See also `docs/DISCLOSURE.md` and `docs/ENTERPRISE_BLOCKERS.md`.
