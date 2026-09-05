# Review of the AI-ESKF blueprint

A teammate circulated a technical blueprint proposing an AI-Aided Error-State
Kalman Filter with a TCN velocity/covariance head, NHC, and HMM map matching.
This is a review of it against (a) the IO-VNBD paper's own documentation and
(b) our measurements on the real data.

**Overall: the architecture is sound and it is what the problem statement asks
for. Three factual claims are wrong, and one design stage is something we have
already measured as not working.** Fix those and the blueprint is strong.

---

## Verified CORRECT — keep these

### Column 16 is Indicated Vehicle Speed (km/hr)

Confirmed directly from the header of `V-S1.csv`:

```
15  Yaw Rate (deg/sec)
16  Indicated Vehicle Speed (km/hr)
17  Indicated Longitudinal Acceleration (g)
```

This is exactly the training label we are using (`load_iovnbd.load_vehicle_csv`
reads it at 0-based index 15 and divides by 3.6).

### The tyre-pressure and mud scenarios are real

Confirmed in `README_1.pdf` (the Data-in-Brief paper): scenario 20 is "Mud
Road", scenario 21 is "Varying Tyre Pressure", and Table 5 enumerates the
pressures used. Sequences such as `V-Vta1a` are annotated "Brake on wet road,
Tyre Pressure A / Hard Brakes on Mud, Wet Road, Country Road".

**This is a genuinely good pitch angle and we should use it.** A static filter
tuned on smooth motorway suspension harmonics has no reason to survive an
asymmetrically deflated tyre; a covariance head trained across pressures does.
It is a clean, physically motivated demonstration of why the AI is doing real
work rather than decorating a Kalman filter.

### The Brossard 1.0 s window, and adapting it to 2.0 s at 10 Hz

Plausible and, more importantly, defensible. If a judge asks why 2 seconds:
Brossard uses 100 timesteps at 100 Hz, i.e. 1.0 s of context; at 10 Hz that
same 1.0 s gives only 10 samples, which is too sparse for a dilated convolution
stack to characterise a noise spectrum, so we doubled the window to recover
sequence length at the cost of some latency. That is a real engineering
trade-off honestly described.

### The caution on the ">30% improvement" figure

Correct, and the teammate already flagged it. Do not put a number in the deck
that we have not measured. See "What we actually measured" below for numbers
that are real.

---

## Verified WRONG — fix before this goes in the deck

### 1. The ground truth is NOT 100 Hz. Both streams are 10 Hz.

The blueprint calls this "The Dataset Trap" and prescribes interpolating the
smartphone data up to 100 Hz. That premise is false, and acting on it would
manufacture fake precision.

Two independent confirmations:

**From the paper.** "Racelogic VBOX Video HD2 CAN-Bus data logger (10Hz)",
"Racelogic VBOX Video HD2 GPS Antenna (10Hz)", and explicitly: the CAN bus data
was recorded "with a sampling and update frequency of 10Hz". The smartphone is
separately documented at 10 Hz.

**From the data.** `S-S1.csv` and `V-S1.csv` both have **51 746 rows**, and the
median timestep in both is **0.1000 s = 10.0 Hz**.

There is nothing to upsample. Interpolating 10 Hz to 100 Hz does not add
information; it adds 90% invented samples that a network will happily overfit,
and it inflates every count-based statistic by 10x.

### 2. The synchronisation problem is smaller than described

The blueprint prescribes cross-correlation clock-drift alignment with Slerp on
the ground-truth quaternions. For the **Synchronised** release this is
unnecessary: the files are already row-aligned. We verified on six drives —
identical row counts, mean speeds agreeing to ~1%, start positions agreeing to
2-13 m, and a cross-correlation lag scan putting best lag at 0 to +-0.5 s.

Keep a lag check as a **validation assert** — it is cheap and it caught nothing,
which is itself worth stating. Do not build a correction pipeline for a problem
the dataset does not have. (The *Unsynchronised* release is a different matter,
but we are not using it.)

### 3. Naive double integration is the wrong villain

The blueprint's Slide 2 is "plot O(t^2) error accumulation from double
integrating acceleration". True, but it attacks a strawman nobody builds, and it
is not our binding constraint.

We measured the real one. Holding **speed** fixed (so no double integration
happens at all) and varying only heading, across 23 drives and 186 forced 60 s
outages scored against CAN truth:

| heading source | median error | PASS_ISRO |
|---|---:|---:|
| raw phone gyro | 321.6 m | 32/186 |
| + causal low-pass | 341.8 m | 29/186 |
| + oracle 3-axis mount + filter | 205.2 m | 42/186 |
| **the car's own CAN yaw rate** | **87.6 m** | **84/186** |

**Even a perfect yaw sensor fails 55% of segments.** The enemy is heading, not
position double-integration. That is a much stronger slide, because it says the
obvious fix does not work and we know it because we measured it.

---

## The design stage that does not work as written

### Stage 3, "HMM overrides it and snaps the position back"

We built exactly this — Newson & Krumm HMM over a real 3 271 km OpenStreetMap
graph — and measured it on 37 forced outages:

| | median error | PASS_ISRO |
|---|---:|---:|
| free DR | 498.9 m | 3/37 |
| post-hoc HMM snap | 507.7 m | 4/37 |

**0.98x.** And broken down by how bad the input was:

| free-DR error | median free | median map | ratio |
|---|---:|---:|---:|
| 0-50 m | 37.9 | 88.3 | **2.33** |
| 50-100 m | 58.2 | 151.0 | **2.59** |
| >500 m | 1290.8 | 1231.5 | 0.95 |

Snapping **actively hurts the cases that were nearly right**. Once the track is
hundreds of metres out, the matcher confidently snaps onto whichever road lies
underneath, and a confidently wrong road is worse than an honest drift.

**The fix is to put the map inside the filter loop rather than after it.** We
built that too — a road-constrained particle filter whose state is
`(edge, distance along edge, direction, speed_scale)` instead of `(x, y, heading)`.
Position is derived from the graph, so cross-track error is bounded by road
width *structurally*. Measured on 43 outages:

| | median error | PASS_ISRO |
|---|---:|---:|
| free DR | 252.7 m | 8/43 |
| **map-in-loop PF** | **125.2 m** | **17/43** |

**2.02x, pass count doubled.** That is the architecture the deck should show.
The blueprint's Stages 1 and 2 (alignment, TCN velocity + dynamic covariance)
slot in front of it unchanged and are still worth building.

---

## Answers to the four judge questions, with our real numbers

**"How are you handling the measurement noise covariance matrix?"**
Two answers, and be honest about which is built. The designed answer is the
blueprint's: a TCN head emitting per-axis variance, trained with an NLL loss so
the network is penalised for being confidently wrong. The measured answer today
is that our filter's own uncertainty is **not yet trustworthy** — posterior
spread correlates with actual error at **-0.23**, i.e. slightly *anti*-correlated.
We know this because we wrote the test before running it, and we are not showing
a confidence radius to a user until it is positive. Saying that out loud is
stronger than claiming calibrated uncertainty we do not have.

**"What sequence length did you use?"**
2.0 s = 20 samples at 10 Hz, adapted from Brossard's 1.0 s / 100 samples at
100 Hz, because 10 samples is too sparse to characterise a noise spectrum. Note
the aliasing caveat: at 10 Hz everything above 5 Hz is already folded into the
passband before we see it, so on a phone we control we sample fast and decimate
with an anti-alias filter rather than sampling at 10 Hz directly.

**"How did you sync the smartphone data with the ground truth?"**
We did not have to — the Synchronised release is row-aligned, and we verified
that rather than assuming it (identical row counts, speeds within 1%, positions
within 2-13 m, cross-correlation lag 0 to +-0.5 s). We do assert it on load.

**"How are you stopping the car from sliding sideways?"**
In the blueprint's stack, NHC as a pseudo-measurement with AI-scaled covariance.
In what we actually built, something stronger: the state vector has no lateral
degree of freedom at all. A particle is a position *along a road*, so sideways
motion is not penalised, it is unrepresentable. NHC then becomes a property of
the state space rather than a soft constraint that a badly tuned covariance can
override.

---

## What to do with the blueprint

Keep: Stage 1 alignment, Stage 2 TCN with dynamic covariance and NLL loss, the
tyre-pressure/mud generalisation test, the ONNX latency slide, and the
partitioning discipline (train on motorways, test on mud — that is exactly the
right instinct).

Change: drop the 100 Hz interpolation, drop the clock-drift correction pipeline,
replace the "double integration" villain with the measured heading result, and
move the map from post-processing into the filter loop.

The honest framing that ties it together: *we built the obvious architecture,
measured where it fails, and the failures are why the final design looks the way
it does.*
