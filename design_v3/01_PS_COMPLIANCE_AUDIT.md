# 01 — Problem Statement Compliance Audit

**Every explicit requirement in PS 26168, against what is actually in the repo
as of 9 Sep 2026.** Verified by reading the code, not by trusting the docs.

This is the most important file for Round 2 Q&A. A judge holding the problem
statement will go down this list. We should have gone down it first.

**Legend:** ✅ done and measured · 🟡 partial / honest limitation · ❌ gap ·
📋 stated design decision (deliberately not done, with a reason)

---

## A. The six "Expected Solution" deliverables

### 1. In-Vehicle Alignment & Calibration Engine 🟡
> *"automatically determines the phone's pitch, roll, and yaw relative to the
> vehicle's driving direction, whether dashboard-mounted or in a mobile holder"*

**Have:** `android/.../nav/MountCalibration.kt` — mount alignment on device.
`lab/models/gravity_canonical.py` + `run_mount_invariant.py` — EqNIO-style
gravity-axis canonicalisation, **measured**.

**The honest result:** online alignment measured **32% → 32% — a wash** on this
corpus (`lab/stress/results/alignment/summary.md`). The oracle mount reached 37%,
so there *is* headroom we did not capture. Gravity canonicalisation was also
near-wash on per-window RMSE, **but measurably improved mount-swap stability**
(probe ΔRMSE +2.110 → +0.785, a 63% reduction in degradation under a random
device rotation).

**What to say:** *"Pitch and roll we solve well — gravity gives them directly, and
our canonicalisation cuts mount-swap error degradation by about two thirds. Yaw
relative to the vehicle is the hard one, and our online alignment was a wash on
this dataset. The oracle says there's about 5 points of pass-rate available
there — it's a named next step, not a solved problem."*

**Gap to close if there is time:** surface alignment state in the UI (see
Vehicle Check in `03_APP_DESIGN_SPEC.md`) so it is *visible* even though the
closed-loop gain is not yet there.

### 2. AI Speed & Vibration Filter ✅🟡
> *"filters out high-frequency road noise/potholes and directly estimates vehicle
> forward velocity from IMU signals"*

**Have:** AVNet-tiny (CNN-GRU), trained on IO-VNBD with CAN-bus speed labels,
leave-file-out protocol, exported to ONNX, **running on the phone**
(`nav/OnnxSpeedModel.kt`). Vibration/motion handling in `nav/VehicleProfile.kt`
and `nav/Zupt.kt`.

**The honest result:** the model **loses to a naive "hold last speed" baseline on
per-window RMSE** (4.65 m/s vs 1.48 m/s), but **wins closed-loop** — 3/3 folds,
median 60 s distance error 100 m vs 228.5 m frozen-onset. That is a genuinely
interesting result and we should present it as one, not hide it.

**What to say:** *"Per-window, our speed model is beaten by simply holding the
last known speed — we report that. But over a 60-second outage it wins clearly,
because the errors don't correlate the way a frozen estimate's do. We optimise
for the thing that matters, which is where you end up, not per-sample RMSE."*

**Explicitly required by PS and worth verifying we can demonstrate:** dynamic
detection/filtering of *engine idling vibration, pothole shocks, and accidental
mount misalignment*. ZUPT covers idling/stationary. Pothole rejection and
misalignment detection should be **shown in the UI** even if the underlying
handling is simple — see Vehicle Check.

### 3. Advanced Map-Matching & Kinematic Constraints ✅
> *"e.g. UKF + Hidden Markov Map Matching… apply Non-Holonomic Constraints (NHC)"*

**Have:** `lab/nav/mapmatch.py` — Hidden Markov map matching, Newson & Krumm
(2009), properly attributed in the module docstring as *their* algorithm. Two
genuine adaptations for dead-reckoned input (growing emission sigma; shape-over-
position transition cost). **NHC is implemented** as a heading-consistency term
inside the matcher — the docstring explicitly says it "encodes the non-holonomic
constraint the problem statement asks for."

Plus the map-in-loop particle filter (**2.02× lower median position error**) and
now `core/cpp/include/nav/manifold.h` with `RoadGraphManifold` +
`CorridorManifold`.

**Note on UKF:** the PS says *"e.g. … Unscented Kalman Filter + HMM"* — "e.g." is
illustrative, not mandatory. We use a **particle filter** instead, and we have a
strong reason: the state space is a graph, so belief at a junction is genuinely
multi-modal and a UKF's single Gaussian cannot represent it. **Have this answer
ready** — a judge may ask why we did not use the named example.

**This is our strongest deliverable. Lead with it.**

### 4. GNSS+INS Fusion Engine ❌🟡  ← **the biggest compliance gap**
> *"an innovative **AI based** Sensor Fusion Algorithm that combines GNSS & IMU
> measurements and provides significant improvement"*

**Have:** a **classical** loosely-coupled EKF. Measured: 49.29 m vs GNSS 52.63 m
vs INS 114.57 m = **1.07× — effectively a wash**
(`lab/stress/results/gnss_ins_fusion/summary.md`).

**Two problems, both real:**
1. The PS asks for an **AI-based** fusion model. Ours is classical.
2. It does not deliver "significant improvement" — 1.07× is a wash, and we say so.

**Honest limitation already documented:** IO-VNBD contains no pseudoranges, so a
genuinely *tightly*-coupled fusion is not possible on this dataset.

**What to say:** *"This is the part of the problem statement where we're weakest,
and we'd rather tell you than have you find it. Our GNSS+INS fusion is a
classical loosely-coupled EKF and it measures 1.07× — a wash. Two reasons: the
dataset has no pseudoranges, so we can't do true tight coupling; and we chose to
spend our time on the GNSS-outage case, which is where the benchmark actually
bites. An AI-based fusion gain — a learned trust schedule between AI-speed, gyro
and map — is documented as our next item, with the paper we'd build it from."*

**Highest-value technical work available before finals.** The backlog item
already exists in `cursor_induction_v2/RESEARCH_2025.md` §D2 (Neural-Augmented KF,
arXiv 2507.00654). If anything gets built after Friday, build this.

### 5. Seamless GNSS Deficit Handler ✅
> *"instant seamless transition… within milliseconds… and vice-versa"*

**Have:** **100 ms** measured GNSS→DR handover. Mode transition visible in the UI.
Meets "within milliseconds" (100 ms = 1 update at 10 Hz).

**Make sure the reverse direction (DR→GNSS reacquisition) is also demonstrated** —
the PS says "and vice-versa" explicitly, and it is easy to only show one way.

### 6. Real-time Navigation Interface ✅
> *"UI displaying a smooth, uninterrupted vehicle icon showing seamless navigation"*

**Have:** the app. **"Smooth" is the operative word** and is currently our weak
point — a 10 Hz position feeding a marker directly will look like it is
teleporting. See `03_APP_DESIGN_SPEC.md` §Marker interpolation: interpolate
between fixes and drive the marker at 60 fps. This is a small change with a large
perceived-quality effect, and it is *literally* a PS requirement.

---

## B. The performance benchmark — where we honestly stand

> **Dead reckoning:** *"restrict positional drift to less than 10% of total
> distance travelled"* — e.g. <5 m over 50 m in <1 min, **or** <100 m over 1 km at
> 60 km/h.

| | Free DR (baseline) | COAST | **PS target** |
|---|---:|---:|---:|
| Median drift | 27.58% | **16.77%** | **<10%** |
| Median position error | 252.66 m | **125.20 m** | — |
| Short-arm pass (<5 m / 50 m) | 17% | — | 100% |
| Tunnel-arm pass | 10% | — | 100% |

**We do not meet the 10% bar.** We roughly halve the gap to it (27.6% → 16.8%),
and 2.02× lower median position error. **State this plainly and first.** A judge
who discovers it themselves scores us far lower than one we tell.

**The framing that is both honest and strong:**
> *"The benchmark is under 10% drift. Free dead reckoning on a phone is at 27.6%.
> We're at 16.8% — we've closed a bit over half the gap, and 2.02× on median
> position error. We are not there yet, and we know exactly what's missing:
> map-in-loop kills sideways error, but not how far along the road you are.
> That's the remaining error, and it's the same limitation the rail industry
> solves with trackside beacons."*

> **GNSS+INS Fusion:** *"10 Hz on smartphones, ~200 Hz on edge with FOG IMU"*

✅ **Met and exceeded.** 10 Hz on phone; edge engine measured **120,305 Hz**
(8.3 µs/sample) against a 200 Hz requirement — 600× headroom.

---

## C. Sensor coverage — one item needs a decision

The PS states the app *"should receive live inputs from the phone's built-in
IMU — the accelerometer, gyroscope, **and magnetometer/compass** and GNSS data if
available."*

| Sensor | Detected | Captured | **Used in the estimate** |
|---|---|---|---|
| Accelerometer (+uncalibrated) | ✅ | ✅ | ✅ |
| Gyroscope (+uncalibrated) | ✅ | ✅ | ✅ |
| **Magnetometer (+uncalibrated)** | ✅ | ✅ | **❌ NO** |
| Barometer | ✅ | ✅ | 🟡 floor-change detector only |
| GNSS | ✅ | ✅ | ✅ |

`sensor/SensorHub.kt` registers the magnetometer (preferring
`TYPE_MAGNETIC_FIELD_UNCALIBRATED`). But `nav/SimpleIns.kt` states in its own
header: *"integrate gyro yaw-rate + speed, **no magnetometer**."*

**So we capture it and do not use it. A judge reading the PS will ask about this.**

**This is defensible — but only if we say it deliberately, with a reason.** The
engineering case is genuine and well known: a magnetometer inside a steel vehicle
cabin, near speakers, wiring, and phone-mount magnets, is badly disturbed;
hard/soft-iron distortion in a vehicle routinely produces tens of degrees of
heading error, which is worse than the gyro drift it would be correcting.

**Recommended action — choose one, in priority order:**

1. **Best (a few hours):** run a measurement. IO-VNBD smartphone logs include
   magnetometer channels — compare mag-derived heading against CAN/GNSS-derived
   heading and report the error distribution. Then we can say *"we measured it: in-
   vehicle magnetic heading error was X degrees, which is why we don't use it."*
   **That converts a compliance gap into another measured negative result — the
   kind of thing that has already worked well for us.**
2. **Acceptable (30 minutes):** write the design decision into
   `docs/` and the Q&A bank, citing the known physics, and **show the magnetometer
   live in Vehicle Check** labelled *"captured · not used in estimate (why)"*.
   Transparency without a measurement.
3. **Do not:** quietly leave it. It reads as either an oversight or a hidden gap.

**What to say either way:** *"We read it, we log it, and we deliberately don't
fuse it. A compass inside a steel cabin next to a magnetic phone mount is not a
compass. We'd rather have honest gyro drift the map can correct than confident
magnetic error it can't."*

---

## D. The one-page summary for the team

| PS requirement | Status |
|---|---|
| Alignment & calibration engine | 🟡 built; online alignment measured a wash; pitch/roll good, yaw open |
| AI speed & vibration filter | ✅ on-device ONNX; loses per-window, wins closed-loop — report both |
| Map-matching + NHC + kinematic constraints | ✅ **our strongest deliverable** — HMM + NHC + map-in-loop 2.02× |
| **AI-based GNSS+INS fusion** | ❌ **classical EKF, 1.07× wash — our biggest gap** |
| Seamless handover (both directions) | ✅ 100 ms — remember to demo DR→GNSS too |
| Real-time nav interface | ✅ built; **"smooth" needs marker interpolation** |
| DR drift <10% | ❌ **at 16.8%; baseline 27.6%; be first to say it** |
| 10 Hz phone / 200 Hz edge | ✅ exceeded — 120,305 Hz |
| Magnetometer as an input | ❌ captured, not used — **needs a stated reason, ideally measured** |
| Edge-deployable, not phone-only | ✅ shared C++ core → phone + headless edge daemon |
| Works with external (non-phone) IMU data | ✅ adapter pattern + edge engine |

**Three sentences for the leader to memorise:**
> *"We're strongest on map-matching — that's our 2.02×. We're weakest on AI-based
> GNSS+INS fusion, which is a classical EKF measuring a 1.07× wash, and we'll tell
> you that before you ask. And we're at 16.8% drift against a 10% bar — about half
> the gap closed, with a named reason for what's left."*
