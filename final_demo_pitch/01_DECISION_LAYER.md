# 01 — Decision Layer

**The understanding, top to end, before a single new line of code.** This is the
file to read if you read only one.

---

## A. Where we actually are (verified, not aspirational)

### The science (laptop) — strong and honest

| Thing | Number | Source of truth |
|---|---|---|
| Free DR, short arm (<5 m / 50 m, <60 s) | **70/403 = 17%** | `lab/stress/results/isro_benchmark/summary.md` |
| Free DR, tunnel arm (<10% & <100 m/km, 60 s) | **33/328 = 10%** | same |
| Free DR given a **perfect** yaw sensor | **still fails 55%** (84/186 pass) | `lab/stress/results/heading_ablation/summary.md` |
| Post-hoc map snapping | **0.98× — it hurts** | `lab/stress/results/mapmatch/` |
| **Map-in-loop particle filter** | **2.02×**, pass 8→17 of 43 | `lab/stress/results/mapfilter/summary.md` |
| Edge engine throughput | **120,305 Hz**, 8.3 µs/sample, 7.5 MB | `core/cpp/apps/README.md` |
| Handover GNSS→DR | **100 ms** | `lab/stress/results/` |
| Speed model (AVNet-tiny, CAN-labelled, leave-file-out) | per-window wash, ONNX exports | `lab/models/run_speed_bakeoff.py` |
| The unit bug we found in our own pipeline | inflated every drift 3.6× | `docs/AUDIT_AND_PLAN.md` |

### The product (Android) — builds, never run on hardware

- App compiles (debug + release + AAB), 47–68 JVM unit tests pass.
- MapLibre + OSM basemap wired (no key, no billing), ONNX inference wired.
- **0 minutes on a real phone.** This is the single biggest unknown.
- UI problem: the map is a **300 dp box** (`ui/DriveScreen.kt:170`), not
  full-screen. No blackout-injection, no ghost car, no settings/sessions/login,
  no live-training surface.

### The repo

- Branch: `demo` (branches reconciled; `main` science + COAST StepDetector merged).
- `web/` is a replay/evidence console (no live sensor read, no phone tracking).
- Substantial `docs/` already exist — reuse them, don't rewrite: `ARCHITECTURE_V2.md`,
  `AUDIT_AND_PLAN.md`, `JUDGE_CROSS_EXAM.md`, `PROOF_PROTOCOL.md`, `ISRO_RELEVANCE.md`.

---

## B. What the rules are REALLY asking for (F1–F10 → our artifact)

The precursor grades F1–F8 off the PPT (Round 1) and F9–F10 off the live
pitch/Q&A/teamwork (Round 2). For each criterion, the artifact that scores it:

| # | Criterion | What a judge wants to see | Our artifact (where it lives) |
|---|---|---|---|
| **F1** | Innovation & Creativity | A genuinely non-obvious idea | **Map *inside* the filter loop** (not post-hoc) + **the measured heading ceiling** (perfect gyro still fails 55%) → PPT slides 4–6 |
| **F2** | Technical Feasibility | Complex, feasible, scalable | Dual deliverable: **same C++ core** → 10 Hz phone + **200 Hz edge engine** (120k Hz measured). PPT slide 7 + `02_RESEARCH_FINDINGS.md` |
| **F3** | UX & Design | Clean, accessible, inclusive | **Uber-black full-screen map app** + live HUD + offline persistence → `04_APP_UI_SPEC.md`, shown live in Round 2 |
| **F4** | Impact & Usefulness | Real problem, many use cases | 200M+ two-wheelers + trucks + older cars; ambulances, logistics, metro; ISRO defence angle → PPT slides 2–3, `docs/ISRO_RELEVANCE.md` |
| **F5** | Technical Execution | Prototype, code quality, stack | Working APK + **live on-laptop training that generates figures in front of the judge** → `06_LIVE_TRAINING_AND_FIGURES_SPEC.md` |
| **F6** | Sustainability & Future Scope | Long-term viability, eco | Zero extra hardware, zero cloud, offline, runs on phones people already own; roadmap to FOG-grade IMU edge box → PPT slide 9 |
| **F7** | Business Viability | Market, revenue, affordability | SDK licensing to OEMs/logistics; free consumer app; ₹0 marginal cost → PPT slide 9, `docs/ENTERPRISE_PRODUCT.md` |
| **F8** | Security & Privacy | Data protection, compliance | **No user data leaves the device**; **basemap-off = zero network**. App still declares INTERNET for public OSM/Carto tiles only (B6 offline-only drop not done — do **not** claim “no INTERNET permission”). Phone-tracker (file 07) is opt-in, LAN-only → PPT slide 8 |
| **F9** | Presentation & Communication | Clarity, pitch, Q&A | The 3-act demo + the Q&A bank → `03_PPT_SPEC.md` §Q&A, `docs/JUDGE_CROSS_EXAM.md` |
| **F10** | Collaboration & Teamwork | Team dynamics, ownership | Per-member code ownership + rehearsed handoffs → `03_PPT_SPEC.md` §Team |

**The read on the trajectory of these rules:** F1/F2/F5 reward *depth you can
defend*; F3/F9 reward *a demo that visibly works*; F8 rewards a *checkable*
privacy property; F4/F6/F7 reward *framing*. We are strong on depth and framing
already. The gap is F3/F5/F9 — making the depth *visible and live*. That is
exactly what files 04–07 build.

---

## C. The precise changes to make (this is the "what to change" list)

Ordered by leverage for Friday. Full specs in the referenced files.

### P0 — must work by Friday 11 Sep

1. **PPT in the official SIH template**, slide-by-slide per `03_PPT_SPEC.md`,
   carrying the exact numbers from §D below. *This alone decides Round 1.*
2. **Full-screen Uber-black map** — delete the `.height(300.dp)` box, map fills
   the screen, dark style, track + vehicle puck on top, HUD overlay. `04_APP_UI_SPEC.md`.
3. **Blackout-injection demo mode** — an in-app replay engine that streams an
   IO-VNBD drive through the real pipeline, with a big "Simulate GNSS Blackout"
   toggle and a HUD that flips GNSS→IDR. This is the Round-2 money shot.
   `05_DEMO_MODES_SPEC.md`.
4. **Live training + figures module** — one short terminal command trains the
   speed model and writes `trajectory_overlay.png` (3-line plot) + `cdf_error.png`
   into a `figures/` folder, in ~60–90 s, reproducibly, in front of the judge.
   `06_LIVE_TRAINING_AND_FIGURES_SPEC.md`.
5. **Stability hardening + sensor-injection test** — inject synthetic left/right
   IMU frames, assert the pipeline actually moves the estimate; NaN/crash/
   lifecycle guards; ONNX-load-fail fallback. `05_DEMO_MODES_SPEC.md` §Stability.
6. **Pre-recorded backup video** of the demo (rules explicitly allow the fallback).

### P1 — strong upgrade if P0 is solid

7. **Ghost car** — second (red) puck showing naive integration flying off-road
   while our (green) puck hugs the street. `05_DEMO_MODES_SPEC.md` §Ghost.
8. **Settings + Sessions/history + login stub** screens. `04_APP_UI_SPEC.md`.
9. **Localhost phone-tracker dashboard** — phone POSTs position to the laptop on
   the LAN; a local web page shows the phone's live dot. `07_...`.
10. **ZUPT tabletop + dynamic-alignment live tests** surfaced in the app.

### P2 — for 30 Sep finals, NOT Friday

11. GNSS+INS tightly-coupled fusion engine (when GNSS present).
12. Online alignment engine (oracle says ~1.57× upside).
13. Field scooter/bike logs with loop closure.
14. On-phone measured latency.

---

## D. The numbers (use these verbatim — do not invent)

Put these on slides and say them out loud. Each has a source file; a judge can
be shown the file.

- **2.02×** — map-in-loop vs. free dead-reckoning, 43 outages, CAN ground truth.
  Cite the **full** run: `lab/stress/results/mapfilter/summary.md`. Live
  `python -m lab.demo` is a **fast re-run of the method** that regenerates
  figures; it does not replace the committed 2.02× headline.
- **Perfect gyro still fails 55%** of 60 s segments (84/186 pass). The negative
  result. `lab/stress/results/heading_ablation/summary.md`.
- **17%** short-arm / **10%** tunnel-arm free-DR pass rates (baseline we beat).
- **120,305 Hz** edge-engine throughput (200 Hz requirement met 600×).
- **100 ms** GNSS→DR handover.
- **3.6×** — the unit bug we found and fixed in our own pipeline (the "we really
  built this" story).
- **3,271 km / 35,631 edges** — the offline OSM graph, independent of the drives.

**Do NOT claim:** a sub-10% tunnel result we haven't hit; ZUPT drift reduction
(not measured end-to-end); first-ever phone INS; beating any specific paper; any
live road drive we didn't run; a confidence radius (the signal is broken).

---

## E. Strategic calls already made (do not relitigate)

- **MapLibre + OSM, not Google Maps.** No key, no billing, offline-capable,
  PS names OSM. Reconfirmed. (Full reasoning: `docs/PROJECT_STATE.md` §4.)
- **Phone-only, no extra hardware** — it is the product thesis and the PS's own
  framing. Barometer is the one free "extra" worth using (floor changes).
- **Web PWA + APK both**, framed as "try-it-now surface" + "the real product".
- **General smartphone-navigator headline**, two-wheeler lean as a
  differentiator, not the lead (`docs/POSITIONING.md`).
- **Honesty rules in `00_READ_ME_FIRST.md` override any spec** that tempts a fake.

---

## F. Risk register for Friday

| Risk | Mitigation |
|---|---|
| No time to test on a physical phone | Demo leans on in-app replay (honest) + laptop live-training; pre-recorded video backup |
| Venue wifi dead | Everything offline by design; phone-tracker is LAN-only and optional |
| Live training crashes on judge's watch | Module must be idempotent, <90 s, pre-warmed once; keep last-good figures committed as fallback |
| Cursor over-builds P2 and misses P0 | `08_EXECUTION_ORDER_AND_ACCEPTANCE.md` hard-gates P0 first |
| A judge asks "did you fake this?" | The 3.6× bug story + the volunteered negative result + "point at any line" |
