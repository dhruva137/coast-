# 01 — What the engine actually does

**Read this before writing code.** Phase 3 asks you to visualise this engine.
You cannot draw a mechanism you do not understand, and a visualisation that
misrepresents the mechanism is worse than none — a technical judge will catch it.

---

## A. The problem, precisely

GPS works by trilaterating timing signals from satellites. Those signals are
weak — roughly the power of a car headlight seen from 20,000 km. Concrete,
steel and rock block them completely. So in a tunnel, an underpass, a
multi-level car park, or a deep urban canyon, the receiver has nothing.

Consumer navigation apps respond by freezing the dot, or by snapping it wildly
between guesses. You have all seen it. For a delivery rider it means a missed
exit; for an ambulance it means dispatch loses the vehicle at the worst moment.

The phone still has two sensors that work underground:

- **Accelerometer** — measures proper acceleration, in three axes, in the
  phone's own frame. It cannot distinguish gravity from motion; a phone lying
  still reads ~9.81 m/s² upward.
- **Gyroscope** — measures angular rate about three axes. Integrate it and you
  get orientation change.

The task: from those two signals alone, keep estimating position.

## B. Why the obvious approach fails — and this is the whole pitch

The textbook method is **strapdown inertial navigation**: rotate the
accelerometer reading into the world frame, subtract gravity, integrate once for
velocity, integrate again for position.

It fails on a phone, badly, for a reason worth understanding exactly.

**Errors integrate.** A constant accelerometer bias `b` becomes a velocity error
growing as `b·t` and a position error growing as `½·b·t²`. A consumer MEMS
accelerometer bias of ~0.02 m/s² gives ~36 m of position error after 60 seconds.
That is already fatal.

**Heading is worse.** A gyro bias `ω` makes heading error grow linearly, and
heading error rotates your entire velocity vector. Hold a heading error `θ` over
distance `d` and you land `d·sin(θ)` sideways. At 16°, that is 28% of everything
you travelled, *sideways*. This is why our measurements keep coming back to
heading.

**The result we published:** free dead reckoning passes only **17%** of the
ISRO short-arm criterion and **10%** of the tunnel arm.
→ `lab/stress/results/isro_benchmark/summary.md`

### The experiment that decides the architecture

The instinct at this point is "get a better sensor / a better filter / a better
neural network." **We tested that instinct and it is wrong.**

We gave the algorithm a **perfect gyroscope** — simulated, zero-error,
physically impossible. Free dead reckoning **still failed 55%** of 60-second
segments.
→ `lab/stress/results/heading_ablation/summary.md`

So the sensor was never the binding constraint. Something structural was
missing. That finding is what justifies everything below, and it is the single
most important thing on our deck.

## C. The answer: put the map inside the filter

**The move:** stop estimating a free position in the plane. Estimate a position
**on the road graph**.

- Naive state: `(x, y)` — a point anywhere in ℝ². Nothing forbids being 15 m
  inside a building.
- **Our state: `(edge_id, offset_along_edge)`** — which road you are on, and how
  far along it you are.

Being off-road is **not representable**. There is no such value. Lateral error
cannot accumulate because the state space has no lateral dimension to accumulate
into.

### The control that proves it is the *in-loop* part that matters

We also measured the obvious version: run free dead reckoning, then snap the
finished track to the nearest road. That scores **0.98× — it actively hurts.**
You take a badly-drifted estimate and snap it confidently onto the wrong road.
→ `lab/stress/results/mapmatch/summary.md`

Same map. Opposite architecture. **0.98× versus 2.02×.** That contrast is the
most persuasive object we own.

## D. How the estimator runs, step by step

This is the loop you will visualise in Phase 3.

```
   IMU @ ~100-200 Hz                    ┌─────────────────────────┐
   accel + gyro ──────────────┐         │  OSM road graph          │
                              │         │  35,631 edges / 3,271 km │
   ┌──────────────────────┐   │         └───────────┬─────────────┘
   │ AVNet-tiny (ONNX)    │◄──┤                     │
   │ CNN-GRU speed model  │   │                     │
   └──────────┬───────────┘   │                     │
        speed │               │ yaw rate            │ candidate edges
              ▼               ▼                     ▼
        ┌─────────────────────────────────────────────────┐
        │   PARTICLE FILTER over (edge, offset)           │
        │                                                 │
        │   1. PREDICT   move every particle along its    │
        │                edge by speed·dt; at a junction  │
        │                fork onto each outgoing edge     │
        │   2. WEIGHT    score each particle: does its    │
        │                implied heading match the gyro?  │
        │                is the turn kinematically sane?  │
        │   3. RESAMPLE  kill low-weight particles,       │
        │                duplicate high-weight ones       │
        │   4. OUTPUT    weighted mean → the puck         │
        └─────────────────────────────────────────────────┘
                              │
                     position on a road
```

**Why a particle filter and not a Kalman filter** — have this answer ready:
at a junction the belief is genuinely **multi-modal**. You might be on either
road. A Kalman filter carries one Gaussian and must collapse that to a single
mean — which is wrong exactly at the moment the ambiguity matters most.
Particles carry both hypotheses until the motion resolves them.

### The supporting pieces

- **AVNet-tiny** — a small CNN-GRU that reads a 2-second window of IMU and
  predicts forward speed. Trained on IO-VNBD with vehicle CAN-bus speed as the
  label, leave-file-out. Exported to ONNX, runs on the phone.
  **Honest result:** it *loses* to a naive "hold last speed" baseline on
  per-window RMSE (4.65 vs 1.48 m/s) but *wins* clearly closed-loop over a 60 s
  outage (100 m vs 228 m). Report both — the second is what matters and the
  first is what makes us believable.
- **ZUPT** (zero-velocity update) — when the IMU says stationary, clamp velocity
  to zero. Kills the single largest source of nonsense drift at traffic lights.
- **NHC** (non-holonomic constraint) — a car cannot slide sideways or fly. In our
  implementation this is a heading-consistency term inside the HMM map matcher.
- **HMM map matching** — Newson & Krumm (2009). *Their* algorithm; we cite it.
  Our adaptations for dead-reckoned input: emission sigma grows with time since
  outage onset, and the transition term compares *shape* rather than absolute
  position (drift-invariant to first order).

## E. What is measured, and what is not

Every number below has a file. `win_tuning/CLAIMS.json` is the registry.

| | |
|---|---|
| **Map-in-loop vs free DR** | **2.02× lower median position error** (252.66 m → 125.20 m), 43 real outages, CAN truth |
| **Perfect gyro still fails** | **55%** of 60-s segments |
| **Post-hoc snapping** | **0.98×** — worse than nothing |
| **Median drift** | free 27.58% → COAST **16.77%**. ISRO bar is <10%. **We do not clear it.** |
| **Heading channel** | gyro 16.87% → onset-calibrated compass **7.22%** (2.34×), 655 windows |
| **Edge engine, worst config** | **19,682 Hz** = 98× the 200 Hz requirement |
| **Handover GNSS→DR** | **100 ms** |
| **Honest washes** | GNSS+INS fusion 1.07× · online alignment 32%→32% · mount-invariance near-wash |
| **Our own bug** | a unit error inflating every drift figure **3.6×**, which we found and fixed |

### The limitation we volunteer first

**Map-in-loop kills lateral error. It does not fix along-track error** — right
road, wrong distance along it. This is a known open problem, and it is exactly
why the rail industry still installs physical balises to reset odometry.

Saying this before anyone asks is worth more than any additional feature.

## F. What this means for what you build

Three consequences that should shape your design decisions:

1. **The map is not decoration, it is the algorithm.** A fleet view drawn on a
   bare grid misrepresents the entire thesis. Tracks must sit on real roads.
   (Phase 2.)
2. **The interesting thing is the belief, not the dot.** The particle cloud
   collapsing at a junction, the weight distribution, the moment the filter
   commits to one road — that is the mechanism, and it has never been shown.
   (Phase 3.)
3. **Our credibility comes from published failures.** The 0.98×, the 1.07×, the
   55%, the 3.6× bug. Any surface you build should make those *easy to find*,
   not tuck them away. A registry containing only wins is one nobody believes.
