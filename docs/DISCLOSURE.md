# Technical Disclosure Note

**Title.** Lean-aware heading-rate estimation and junction-concentrated graph evaluation for smartphone inertial navigation of leaning single-track vehicles.

**Matter.** SIH 2026 PS 26168 (ISRO). Lab identifier: SIH26168.

**Document type.** Laboratory notebook record of an unpublished prototype. **Not** a patent application, claim of priority, assignment, or representation to any patent office. Written so a later attorney can reconstruct what was built, observed, and deliberately not asserted.

**Inventors.** ________________ / ________________ / ________________  
*(blank pending contribution review)*

**Date of this record.** 4 September 2026.

**Status.** Unpublished prototype. No filing. No public disclosure intended by this note. All numbers below are from physics simulation unless stated otherwise.

---

## 1. Field

Smartphone inertial navigation (dead reckoning) for **leaning single-track vehicles** — motorcycles and scooters — during GNSS outage. Host sensor: consumer phone IMU (accelerometer, gyroscope), optionally ambient light and barometer. Intended use: on-device fallback when GNSS is denied (tunnel, underpass, basement garage, urban canyon). Distinct from four-wheel automotive dead reckoning and from pedestrian inertial odometry.

---

## 2. Background (prior art — we do not claim)

The following are **prior art as to this note**. We use them; we do not claim to have invented them.

**Qian et al., 2025 (AVNet).** *Satellite Navigation* 6:15. CNN-GRU attitude and velocity into an invariant EKF on SE₂(3), with data-driven NHC and a learned noise adapter. Cars; phone rigidly mounted. Our speed input, if learned, is meant to **compose with** this line of work, not replace it.

**Brossard, Barrau & Bonnabel, 2020 (AI-IMU).** *IEEE T-IV* 5(4):585–595. Invariant EKF plus a CNN that adapts **car** NHC noise. KITTI baseline. Published code is our reproduction floor, not our contribution.

**Titterton & Weston.** *Strapdown Inertial Navigation Technology* (IET). For a yaw-then-roll sequence,

\[
\omega_{\mathrm{body}} = [\dot{\varphi},\ \dot{\psi}\sin\varphi,\ \dot{\psi}\cos\varphi],
\quad
\dot{\psi} = \omega_y\sin\varphi + \omega_z\cos\varphi.
\]

**We do not claim discovery, first statement, or first use of these kinematics.** They are textbook. Any later sentence that “we found \(\omega_z=\dot{\psi}\cos\varphi\)” would be false and would be withdrawn.

---

## 3. Problem

Car NHC and the working approximation \(\dot{\psi}\approx\omega_z\) are **kinematically false** on a leaning single-track vehicle. The error is \(\cos\varphi\) and occurs **during the turn**, when heading is needed. In simulation with bias removed, model-only heading-rate error was about 2% at 11° lean, 23% at 26°, 38% at 34°, 51% at 45°. On a same-direction-turning route it accumulated; an oracle using true lean and the textbook \(\omega_y,\omega_z\) combination did not.

A leaning bike in a coordinated turn has specific force \(\approx[0,0,g/\cos\varphi]\) and looks like “upright but heavier.” Naive \(\varphi=\arccos(g/|f|)\) was biased in our sandbox. An EKF lean estimator we tried was worse. Lean is the bottleneck; the kinematics are not.

---

## 4. Embodiments (as implemented)

Laboratory embodiments, not a product. Described so a skilled person can run the TypeScript prototype.

### A. Fixed-point coordinated-turn lean estimator on a phone

Assume a coordinated turn, \(\tan\varphi \approx v\,\dot{\psi}/g\), and substitute the textbook heading rate:

\[
\varphi = \arctan\!\big(v\,(\omega_y\sin\varphi + \omega_z\cos\varphi)/g\big).
\]

Solve by **fixed-point iteration** from \(\varphi_0=\operatorname{atan2}(v\,\omega_z,g)\), clamped, typically 3–8 iterations. Below a small speed the iteration is unobservable and lean is returned as zero. Inputs: body gyro \(\omega_y,\omega_z\) (optionally \(\omega_x\) as \(\dot{\varphi}\)) and scalar speed \(v\) from learned odometry or GNSS. Host: a smartphone IMU.

In simulation, lean RMSE was about 0.5–1.0° when the coordinated-turn assumption held. We record that **application and solver arrangement** on a phone IMU, not the identities.

### B. Insensitivity used as a robustness argument

If \(\hat{\varphi}=\varphi+\Delta\varphi\), then to machine precision in our check,

\[
\dot{\psi}_{\mathrm{est}} = \dot{\psi}\cdot\cos(\Delta\varphi).
\]

Scale error depends on **lean error**, not lean angle. A 10° lean error at 40° lean is about 1.5% heading-rate error; car-style \(\dot{\psi}\approx\omega_z\) at the same lean is about 23%. We use this as an **operating-point argument**: lean need only be good to roughly 10°. We do not claim the cosine identity as a new physical law.

### C. Adaptive heading compute on a road graph, concentrated at junctions

Along an edge, projecting a drifting position onto the edge removes most of the cross-track effect of heading error (in simulation, 10° → 0.7 m after projection). Heading value is therefore **concentrated at forks**. One embodiment uses a cheap heading likelihood along an edge and tightens the residual (smaller \(\sigma\), longer horizon) when remaining distance to the next node falls below a speed-dependent horizon. The problem is **which outgoing edge**, not free 2-D regression.

Graph particle filters and map projection are old. What we record is the **compute-allocation rule** and the junction-decision framing, in `graphpf`.

### D. Light-pulse **counting** from the portal

Ambient lux is thresholded; rising edges are counted from tunnel entry; along-track distance is \(N\times\) mapped lamp spacing. We **do not** phase-match. Phase matching constrains position only modulo spacing. Counting from the portal is an absolute scale observation. Simulation suggested a modest 9–21% along-track gain at 60% detection / 10% false alarm; the module is under-tuned.

### E. Branch-decision accuracy as an evaluation metric

Complementary to drift percent: **branch-decision accuracy** — the fraction of junctions at which the estimated outgoing edge equals the true outgoing edge. The driver-relevant question is “which ramp,” not only metres of ATE. Implementation: `metrics.branchAccuracy`.

---

## 5. Narrow statements of subject matter

Notebook statements of what this prototype does. Written so they can be defended or abandoned. **Not filed claims.**

1. A method, on a smartphone IMU of a leaning single-track vehicle, of estimating lean and heading rate by **fixed-point iteration** of \(\varphi=\arctan(v(\omega_y\sin\varphi+\omega_z\cos\varphi)/g)\), using body gyro and a scalar speed, and integrating heading with \(\dot{\psi}=\omega_y\sin\varphi+\omega_z\cos\varphi\) rather than \(\omega_z\) alone.

2. Use of \(\dot{\psi}_{\mathrm{est}}/\dot{\psi}=\cos\Delta\varphi\) as a **robustness argument** for that estimator: heading-rate scale error is treated as a function of lean error, not of lean magnitude.

3. On a stored road graph, a particle (or equivalent discrete) filter that **allocates tighter heading likelihood near nodes** than along an edge, for choosing an outgoing edge.

4. Along-track scale in a lit tunnel by **counting** ambient-light pulses from a known portal, using mapped spacing, **without** phase-locked matching to the lamp pattern.

5. Reporting **branch-decision accuracy** (correct outgoing edge at a junction) as an evaluation figure of merit for GNSS-denied vehicle dead reckoning, in addition to drift percent.

**We do not claim, and we ask that no later filing claim without independent advice:**

- Discovery or first statement of roll/yaw strapdown kinematics (Titterton & Weston; any equivalent textbook); “kinematics discovery”; any statement that the \(\cos\varphi\) error was unknown to the inertial literature.
- Map-matching, HMM map-matching, or map-fusion through tunnels as such (Newson & Krumm, 2009; Map-Fusion, 2024).
- Localisation by learned **road vibration signatures** (arXiv 2303.03942).
- Adaptive NHC noise learning, including MTDNN-style multitask DNN calibration of NHC (ENC 2025).
- Replacement of learned odometry / AVNet / AI-IMU. We consume speed; we do not supersede those systems.
- A monopoly, priority date, or “first smartphone two-wheeler DR system.” Unawareness of a published phone paper that treats lean this way is a literature remark, not a first-to-file assertion.

---

## 6. Limitations (honesty)

From the project record of 4 September 2026:

1. Findings F1–F12 are **simulation**. None are validated on a real two-wheeler.
2. The simulator generates lean from the **same** coordinated-turn law the solver assumes. Adversarial wobble, banking, and velocity-scale tests were run in that sandbox; the method has not met a scooter on an Indian road. Whether \(\tan\varphi\approx v\dot{\psi}/g\) holds in traffic is unmeasured.
3. Hard braking or accelerating mid-turn is the known failure mode (0.4 g degraded simulated drift from about 3% to 9.6%; still below car-style in that run).
4. The lean solver **requires speed**. It composes with, and does not replace, learned odometry.
5. Light-pulse counting is under-tuned (9–21% simulated gain).
6. Magnetometer aiding is likely unusable on a two-wheeler (engine and frame distortion).
7. Intended roll ground truth is a frame-mounted second phone, not an AHRS.

A reader who treats the simulated RMSE figures as field performance has misread this note.

---

## 7. Enablement

A skilled person can reproduce the embodiments from the TypeScript prototype without further invention of the maths:

| Embodiment | Module | Entry points |
|---|---|---|
| A, B | `core/ts/src/leansolver` | `solveLean`, `yawRateFromLean`, `headingRateScaleError`, `stepHeading` |
| C | `core/ts/src/graphpf` | `GraphParticleFilter.step`, `adaptiveHorizon`, junction \(\sigma\) |
| D | `core/ts/src/aiding` | `stepLightCount`, `createLightCounter` (count, not phase) |
| E | `core/ts/src/metrics` | `branchAccuracy` |

Simulation noise used IO-VNBD-derived vibration levels and LSM6DSM densities; see `research/exp1..exp8f.py` and `SIH26168_PROJECT_BIBLE.md` §§4, 9, 10. This TypeScript core is the enablement of record.

---

*End of note. If this record conflicts with a later filing, the filing must narrow or disclaim — not this notebook widen.*
