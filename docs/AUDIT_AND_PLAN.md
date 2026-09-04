# SIH 26168 — independent audit and the plan to win

**Audited:** 4 Sep 2026. **Reproduce:** `python lab/stress/audit_can_truth.py`
**Evidence:** `lab/stress/results/can_truth/report.json`

This document supersedes the "everything is honestly RED" reading in
[`PROGRESS.md`](../PROGRESS.md). The RED gates were real, but three of the four
causes are **defects in the evaluation harness**, not physics. They are fixable
this week.

---

## Part 1 — the official problem statement, re-verified

Pulled live from the portal (`sih.gov.in/sih2026PS`, PS ID 26168) on 4 Sep 2026.
Third-party PS catalogues are scraped stubs and get the theme wrong; use the
portal.

| Field | Portal value | What the repo said | Action |
|---|---|---|---|
| Deadline | **30 September 2026** | 20 September | **+10 days of runway.** Update the bible and sprint plan. |
| Theme | Smart Vehicles | Smart Vehicles | correct |
| Submissions | **0/500** as of 4 Sep | "monitor daily" | uncontested so far; keep watching |
| Dataset | IO-VNBD, github.com/onyekpeu/IO-VNBD | same | correct |

### Requirements the repo is not currently building against

The bible's §1.1 summary is faithful but lossy. These clauses are in the
official text and are **graded deliverables**, not nice-to-haves:

1. **"an Edge deployable software engine"** — a second, separate deliverable
   alongside the mobile app. It must run on **external IMU data, not just phone
   IMU**, and hit **~200 Hz** with FOG-grade IMU input. The repo has no 200 Hz
   path and no external-IMU ingestion. `core/cpp` is the natural home; it is
   currently unbuilt as a product.
2. **"In-Vehicle Alignment & Calibration Engine"** — automatic pitch/roll/yaw of
   the phone relative to the driving direction, dashboard-mounted *or* loose in
   a holder. The repo hardcodes one mount contract (`gz = -GYROSCOPE Pitch`).
   See Finding 2 — this is exactly the module that is missing.
3. **"GNSS+INS Fusion Engine"** — an AI fusion model for the period when GNSS
   **is** available. The repo only measures the outage. Half the graded system
   is unmeasured.
4. **"Seamless GNSS Deficit Handler ... within milliseconds"** in **both**
   directions. There is no transition-latency metric anywhere in `lab/`.
5. **Magnetometer/compass** is named as a live finale input. The bible writes it
   off in §10.6. IO-VNBD ships `MAGNETIC FIELD X/Y/Z`; it is unread by the loader.
6. **Map-matching is requested, by name** — "Unscented Kalman Filter + Hidden
   Markov Map Matching" over OpenStreetMap. The repo's caution about not
   *claiming* map-matching as novelty is right, but it must still be **shipped**:
   it is a required bullet. Current `map_aid.py` snaps to a polyline built from
   the evaluated drive's own GNSS, which is not a map.
7. **The benchmark has two arms, joined by OR:**
   - `< 5 m drift over 50 m of GNSS denial in < 1 minute`, **or**
   - `< 100 m over 1 km at 60 km/h`.
   Every gate in `lab/stress/` scores only the second arm. The first arm is
   easier, equally official, and is the one you can demo live in a college
   corridor. **Add it as a first-class gate.**
8. **"During the screening process more datasets will be provided"** — the
   ingestion path must be format-tolerant. Today `load_iovnbd.py` hardcodes
   IO-VNBD header aliases.

---

## Part 2 — four defects found in the evidence pipeline

IO-VNBD's synchronised release ships **row-aligned pairs**: `S-S1.csv` (phone,
51,746 rows) and `V-S1.csv` (the same drive from the car, 51,746 rows). `V`
carries CAN yaw rate, indicated vehicle speed, four wheel speeds, steering
angle and a **10 Hz** GPS fix. It is an independent oracle for everything the
phone file leaves ambiguous.

**The repo never opens a single `V-*.csv`.** `grep -rn "V-S1\|Yaw Rate\|Wheel Speed" lab/` returns nothing.

### Finding 1 — the speed column is m/s, and the loader divides it by 3.6

`load_iovnbd.py` reads the header `GPS SPEED (Kmh)` and applies `/3.6`. The
header is wrong. Against CAN indicated speed on S-S1:

```
speed column / CAN true speed = 0.945    -> the column is already m/s
```

Cross-checked geometrically: the S-S1 GPS polyline is 37,029 m long;
`sum(col x dt)` = 37,824 m; `sum(col/3.6 x dt)` = 10,507 m.

Consequences, all of which flow into every number in `PROGRESS.md`:

- dead-reckoned distance is 3.6x too short, so along-track error is huge;
- the `distance_m` denominator is 3.6x too small, so **every reported drift %
  is inflated by ~3.6x**;
- `solve_lean` gates on `v < 0.4` and computes `phi = atan2(v*psidot, g)` — at
  3.6x-low speed the lean estimate is wrong by construction, so the F5 solver
  has never actually been evaluated;
- `train_avnet.py` regresses speed against 3.6x-low labels.

The guard `if max(speed) > 80: /3.6` never fires because these drives peak at
21.7 m/s.

**Fix:** delete the `/3.6` for IO-VNBD S-files; replace the header-string
heuristic with a physical check — compare `sum(v*dt)` against GPS path length
and reject any factor outside `[0.8, 1.25]`.

### Finding 2 — the mount is hardcoded, and it is ~24 degrees off

Against CAN yaw rate at full 10 Hz on S-S1:

| channel | corr | gain |
|---|---:|---:|
| `gyro_yaw` | +0.055 | +0.061 |
| **`gyro_pitch`** | **+0.908** | **+0.856** |
| `gyro_roll` | -0.280 | -0.616 |

The repo's axis choice and **sign are correct** (flipping the sign makes the
replay worse — config C below). But the best fixed mount vector is

```
yaw_rate = 0.029*gyro_yaw + 0.944*gyro_pitch + 0.431*gyro_roll     |w| = 1.038
corr 0.924, residual 2.72 deg/s against a true 7.14 deg/s signal
```

so the true rotation axis sits about 24 degrees away from the pitch axis, and
`-gyro_pitch` alone under-reads by ~15%. That is a per-mount constant, and it is
precisely what the PS's **In-Vehicle Alignment & Calibration Engine** is for.
Hardcoding it means the system cannot survive a different phone or holder — the
finale runs on *your* phone in *your* mount, which is neither of these.

### Finding 3 — ground truth is a 0.1 Hz staircase interpolated to 10 Hz

The phone file holds each GPS fix for ~9 s: **498 unique positions in 51,746
rows**. `outage_replay._interp_lla` linearly interpolates that staircase and
scores against it. The paired `V-S1.csv` has **40,684 unique fixes** over the
same drive — real 10 Hz truth.

Scoring a 60 s outage against a polyline whose vertices are 90 m apart injects
tens of metres of fabricated error and cannot resolve a turn at all.

**Fix:** ground truth comes from `V-*.csv` lat/lon wherever a pair exists.

### Finding 4 — 99% of IO-VNBD is unpulled LFS stubs

```
find data/raw/IO-VNBD -name '*.csv' -printf '%s\n' | awk '{if($1<1000)a++;else c++}END{print a,c}'
-> 559 stubs (130-133 bytes), 5 real
```

Only `S-S1`, `S-S2`, `S-S4`, `S-M` and `V-S1` are real out of **564 CSVs**.
That is 0.9% of the official dataset. The whole `Vf`, `Vta`,
`Vtb`, `Vw`, `Y`, `St` families — motorway, roundabout, traffic, wet-road
categories, i.e. **all the actual road-speed driving** — are pointers. The
lab has been drawing conclusions from four low-speed suburban files, one of
which (`S-M`) contains segments at 0 m/s that the gate then reports as
972% drift.

The bible's own §2.9 warning ("verify a CSV is >1 MB") was written and then not
enforced across the corpus.

**Fix:** `cd data/raw/IO-VNBD && git lfs install && git lfs pull`, then fail the
harness loudly if fewer than N real files are present.

**Status: done.** All 564 CSVs are now real, 0 stubs. `find_smartphone_csvs()`
returns 24 unique drives (it now de-duplicates the Synchronised and
Unsynchronised copies of each drive, preferring the synchronised one so CAN
truth is available), and 23 of them have a paired `V-*.csv`.

### Finding 5 — the speed-unit bug is universal, and the fix is confirmed

The `resolve_speed_unit` replacement decides the unit geometrically instead of
trusting the header. Across all 25 audited pairs the column integrates to
between **0.81x and 1.00x** the CAN indicated speed. Every drive is m/s. The
`(Kmh)` header is wrong everywhere, not just on S-S1.

### Finding 6 — the gyro is vibration-dominated on the fast drives

Correlating each gyro channel against CAN yaw rate over speed > 4 m/s samples:

| drive | mean v | gyro std | CAN yaw std | corr raw | corr 0.25 Hz LP | 3-axis @ 0.5 Hz |
|---|---:|---:|---:|---:|---:|---:|
| S-S1 | 9.4 | 0.132 | 0.125 | +0.908 | +0.976 | +0.979 |
| S-S3c | 13.7 | 0.115 | 0.115 | +0.947 | +0.954 | +0.956 |
| S-Vta2 | 11.4 | 0.326 | 0.085 | +0.206 | +0.755 | +0.828 |
| S-Vw4 | 18.9 | 0.349 | 0.095 | +0.244 | +0.601 | +0.869 |
| S-Vtb1 | 14.8 | 0.320 | 0.073 | +0.127 | +0.276 | +0.477 |
| S-Vtb5 | 18.4 | 0.253 | 0.046 | -0.010 | -0.025 | +0.034 |
| S-Vfa02 | 24.9 | 0.242 | 0.042 | +0.010 | +0.041 | +0.041 |

Where the phone's gyro standard deviation runs several times the vehicle's
actual yaw rate, the raw channel carries almost no heading information. That is
the motorway regime — precisely the regime the ISRO tunnel benchmark targets.
Finding F7 already measured the frequency separation that makes this
addressable; the pipeline simply never applied a filter.

Two cautions that matter for how this is reported:

- **Low correlation on a motorway can be benign.** On S-Vtb5 and S-Vfa02 the
  CAN yaw std is only ~0.043 rad/s: the car is going straight, so there is
  barely any signal to correlate against. Judge the heading path by integrated
  error, not correlation.
- **`filtfilt` is not deployable.** Zero-phase filtering reads future samples.
  `lab/stress/gyro_preprocess.py` provides both a causal filter (real-time
  legal, ~0.64 s group delay at the default cutoff) and a zero-phase one
  labelled as an offline ceiling. Quote the causal number.

### Finding 7 — a phone gyro cannot carry 60 s of heading, at any cutoff

`lab/stress/run_heading_ablation.py` ablates the heading path with speed held
at the phone's own GNSS speed so that only heading varies, scored against the
paired CAN trajectory. **23 drives, 186 forced 60 s outages at road speed:**

| config | what it is | median error | median drift % | PASS_ISRO |
|---|---|---:|---:|---:|
| A | raw `-gyro_pitch` (shipped contract) | 321.6 m | 40.2 | 32/186 |
| B | + 0.5 Hz causal low pass | 341.8 m | 37.8 | 29/186 |
| C | + CAN-fitted 3-axis mount *(oracle)* | 233.7 m | 30.8 | 37/186 |
| **D** | **+ mount and low pass** *(oracle)* | **205.2 m** | **24.7** | **42/186** |
| E | + stationary bias removal *(oracle)* | 207.5 m | 26.2 | 41/186 |
| **F** | **CAN yaw rate directly** *(ceiling)* | **87.6 m** | **12.4** | **84/186** |

Four load-bearing conclusions:

1. **Filtering alone does not help.** B is *worse* than A on median error
   despite transforming correlation (Finding 6). Integrated heading error is
   dominated by the slowly-varying component a low pass passes straight
   through. Correlation was the wrong objective all along.
2. **Mount and filter pay off only together** (A to D: 1.57x on error, and
   pass count 32 to 42). That is why one hardcoded axis survives on the quiet
   urban drives and collapses elsewhere.
3. **Bias removal makes it worse.** The stationary gyro estimate is too noisy
   to help. Do not ship it without rethinking the estimator.
4. **The decisive one: even a perfect gyro passes only 84 of 186 segments.**
   Row F substitutes the car's own CAN yaw rate — a sensor a phone will never
   have — and still fails 55% of road-speed 60 s outages at 12.4% median drift.

> **Free-inertial dead reckoning on a smartphone cannot meet the ISRO 60 s
> tunnel benchmark, even given a perfect yaw sensor.** Measured across 23
> drives and 186 outages against independent CAN ground truth.

That is the strongest and most defensible statement in the submission. It is
measured rather than argued from simulation, and no published work
characterises IO-VNBD's smartphone logs this way.

### Finding 8 — post-hoc map matching does NOT rescue a drifted track

The obvious next move — dead-reckon freely, then snap the result to the road
network — was built and measured, and it fails.
`lab/stress/run_mapmatch_eval.py` runs Hidden Markov map matching (Newson &
Krumm 2009) over a real OpenStreetMap graph built by `maps/osm_extract.py`
(35 631 edges, 3 271 km, `built_from_drive_data: false`, asserted before
scoring). 8 drives inside the graph bbox, 37 forced 60 s outages:

| | median error | median drift % | PASS_ISRO |
|---|---:|---:|---:|
| Free DR | 498.9 m | 45.4 | 3/37 |
| Map-aided | 507.7 m | 45.4 | 4/37 |

**0.98x. Helped 20, hurt 16.** And the breakdown by error magnitude is the
part that matters:

| free-DR error | n | median free | median map | ratio |
|---|---:|---:|---:|---:|
| 0-50 m | 1 | 37.9 | 88.3 | **2.33** |
| 50-100 m | 1 | 58.2 | 151.0 | **2.59** |
| 100-200 m | 8 | 145.2 | 181.6 | 1.25 |
| 200-500 m | 9 | 301.7 | 307.5 | 1.02 |
| >500 m | 18 | 1290.8 | 1231.5 | 0.95 |

Map matching **actively hurts** the cases that were nearly good, and does
nothing for the cases that were already lost. Once the track is hundreds of
metres out, the matcher confidently snaps it onto whichever road happens to
lie underneath, which is the wrong road — and a confidently wrong road is
worse than an honest drift.

One tuning error of mine was found and corrected along the way. Growing the
emission sigma over the outage seemed principled, since uncertainty genuinely
does grow, but it weakens the constraint that makes matching work. Measured on
16 segments with free-DR error under 400 m: growing 15 m + 1.5 m/s gave ratio
1.21; fixed 30 m gave 0.96. The default is now fixed. It changed the headline
by ~4% — the conclusion is not a tuning artefact.

**Architectural consequence.** The map cannot be a post-processor. It has to be
*inside* the filter loop, constraining every step so that error never grows past
road spacing in the first place. That is exactly what the problem statement
asks for when it names "Unscented Kalman Filter + Hidden Markov Map Matching" —
a filter, not a cleanup pass. Building that tightly-coupled estimator is the
single highest-value remaining task, and Findings 7 and 8 together are the
evidence for why it is the only path that can work.

The honest framing for the submission: *"we measured the ceiling of the obvious
approach, found it insufficient, measured the obvious fix, found it
insufficient too, and that is why the estimator is built the way it is."*

---

## Part 3 — what the numbers actually are once you fix the harness

Forced 60 s GNSS denial, 8 segments on S-S1, scored against `V-S1` 10 Hz GPS.
Reproduce with `python lab/stress/audit_can_truth.py`.

| config | median error | drift % | m/km | PASS_ISRO |
|---|---:|---:|---:|---:|
| A — repo contract (`-pitch`, `v/3.6`) | 242.5 m | 56.8 | 567.7 | 0/8 |
| B — speed unit fixed | 129.8 m | 23.5 | 235.4 | 0/8 |
| C — sign flipped (control) | 435.5 m | 78.0 | 780.4 | 1/8 |
| D — least-squares mount vector | 138.7 m | 22.5 | 225.2 | 0/8 |
| **E — oracle CAN yaw + CAN speed** | **44.0 m** | **10.5** | **104.6** | **4/8** |

Read this carefully, because it changes the strategy:

- Fixing one line of unit handling **halves the error** (56.8% to 23.5%).
- The mount vector buys a further ~1 point. Small here because this drive's
  mount happens to be close to the pitch axis; on a different mount it is the
  difference between working and not.
- **Row E is the ceiling.** With a *perfect* yaw rate and a *perfect* speed, this
  architecture still only reaches 10.5% median drift and passes 4 of 8. So no
  amount of AVNet speed regression or lean solving gets you to the bar on its
  own.

The binding constraint after the fixes is **heading**, exactly as finding F8
predicted — but the residual is now in the *initial heading seed* and in
unmodelled slow heading error, not in the gyro. And the only thing that kills
accumulated heading error is the map (F9: 10 degrees of heading error, 93.4 m
raw, 0.7 m after projection).

**That is the winning path, and the PS asks for it by name:** real OSM +
Hidden-Markov map matching. Not the current `map_aid.py`, which snaps to the
evaluated drive's own GNSS polyline and is therefore not evidence.

---

## Part 4 — the plan

Ordered by (points on the rubric) / (hours). Each item names its acceptance test.

### This week — recover the evidence base

| # | Change | Where | Done when |
|---|---|---|---|
| 1 | Drop the `/3.6`; replace with a physical unit check against GPS path length | `lab/stress/load_iovnbd.py` | `audit_can_truth.py` reports `col_over_true` in `[0.8,1.25]` for every pair |
| 2 | `git lfs pull` the full corpus; harness aborts if < 20 real CSVs | `data/raw/IO-VNBD`, `load_iovnbd.find_smartphone_csvs` | `find ... -size +1M` returns the full IO-VNBD set |
| 3 | Ground truth from `V-*.csv` 10 Hz GPS when a pair exists; keep interpolated phone GPS only as a labelled fallback | `outage_replay._interp_lla` and callers | every scored row records which truth source it used |
| 4 | Re-run every gate. Rewrite `CURRENT_VERDICT.md` and `PROGRESS.md` from the new rows | `lab/stress/` | numbers in the repo match `audit_can_truth.py` |
| 5 | Add the **50 m / 60 s / 5 m** arm of the benchmark as a first-class gate | `lab/stress/product_gate.py` | gate reports both arms separately |

Item 4 matters for credibility as much as accuracy. Publishing "0 PASS, honest"
when the cause was a unit bug is the cross-examination you lose. Publishing
"we found our own bug, here is the before/after and the script that proves it"
is the one you win — it is a stronger novelty story than the lean solver.

### Next two weeks — build the modules the PS grades

| # | Module | Why | Acceptance |
|---|---|---|---|
| 6 | **Alignment & calibration engine.** Estimate the mount rotation online from a short GNSS-available window: regress `course_rate` on the gyro triple, and forward axis from accel during braking. Ship it, do not hardcode. | Named PS deliverable; Finding 2 | recovers `w` within 5 degrees on S-S1 using only pre-outage data, no CAN |
| 7 | **Real OSM + HMM map matching.** Newson & Krumm formulation over an offline OSM extract. Cite it, do not claim it. | Named PS deliverable; F9 says it is where the accuracy is | drift on the same 8 segments drops below 10% with a map the algorithm did not see the answer in |
| 8 | **Speed model retrained on CAN labels.** `V-*.csv` gives `Indicated Vehicle Speed` at 10 Hz — a far better label than 0.1 Hz GPS. This is literally the PS's "AI Speed & Vibration Filter". | Finding 4 + the PS bullet | held-out speed RMSE beats speed-hold on files excluded from training |
| 9 | **Transition-latency metric.** Time from GNSS loss to first DR fix, and from re-acquisition to converged fusion. | Named PS deliverable, currently unmeasured | reported in ms in `lab/eval/metrics.py` and shown on the app HUD |
| 10 | **GNSS+INS fusion path,** scored while GNSS is present, not only during denial. | Half the graded system | fused position beats raw GNSS on the degraded-accuracy rows |

### Before the finale — the second deliverable

| # | Item | Note |
|---|---|---|
| 11 | **Edge engine.** `core/cpp` built as a standalone binary that ingests a generic IMU CSV, no phone required, and sustains ~200 Hz. | The PS asks for this explicitly and separately. It is probably the single most-skipped requirement across competing teams. |
| 12 | Read `MAGNETIC FIELD X/Y/Z` and use it as a bounded heading prior with a distortion detector. | The PS names the magnetometer. "We tested it and it is unusable on a two-wheeler, here is the data" is a fine answer; "we never read the column" is not. |
| 13 | Generic CSV ingestion with a column-mapping config. | "More datasets will be provided during screening." |

### Positioning — one correction

The repo is positioned 100% on two-wheelers. The PS names two-wheelers
prominently, and that opening is genuinely good — but it also names commercial
trucks and older cars, and **IO-VNBD is entirely cars**. Lead with the general
engine, and present lean-awareness as the extension that the incumbent
literature cannot do. Do not stake the whole submission on a vehicle class for
which you currently have zero field logs.

---

## What did not change

These hold up and should stay:

- `gz = -GYROSCOPE Pitch` — the sign is right, confirmed against CAN.
- F8's error budget: heading dominates. The corrected numbers make it *more*
  true, not less.
- F9's map projection result. It is now the main line of attack.
- The dual prototype/deployment gate, and the refusal to sell a prototype pass
  as an ISRO pass. Keep that discipline; just make sure the RED you own is a
  real RED.
