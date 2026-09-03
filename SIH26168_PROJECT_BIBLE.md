# SIH26168 — Intelligent Dead Reckoning
### Project bible: problem, research, architecture, execution

**Problem Statement ID:** 26168
**Title:** AI-ML based Intelligent Dead Reckoning system for seamless navigation
**Organisation:** Indian Space Research Organisation (ISRO)
**Department:** Department of Space
**Category:** Software · **Theme:** Smart Vehicles
**Official dataset:** IO-VNBD — https://github.com/onyekpeu/IO-VNBD

**Status of this document:** living. Last updated 4 Sept 2026.
Everything marked ⚠️ is unverified and must be tested before it is believed.

---

## 0. TL;DR for a new team member

We are building a phone app that keeps navigating accurately when GPS dies —
tunnels, underpasses, basement car parks, urban canyons.

Three things make us different from the other ~5 teams who reach the finale on
this PS:

1. **Two-wheelers.** All published vehicle dead reckoning assumes a car that
   cannot lean. India runs on ~200M scooters and motorcycles that lean into
   every turn. We handle that case; nobody has published it.
2. **We treat it as a graph decision problem, not a regression problem.** We
   don't just estimate a position, we decide *which ramp you took*.
3. **The judge drives the demo.** Loop closure gives us unfakeable ground truth
   with zero infrastructure.

**The single hardest deadline is not the finale. It is 20 September**, when the
proposal — which must contain preliminary models and position plots from
IO-VNBD — is due.

---

## 1. Problem statement in full context

### 1.1 What ISRO actually asked for

Vehicle logistics, ride-hailing, quick commerce and emergency responders rely on
smartphone navigation powered by GNSS (GPS/Galileo/NavIC). In long tunnels,
underpasses, multi-level car parks, dense forested highways and deep urban
canyons, GNSS drops entirely. GNSS is also vulnerable to jamming and
unintentional electromagnetic interference. Apps then freeze, jump erratically,
or miscalculate turns — causing missed exits, delivery delays and safety hazards.

The system must fall back to self-contained inertial navigation (INS) built from
the phone's IMU, dead-reckon through the outage, and switch back to GNSS-aided
INS cleanly on re-acquisition. Low-cost MEMS IMUs suffer sensor biases,
deterministic errors and thermo-mechanical drift.

The PS explicitly names **millions of two-wheelers (motorcycles/scooters)** that
rely solely on the rider's smartphone. **This sentence is our entire opening.**

### 1.2 The published benchmark (this is what we are scored on)

| Requirement | Target |
|---|---|
| Positional drift | < 10% of distance travelled |
| Tunnel accuracy | < 100 m error over 1 km at 60 km/h |
| Update rate | 10 Hz, on-device |
| Proposal requirement | Preliminary AI models **and position plots** inferenced from IO-VNBD |

That last row is the most valuable line in the whole PS. It forces every
applicant to have trained something before submitting. Most will not bother.
**It collapses our competition at the screening stage — but only if we comply.**

### 1.3 Competitive context

SIH 2025 official numbers: 72,165 idea submissions from 68,766 teams against 271
problem statements; 1,360 teams reached the Grand Finale across 60 nodal centres.

- Overall finale rate: **2.0%**
- Teams per PS at the finale: **~5**
- Average submissions per PS: **~266 of a 500 cap**

SIH 2026 has **229** problem statements (fewer slots, same crowd) → average
climbs to ~315 per PS. Monitor the live `n/500` counter on the portal daily.

**What the other teams will build:** a reproduction of AVNet/DMDVDR (see §2.1),
because it is the paper this PS is derived from, its code is public, and it is
the obvious answer. Assume 3 of your 5 finale rivals have a working car-based
DR pipeline. Reproduction is our *floor*, not our contribution.

### 1.4 Judging reality

- Nodal centre jury = org representative (ISRO) + industry professionals +
  host-institute academics. Domain experts in the *problem*, rarely in *our method*.
- 3 mentoring rounds (unscored) + 3 evaluation rounds (scored).
- In the final round **judges use the application themselves**.
- Official criteria: novelty, complexity, clarity, feasibility, practicability,
  sustainability, scale of impact, user experience, future work potential.
- No winner is declared at all against ~2-3% of problem statements. Overclaiming
  and failing is worse than a modest claim, delivered.

---

## 2. Research bibliography

### 2.1 The paper this PS is derived from — read this first

**Qian, Lin, Niu, Huang, Li, Guo, Wang, Chen (2025).** "AVNet: learning attitude
and velocity for vehicular dead reckoning using smartphone by adapting an
invariant EKF." *Satellite Navigation* 6:15, 20 June 2025. Open access.
DOI 10.1186/s43020-025-00168-7

- CNN-GRU ("AVNet") estimates data-driven attitude (DDATT) + velocity (DDODO)
- Fed as pseudo-measurements into an **Invariant EKF** on Lie group SE₂(3)
- Plus data-driven non-holonomic constraint (DDNHC) and a CNN noise adapter
- **0.4% relative horizontal error** in car parks; **0.64% drift** in a 578 m
  tunnel with 55 s GNSS outage
- Phone: Huawei Mate 30, **STMicro LSM6DSM** IMU (gyro 3.8×10⁻³ °/s/√Hz,
  accel 90 µg/√Hz). Trained on an RTX 4090.
- Code: `github.com/DragonEmperorG/QDeepOdo` and `QAIIMUDeadReckoning`
- Logger: `github.com/DragonEmperorG/VDRDataCollector`
- Their stated limitation: *phone was rigidly fixed; dataset small; needs
  generalisation across phones and more complex driving.* **That is our opening.**

### 2.2 Foundational — the InEKF + learned-covariance line

- **Brossard, Barrau, Bonnabel (2020).** "AI-IMU Dead-Reckoning." *IEEE T-IV*
  5(4):585–595. IEKF + CNN adapting noise covariance of NHC pseudo-measurements.
  **1.10% translational error on KITTI**, competitive with LiDAR/stereo methods.
  Code: `github.com/mbrossar/ai-imu-dr` ← **our baseline implementation**
- Brossard et al. (2019). "RINS-W: Robust Inertial Navigation System on Wheels." IROS.
- Brossard, Bonnabel, Barrau (2020). "Denoising IMU Gyroscopes with Deep Learning
  for Open-Loop Attitude Estimation." *RA-L* 5(3).
- Barrau & Bonnabel (2017). "The Invariant EKF as a Stable Observer." *IEEE TAC* 62.
- Barrau & Bonnabel (2023). "The Geometry of Navigation Problems." *IEEE TAC* 68.

### 2.3 Learned pseudo-odometry (what everyone will copy)

- **OdoNet** — Tang, Niu, Zhang, Li, Liu (2022). *IEEE Sensors J* 22(12).
- **SdoNet** — Wang et al. (2023). *IEEE IoT J* 10(21).
- **DeepOdo** — Wang, Weng, Qu, Ding, Chen (2023). *IEEE TIM* 72.
- **DeepVIP** — Zhou et al. (2022). *IEEE T-VT* 71(12).
- **XDRNet** — Zhou et al. (2022). IPIN.
- **OriNet** — Esfahani et al. (2020). *RA-L* 5(2). BiLSTM 3D attitude.

### 2.4 Pedestrian/robot inertial odometry (methods, not application)

- **IONet** — Chen, Lu, Markham, Trigoni (2018). AAAI 32.
- **RoNIN** — Herath, Yan, Furukawa (2020). ICRA.
- **TLIO** — Liu et al. (2020). *RA-L* 5(4). Regresses displacement **and covariance**.
- **PDRNet** — Asraf, Shama, Klein (2021). *IEEE Sensors J* 22(6).
- **IDOL** — Sun, Melamed, Kitani (2021). AAAI 35.

### 2.5 The 2025–26 frontier — none of it applied to vehicles yet

- **TartanIMU** — Zhao, Zhou, Blanchard, Qiu, Wang et al. (2025). CVPR 2025,
  pp. 22520–22529. *A light foundation model for inertial positioning in robotics.*
- **MambaIO** (Nov 2025) — frequency-decoupled: low band → Mamba SSM for
  long-range motion, high band → multi-path conv. SOTA on RIDI, RoNIN, RNIN,
  OxIOD, TLIO, IMUNet. **Directly motivates our backbone (see §4 finding F6).**
- **AirIO** — Qiu et al. (2025). arXiv 2501.15659. IMU feature observability.
- **AirIMU** — arXiv 2310.04874. Learned uncertainty propagation.
- **KISS-IMU** (2026) — self-supervised, motion-balanced, uncertainty-aware.
- **EqNIO** — subequivariant neural inertial odometry.
- **MTDNN** — ENC 2025 (publ. *Eng. Proc.* 2026, 126(1):44). Multitask DNN jointly
  learning IMU calibration, **adaptive NHC noise**, zero-velocity detection.
  ⚠️ Overlaps one of our earlier ideas — cite, do not claim.

### 2.6 Surveys / textbooks

- Chen & Pan (2024). "Deep Learning for Inertial Positioning: A Survey."
  *IEEE T-ITS* 25(9):10506–10523. arXiv 2303.03757.
- Cohen & Klein. "Inertial Navigation Meets Deep Learning." arXiv 2307.00014.
- Titterton & Weston. *Strapdown Inertial Navigation Technology*, IET.
  ← the roll/yaw kinematics in §4/F1 is textbook here. **Do not claim discovery.**
- Groves. *Principles of GNSS, Inertial and Multisensor Integrated Navigation*, 2nd ed.

### 2.7 Map-aided localisation — a POPULATED field, know it before you claim

- **Newson & Krumm (2009).** HMM map matching. The standard formulation.
- **Map-Fusion** (2024). arXiv 2409.01038. Street-network map + intermittent GPS
  + drifting IMU + VO through tunnels and rain, four datasets.
- **"Learning Position From Vehicle Vibration Using an IMU."** arXiv 2303.03942.
  GNSS-free positioning by learning **road signatures** per route segment.
  ⚠️ **This pre-empts the road-signature idea. Cars only. Our residual claim is
  two-wheelers, which couple to the road far more directly than a sprung car.**
- "Vehicle Localization and Control on Roads with Prior Grade Map." arXiv 1809.04167.
- Kim, Im, Jee (2022). "Tunnel Facility-based Vehicle Localization using 3D LIDAR."
  *IEEE T-ITS* 23(10).
- "Vehicle Localization in GPS-Denied Scenarios Using Arc-Length-Based Map
  Matching." arXiv 2410.12208.
- Brož & Tichý (2024). "Road tunnel positioning: enabling LBS in GNSS-denied
  environments." *IEEE Access* 12:156694.
- Niu et al. (2024). **MGINS** — lane-level localisation via magnetic field
  matching/GNSS/INS fusion. *IEEE T-ITS* 25(10).

### 2.8 Opportunistic sensing (our free aiding sources)

- **CRSM** — road surface monitoring on 100 taxis; **90% pothole detection,
  near-zero false alarms**.
- "Assessing and Mapping Road Surface Roughness ... on **Bicycle-Mounted**
  Smartphones." PMC5876687. Correctly recognised speed bumps and manhole covers
  from a bicycle. ← proves our demo vehicle works as a sensor.
- "Toward a mobile crowdsensing system for road surface assessment." Bumps
  localised to **5–10 m**.
- **VS13 dataset** — arXiv 2212.01651. 400 annotated audio-video recordings of
  vehicles at known speeds. Public benchmark for acoustic speed estimation.
- Koops & Franchetti (2015). Ensemble estimation of **speed and gear position**
  from acoustic data. DSP.
- Göksu. "Vehicle speed measurement by on-board acoustic signal processing."
  *Measurement*. ← the on-board case; most acoustic work is roadside arrays.

### 2.9 Datasets

| Dataset | Contents | Note |
|---|---|---|
| **IO-VNBD** | Ford Fiesta, UK/Nigeria/France, **10 Hz**, ~2.2M×24 samples, GPS + CAN + phone IMU | **Required by the PS.** Git LFS. |
| KITTI | Automotive-grade IMU, cars | AI-IMU's benchmark |
| RoNIN / TLIO / OxIOD | Pedestrian IMU | for backbone pretraining |
| GSDC 2023-24 (Kaggle) | Smartphone GNSS+IMU, includes tunnel sections | AVNet used this for their tunnel case study |
| VS13 | Vehicle audio at known speeds | acoustic speed module |
| **Ours (to build)** | **Two-wheeler smartphone IMU** | **Does not exist. This is our artifact.** |

⚠️ IO-VNBD ships via Git LFS. `git lfs install && git lfs pull`. Files appear as
~130-byte pointer stubs otherwise. **Verify a CSV is >1 MB before trusting it.**

---

## 3. What we already know is wrong with the obvious approach

Everyone will reproduce AVNet on IO-VNBD. Three traps:

1. **Sample-rate mismatch.** AVNet windows 200 samples at 200 Hz → 1 Hz output.
   IO-VNBD is **10 Hz**. Copying their window math silently destroys performance
   and you will not know why. Redesign the windowing for 10 Hz.
2. **Rigid mount assumption.** AVNet rigidly bolted the phone to a bracket. Real
   riders use pockets and cheap holders that shift.
3. **Cars only.** IO-VNBD has zero two-wheeler data.

---

## 4. Our experimental findings (sandbox, September 2026)

All from physics simulation with IO-VNBD-derived noise levels (vibration ~0.15 g,
0.08 rad/s) and LSM6DSM noise densities. **None of it is validated on real
two-wheeler data yet.** Code: `research/exp1..exp8f.py`.

**F1 — the kinematic relation.** Yaw ψ about world-z then roll φ about body-x:
```
ω_body = [ φ̇ , ψ̇·sin(φ) , ψ̇·cos(φ) ]
```
So `ω_z = ψ̇·cos(φ)`. Car-derived methods assume ψ̇ ≈ ω_z and are therefore wrong
by cos(lean), exactly during turns. **Textbook kinematics — do not claim
discovery; claim the application.**

**F2 — the exact correction (one line).**
```
ψ̇ = ω_y·sin(φ) + ω_z·cos(φ)          [exact]
```

**F3 — the model error is real, superlinear and does NOT cancel.**
Pure model error, bias removed: 11° lean → 2.2% drift; 26° → 23%; 34° → 38%;
45° → 51%. On a same-direction-turning route it accumulates to **−135° heading
error**. Roll-aware with true lean: 0.04% at every level.

**F4 — lean estimation is the bottleneck, and the obvious estimators fail.**
In a coordinated turn the body-frame specific force is `[0, 0, g/cos φ]` — a
leaning bike is observationally *identical* to "upright but heavier". Naive
`φ = arccos(g/|f|)` has a **+8° bias** (arccos rectifies noise since d|f|/dφ → 0
at φ=0). Our EKF with a derived noise model was **worse: RMSE 34–49°**. Reported
as a failure.

**F5 — the fixed-point solver (this works).** Substitute the coordinated-turn
relation into F2:
```
φ = arctan( v·(ω_y·sin φ + ω_z·cos φ) / g )
```
Solve by fixed-point iteration. Converges in **3–5 iterations**; lean RMSE
**0.5–1.0°**; matches oracle. `v` comes from the learned-velocity network, so
this **composes with** AVNet rather than competing with it.

Survives adversarial perturbation: rider wobble 5° + overshoot → 3.0% drift;
road banking 10° → 3.2%; velocity scale error **±40%** → 3.4%.
**Genuine weakness:** hard braking/accelerating mid-turn — 0.4 g degrades drift
3.0% → 9.6% (still beats car-style's 37%).

**F6 — why it is robust (verified to 2.2×10⁻¹⁶).**
```
ψ̇_est = ψ̇ · cos(φ − φ̂)
```
The scale error depends on the lean **error**, not the lean **angle**.
Car-style at 40° lean: 23.4% error. Ours with a sloppy 10° lean estimate: 1.5%.
**You need lean only to ~10°; we deliver 0.5–1°.**

**F7 — frequency separation justifies the backbone.** Welch PSD: 100% of
vehicle-motion power below 2 Hz; SNR **+29 dB below 2 Hz**, **−34 dB above
10 Hz**. A MambaIO-style low/high split is justified by measurement.

**F8 — the arbitrage. Heading, not speed, is the binding constraint.**

| Error source | Position error | Drift |
|---|---|---|
| AVNet velocity error (0.5 m/s ≈ 5%) | 15.0 m | 1.13% |
| AVNet attitude error (~10°) | 52.3 m | 3.94% |
| cos(lean) error at 34° lean | 84.9 m | 6.40% |
| Phone gyro bias 0.3°/s over 125 s | 188.5 m | **14.20%** |

Equal-effort: 1% speed error → 3.0 m; 1% heading error (3.6°) → 18.9 m.
**Heading is 6.3× more damaging.** The field optimises velocity (the 1.13% term).

**F9 — the map annihilates heading error along an edge.**

| Heading error | Raw 2D error | After map projection | Killed |
|---|---|---|---|
| 10° | 93.4 m | 0.7 m | 99.3% |
| 30° | 276.1 m | 6.3 m | 97.7% |

**F10 — heading value is concentrated at junctions.**

| Junction divergence | Heading accuracy needed |
|---|---|
| ±25° | degrades above ~30° error |
| ±15° | degrades above ~20° error |
| ±8° | degrades above ~10° error |
| 4-way garage, 10% speed err | collapses 75% → 25% |

→ **Design principle: allocate heading compute adaptively — cheap along an edge,
maximum approaching a junction.** Nobody does this because nobody frames DR as a
graph decision problem.

**F11 — light pulses must be COUNTED, not phase-matched.** Phase matching gives
~0% gain (it only constrains position modulo the spacing). Counting from tunnel
entry is absolute: 9–21% along-track improvement, stable at 60% detection rate
with 10% false alarms. ⚠️ Under-tuned; needs work.

**F12 — the metric the field is missing.** Everyone reports drift %. The user
experiences *"did I take the right ramp."* Report **branch-decision accuracy**.

---

## 5. Architecture

### 5.1 Principles

1. **One core, three shells.** The estimator is written once and compiled for
   Android, web and desktop. Never fork the maths.
2. **Replay-first.** Every component must run offline against a recorded log.
   If it only works live, it cannot be debugged at 3 a.m. in the finale.
3. **Loop closure is the metric.** Dev metric and demo metric are identical, so
   every day of development is demo rehearsal.
4. **Degrade, never freeze.** Always output a position and an honest covariance.

### 5.2 Layer diagram

```
┌──────────────────────────────────────────────────────────────────┐
│ L4  PRESENTATION                                                 │
│  Android: Kotlin + Jetpack Compose + MapLibre Native             │
│  Web:     React + Vite + MapLibre GL JS + deck.gl                │
│  Desktop: same web bundle in Tauri/Electron + Python lab console │
└──────────────────────────────────────────────────────────────────┘
                               ▲  position, covariance, edge, events
┌──────────────────────────────────────────────────────────────────┐
│ L3  NAVIGATION CORE   (C++17, one codebase)                      │
│   ├── preprocess    resample, Butterworth, bias cal, ZUPT/ZIHR   │
│   ├── inference     ONNX Runtime → velocity + attitude + covar   │
│   ├── leansolver    fixed-point coordinated-turn solver  [F5]    │
│   ├── inekf         Invariant EKF on SE₂(3)                      │
│   ├── graphpf       particle filter on the road graph  [F9,F10]  │
│   ├── aiding        light-count, acoustic speed, barometer [F11] │
│   └── metrics       loop closure, drift %, branch accuracy [F12] │
│                                                                  │
│  Compiles to: .so via NDK/JNI │ .wasm via Emscripten │ native    │
└──────────────────────────────────────────────────────────────────┘
                               ▲  ISensorFrame (uniform struct)
┌──────────────────────────────────────────────────────────────────┐
│ L2  SENSOR ABSTRACTION  (platform adapters → identical struct)   │
│  Android  SensorManager 200Hz · Fused/GNSS · Baro · Light · Mic  │
│  Web      DeviceMotionEvent (~60Hz) · Geolocation · no baro      │
│  Desktop  CSV / rosbag replay only                               │
└──────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────┐
│ L1  MAP  OSM extract → compact binary graph (nodes, edges,       │
│          headings, tunnel flags, light spacing, grade)  offline  │
└──────────────────────────────────────────────────────────────────┘
```

### 5.3 Pragmatic fallback (decide by 15 Oct)

C++ → JNI + WASM is the right architecture and a real risk for a 14-week student
team. **Fallback:** implement the core twice — Kotlin for Android, TypeScript for
web — with a shared golden-vector test suite (same input log → same output
trajectory, asserted to 1e-6). Uglier, but ships.
**Decision rule:** if WASM + JNI builds are not both green by 15 Oct, fork.

### 5.4 Android app

- Kotlin, min SDK 26, Jetpack Compose
- `SensorManager` at `SENSOR_DELAY_FASTEST`, `TYPE_ACCELEROMETER_UNCALIBRATED`
  and `TYPE_GYROSCOPE_UNCALIBRATED` (raw, so *we* own bias estimation),
  plus `TYPE_PRESSURE` and `TYPE_LIGHT`
- ONNX Runtime Mobile (NNAPI EP, CPU fallback) — model < 5 MB, target < 10 ms/inference
- MapLibre Native + offline MBTiles (no API key, no billing)
- Foreground service so logging survives screen-off
- **Two modes:** `RECORD` (raw CSV to disk, for data collection) and
  `NAVIGATE` (live estimation). Record mode ships in week 1.

### 5.5 Web app

Purpose: the **research console and judge-facing explainer**, not the primary
product. Runs the same WASM core over uploaded logs.

- React + Vite + TypeScript, MapLibre GL JS, deck.gl for particle clouds
- Drag-drop a log → replay with a scrubber, speed control, step-through
- Side-by-side trace comparison (baseline vs ours) ← **demo Act 2**
- Live plots: lean estimate, covariance ellipse, particle cloud, branch posterior
- Runs fully client-side. No backend, no cost, works offline at the venue.
- ⚠️ `DeviceMotionEvent` needs HTTPS + a user gesture on iOS and caps ~60 Hz.
  Treat live web sensing as a bonus, not a dependency.

### 5.6 Desktop / PC

Two things, both cheap:

1. **Tauri shell** around the identical web bundle → an offline binary for the
   judges' table. ~5 MB, no Electron bloat. (Electron is the fallback.)
2. **Python lab console** (`lab/`) — training, batch evaluation, plot generation.
   This is where models are made; it never ships to a phone.

### 5.7 Repository layout

```
sih26168/
├── core/                 C++17 navigation core (the crown jewels)
│   ├── include/nav/      preprocess.h inference.h leansolver.h inekf.h
│   │                     graphpf.h aiding.h metrics.h
│   ├── src/
│   ├── bindings/         jni/  wasm/  pybind/
│   └── tests/            golden-vector tests, gtest
├── android/              Kotlin app
├── web/                  React + Vite console
├── desktop/              Tauri shell
├── lab/                  Python: training, eval, plots
│   ├── baselines/        ai-imu-dr and AVNet reproductions
│   ├── datasets/         io_vnbd.py, ours.py
│   └── research/         exp1..exp8f.py  (the simulation studies)
├── maps/                 OSM extraction → binary graph
├── data/                 (gitignored) raw logs
└── docs/                 this file, ADRs, the preprint
```

### 5.8 Log schema — freeze this in week 1, never change it

`data/<rider>/<vehicle>/<YYYYMMDD_HHMMSS>/imu.csv`

```
t_ns, ax, ay, az, gx, gy, gz, mx, my, mz, pressure_hpa, lux
```
`gnss.csv`: `t_ns, lat, lon, alt, speed, bearing, acc_h, acc_v, n_sats`
`meta.json`: phone model, mount type, vehicle, rider, route id, loop-closure
marker lat/lon, notes.

Units: SI, uncalibrated where available, monotonic `t_ns` from
`SystemClock.elapsedRealtimeNanos()`. **Any log missing `meta.json` is worthless.**

### 5.9 Metrics — implement before any model

| Metric | Definition | Why |
|---|---|---|
| **Loop closure error** | \|p_end − p_start\| when returning to a marked point | Ground truth with zero infrastructure. Demo + dev metric. |
| Drift % | final error ÷ distance travelled | The ISRO benchmark |
| ATE / RTE | KITTI-style, sub-sequences 100–900 m | Comparable to published work |
| Error CDF | percentile position error | Tails, not means |
| **Branch-decision accuracy** | % of junctions where the correct edge was chosen | **[F12] The metric we define** |
| Lean RMSE | vs reference | Two-wheeler module health |
| On-device latency | ms/inference, Hz sustained | 10 Hz requirement |

---

## 6. Data plan — the thing that silently runs out of time

**Start week 1. Not week 4.**

| Set | Vehicle | Route | Purpose |
|---|---|---|---|
| A | Car | IO-VNBD (download) | Required baseline |
| B | **Bicycle** | Campus loops, marked start/end | Leaning dynamics, free, immediate |
| C | Scooter | Urban route: turns, roundabout, potholes | The real target |
| D | Scooter/car | Underpass / tunnel, GNSS at both ends | Demo Act 3 |
| E | Any | Basement car park, multi-level | Barometer + garage graph |

**A bicycle is a leaning single-track vehicle with the same kinematics as a
scooter.** It costs nothing, is on every campus, and unblocks the two-wheeler
work immediately. Do not wait for a motorcycle.

Every session: three mount positions (handlebar clamp, pocket, tank bag), two
phone models minimum, and **always return to the marked start point** so every
log is self-labelling via loop closure.

⚠️ Roll ground truth is hard without an AHRS rig. Acceptable proxy: a second
phone strapped rigidly to the **frame** (not the rider). State this honestly in
the evaluation section rather than claiming precision you cannot verify.

---

## 7. Execution plan

### Sprint 0 — by 7 Sept (BLOCKING, do today)
- [ ] `git lfs install && git lfs pull` IO-VNBD; verify a CSV is >1 MB
- [ ] Clone and run `ai-imu-dr` and `QDeepOdo` unmodified
- [ ] Android `RECORD` mode: raw IMU → CSV. No UI. Two hours of work.
- [ ] Loop-closure + drift evaluation harness (`lab/eval/`)
- [ ] Freeze the log schema (§5.8)
- [ ] Screenshot the `n/500` counter

### Sprint 1 — by 18 Sept (SUBMISSION)
- [ ] AVNet/DMDVDR reproduced on IO-VNBD — **fix the 10 Hz windowing**
- [ ] **Position plots from IO-VNBD** ← the PS requirement
- [ ] First bicycle dataset (≥ 10 loops)
- [ ] PPT: error-budget table [F8], IO-VNBD plots, two-wheeler gap, architecture
- [ ] Video (phone recording beats Figma)
- [ ] **Submit by 18 Sept.** Portals fail on deadline day.

### Sprint 2 — October: the core
- [ ] C++ core skeleton + golden-vector tests; JNI and WASM builds green
- [ ] Frequency-decoupled backbone [F7]; export ONNX
- [ ] Fixed-point lean solver in C++ [F5]
- [ ] InEKF on SE₂(3)
- [ ] Scooter + tunnel datasets
- [ ] **15 Oct: WASM/JNI go/no-go decision (§5.3)**

### Sprint 3 — November: the system
- [ ] Real-time on-device inference at 10 Hz — the dot moves live
- [ ] OSM → binary graph; graph particle filter [F9, F10]
- [ ] Adaptive heading compute near junctions [F10]
- [ ] Opportunistic aiding: light counting [F11], barometer, acoustic speed
- [ ] Web console with side-by-side replay
- [ ] Branch-decision accuracy reporting [F12]

### Sprint 4 — December: the demo
- [ ] Run demo Act 1 **fifty times with fifty different people** until it never fails
- [ ] Tauri desktop build for the judges' table
- [ ] Offline map tiles bundled — assume no venue wifi
- [ ] Business case: cost, SDK model, target customers
- [ ] Limitations slide (§10) — under-claim deliberately
- [ ] **Freeze two hours before the round. No exceptions.**

### Team split (6 people, everyone owns a metric)

| # | Owner of | Success measured by |
|---|---|---|
| 1 | Backbone + ONNX export | velocity/attitude RMSE, model size, latency |
| 2 | Lean solver + InEKF | lean RMSE, drift % on two-wheeler data |
| 3 | Graph PF + map pipeline | branch-decision accuracy |
| 4 | Data collection + the public dataset | hours logged, routes, loop-closure coverage |
| 5 | Baselines + evaluation harness | reproduction fidelity vs published numbers |
| 6 | Android/web/desktop + demo + business | demo success rate over 50 trials |

---

## 8. The demo script

**Constraint:** the finale is in a college building in December. You cannot drive
a car through a tunnel in front of a judge. Everything must work on a campus, in
five minutes, driven by a tired stranger.

**Act 1 — The handoff (60 s).** Judge holds the phone. Walk from outside (GPS
locked) into the basement. GPS dies. Dot keeps moving. They walk a loop of *their*
choosing back to a marked X. Screen: *"closure error 4.2 m over 180 m = 2.3%."*

**Act 2 — The vehicle (90 s).** Bicycle in the car park. Two traces, one screen:
reproduced AI-IMU baseline vs ours, same ride. Baseline diverges at every turn.

**Act 3 — The benchmark (60 s).** Replay a real underpass drive with GNSS at both
ends: *"entered here, predicted exit here, GPS says here — 38 m over 1.1 km =
3.4%"* against ISRO's <10% / <100 m per km.

**Act 4 — The metric (60 s).** *"Every team quotes drift percentage. Here's what a
driver experiences: did we take the right ramp? 100% across 40 runs at ±25°
junctions, degrading at ±8°."*

**Act 5 — The ask (30 s).** 200M two-wheelers, any phone, zero hardware, ships as
an SDK to ride-hailing, delivery fleets and ambulance services.

---

## 9. Novelty claims — say exactly this, no more

✅ **Defensible:**
- First smartphone dead-reckoning system handling **leaning two-wheelers**
- Fixed-point coordinated-turn solver [F5] with the cos(Δφ) insensitivity
  property [F6]
- Error-budget analysis showing heading dominates speed 6.3× [F8]
- **Branch-decision accuracy** as an evaluation metric [F12]
- Public two-wheeler inertial dataset (if we ship it)
- Two-wheelers as superior road-signature sensors (cars' suspensions filter the
  signal we want)

❌ **Do NOT claim:**
- "Discovering" the roll/yaw kinematics — Titterton & Weston, textbook
- Map-matching for tunnels — Newson & Krumm 2009, Map-Fusion 2024
- Road-signature localisation — arXiv 2303.03942 got there first
- Mount-angle estimation — Wang et al. already published
- Adaptive NHC noise — MTDNN, ENC 2025

A defence-grade jury rewards calibrated humility and punishes overclaiming.
Under-claim deliberately.

---

## 10. Known limitations (put this on our own slide)

1. Findings F1–F12 are **simulation**. Not yet validated on real two-wheeler data.
2. The simulator generates lean using the same coordinated-turn law the solver
   assumes. It survived adversarial perturbation (§F5) but has never met a real
   scooter. ⚠️ **Test whether `tan(φ) ≈ v·ψ̇/g` holds on a real Indian road.**
3. Hard braking/accelerating mid-turn is the genuine failure mode (0.4 g →
   9.6% drift).
4. The method needs speed as input; it composes with, and does not replace,
   learned odometry.
5. Light-pulse counting is under-tuned (9–21% gain).
6. Magnetometer aiding is likely unusable on a two-wheeler (engine/frame distortion).
7. Roll ground truth uses a frame-mounted second phone, not an AHRS.

---

## 11. Open questions — assign an owner to each

| # | Question | Owner | Due |
|---|---|---|---|
| Q1 | Does `tan(φ) ≈ v·ψ̇/g` hold on a real scooter in traffic? | #2 | 20 Sept |
| Q2 | Do tunnel/underpass lights give a clean ambient-light pulse train at speed? | #3 | 15 Oct |
| Q3 | Does tyre noise amplitude track speed usably from inside a vehicle? | #1 | 1 Nov |
| Q4 | What is IO-VNBD's true usable rate after 10 Hz windowing redesign? | #5 | 18 Sept |
| Q5 | Is two-PS submission allowed in 2026? (ask SPOC) | #6 | 6 Sept |
| Q6 | Barometer resolution on our actual phones, in a real garage? | #4 | 15 Oct |

---

## 12. Reference card

- PS portal: https://www.sih.gov.in/sih2026PS → ID 26168
- Dataset: https://github.com/onyekpeu/IO-VNBD (Git LFS)
- Baseline: https://github.com/mbrossar/ai-imu-dr
- AVNet: https://github.com/DragonEmperorG/QDeepOdo
- AVNet filter: https://github.com/DragonEmperorG/QAIIMUDeadReckoning
- Logger reference: https://github.com/DragonEmperorG/VDRDataCollector
- AVNet paper: https://doi.org/10.1186/s43020-025-00168-7

**Benchmark to beat:** <10% drift · <100 m per km at 60 km/h · 10 Hz on-device
**Submission deadline:** 20 September 2026 (submit 18th)
**Grand finale:** December 2026, 36 hours
