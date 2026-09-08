# COAST — complete project state

**Written:** 9 Sep 2026. **Purpose:** hand-off. An agent or teammate reading only
this file should be able to pick the project up without re-deriving anything.

**Repo:** https://github.com/dhruva137/SIH-2026
**Problem statement:** SIH 2026 **26168**, ISRO / Department of Space —
"AI-ML based Intelligent Dead Reckoning system for seamless navigation".
**Deadline:** 30 September 2026 (verified live on sih.gov.in — *not* the 20th,
which several of our own older docs still say).

---

## 0. THE MOST IMPORTANT THING IN THIS FILE

**There are two divergent branches with overlapping, conflicting work, and
`main` has four unpushed commits.** Nothing is merged. Both branches
independently built a drive UI, a map view and vehicle profiles. Whoever picks
this up must resolve this *before* writing new Android code, or the work will be
lost or duplicated a third time.

```
                            56ec3a0  (origin/main — last common commit)
                           /        \
   cursor/coast-drive-ui-4649        main (LOCAL ONLY, 4 commits unpushed)
   3 commits, pushed                 4 commits, NOT pushed
   COAST UI + walking PDR            harness rebuild + map-in-loop + metro
```

---

## 1. What we are actually building, in one paragraph

A phone app that keeps telling you where you are **after GPS dies** — in a
tunnel, an underpass, a basement car park, an underground metro, or when GNSS is
jammed. It does this from the phone's own accelerometer and gyroscope alone, with
no internet and no extra hardware, and snaps the estimate onto a road/rail map so
the error cannot grow without bound. Product name: **COAST** ("when GPS dies, you
coast on sensors"). Already named and branded on both branches.

---

## 2. Branch map

### `main` (local, **4 commits UNPUSHED**, ahead of origin/main)

The **science and evidence** line. Everything measured lives here.

| Commit | What |
|---|---|
| `0871085` | Rebuilt the evidence harness; found the real ceiling of phone-only DR |
| `ca26230` | Architecture v2 — map inside the filter loop; app rebuilt for end users |
| `94c84a2` | Validated v2: map-in-loop beats free DR **2.02x**; reviewed teammate blueprint |
| `9645757` | Vehicle profiles (10 kinds) + zero-velocity updates + metro mode |

Key files added: `lab/stress/{audit_can_truth,run_heading_ablation,run_isro_benchmark,run_mapmatch_eval,run_mapfilter_eval,run_transition_latency,gyro_preprocess}.py`,
`lab/nav/{mapmatch,mapfilter}.py`, `maps/osm_extract.py` + a real 3 271 km OSM
graph, `core/cpp/apps/idr_edge.cpp`, `docs/{AUDIT_AND_PLAN,ARCHITECTURE_V2,BLUEPRINT_REVIEW}.md`,
Android `nav/{VehicleProfile,Zupt,MountCalibration,OnnxSpeedModel}.kt` and a
rebuilt UI.

### `cursor/coast-drive-ui-4649` (pushed, currently checked out)

The **product/UI** line, built in Cursor.

| Commit | What |
|---|---|
| `9dc5d57` | COAST ride UI, **walking PDR**, crash-safe HUD |
| `589abae` | POSIX Gradle wrapper fix so Linux unit tests run |
| `8bb4621` | Web console binds dual-stack so localhost preview works |

Key files: `android/.../nav/StepDetector.kt` (**Weinberg step-length pedestrian
dead reckoning — this is real and it works**), `ui/DriveScreen.kt`,
`ui/DriveMap.kt`, `test/SimpleInsTest.kt`, plus web `Landing/Console` and Tauri
config changes.

### Pull requests

**None.** `gh` CLI is not installed locally, but both branches exist on
`origin` and no PR has been opened for either. `origin/main` is still at the
old `56ec3a0`.

### CORRECTION TO AN EARLIER CLAIM

I previously told the user "walking PDR does not exist, the estimator only has a
vehicle accel-integrator." **That was wrong.** It was true of `main`, which is
what I was building APKs from, and false of the COAST branch, which has a proper
`StepDetector` using peak-trough detection and the Weinberg step-length model
`L = k(a_max - a_min)^(1/4)`. The walking demo is much better supported than I
said. The two branches simply never saw each other.

---

## 3. The benchmark, and where we actually stand

### What ISRO asks for

Two arms, joined by **OR**:
- **< 5 m drift over 50 m** of GNSS denial, completed in **< 1 minute**, or
- **< 100 m drift over 1 km at 60 km/h**, in tunnels / underground metro *or
  similar simulated environments where GNSS signals are unavailable*

Plus: 10 Hz on the phone, ~200 Hz on an edge engine fed by an external
FOG-grade IMU, in-vehicle alignment, map-matching + non-holonomic constraints,
and handover "within milliseconds" in both directions.

### What we measure today (all on real IO-VNBD data, against CAN ground truth)

| Thing | Number | Status |
|---|---|---|
| Free DR, short arm (50 m) | 70/403 pass = **17%** | baseline |
| Free DR, tunnel arm (60 s) | 33/328 pass = **10%** | baseline |
| Free DR given a **perfect** yaw sensor | still fails **55%** | the key negative result |
| Post-hoc map snapping | **0.98x** — hurts near-misses | rejected, measured |
| **Map-in-loop particle filter** | **2.02x**, pass 8→17 of 43 | **our architecture, validated** |
| Edge engine throughput | **120 305 Hz**, 8.3 µs/sample | requirement met 600x over |
| Handover, GNSS lost → DR | **100 ms** | requirement met |
| Handover, DR → GNSS regained | 0 ms w/ 444 m jump, or 11.5 s w/ 24 m | tradeoff, unsolved |
| Filter's confidence signal | correlates **−0.23** with error | **BROKEN** — do not display |
| Android app | 47 JVM tests pass, release+AAB build | **0 minutes on a real phone** |

### The one-line honest summary

We have **proven on real data** that the obvious approach (dead-reckon, then fix
it up) cannot meet the bar, and that putting the map inside the filter loop is
**2x better**. We have **not** proven anything on a physical phone.

---

## 4. Answers to the strategic questions

### "Is our blocker the phone sensors, or beating the benchmark on the laptop?"

**It is the benchmark, and the benchmark is a laptop problem.** This is the most
important strategic clarification in this document.

- **Screening (30 Sep)** is graded on preliminary AI models and position plots
  from IO-VNBD. That is 100% laptop work. No phone is involved at all.
- **The finals** need a working demo, which is where the phone matters.
- The science is *further along* than the product. We can improve benchmark
  numbers indefinitely on the laptop without ever touching a phone.

So: **the laptop proves the claim; the phone makes it believable.** They are
separable, and right now the phone side is the riskier one purely because
nothing has been run on hardware.

### "Can a live website read motion sensors? Do we really need an APK?"

**A website can, with real limits. Our current website does not.** Verified:
`web/` contains zero `DeviceMotionEvent` / `Geolocation` usage — it is a replay
and evidence console, not a live sensor app.

What a browser *can* do:

| | Browser (Chrome on Android) | Native APK |
|---|---|---|
| Read accel/gyro | Yes, `DeviceMotionEvent`, **HTTPS only** | Yes |
| Sample rate | capped ~60 Hz, throttled | `SENSOR_DELAY_FASTEST`, 200–500 Hz |
| Keeps running screen-off / backgrounded | **No** | Yes, foreground service |
| Uncalibrated raw sensors | No | Yes |
| Works fully offline | Yes if cached (PWA) | Yes |
| iOS | needs `requestPermission()` + user gesture | n/a |

**Verdict:** for a *2-minute walking demo held in the hand with the screen on*, a
web page is genuinely viable and would remove the sideload friction entirely. For
the actual product claim — a scooter rider's phone in a pocket, screen off,
logging for 20 minutes — the browser dies and the APK is mandatory.

**Recommendation: do both, and be explicit about why.** The web page is the
"anyone can try it right now, scan this QR" surface. The APK is the product. Say
that on stage; it is a strength, not a hedge.

### "I want Google Maps"

Push back on this, for three reasons that are all defensible in front of a judge:

1. **It contradicts our own verified privacy claim.** The app currently has
   **no INTERNET permission and zero network calls**. That is a real, checkable
   property and a good story. Adding Maps SDK throws it away.
2. **It needs live internet.** The venue wifi is unreliable — which is exactly
   why MapLibre was left disabled. A map that blanks on stage is worse than no
   map.
3. **It is not what Rapido/Uber actually do.** When those apps "still track you
   with GPS off", they are using Android's Fused Location Provider falling back
   to **Wi-Fi and cell-tower positioning** — network-based, 50–200 m accurate,
   and it does *not* work underground. What we do — true inertial DR, offline —
   is the *harder* thing. Framing ours as "like Uber" actively undersells it.

**Do this instead:** we already have a real OpenStreetMap road graph (139 078
nodes, 35 631 edges, 3 271 km) that is fully offline and free, and it is what
drives the 2.02x result. Rendering that as the map background gives the
"it looks like a maps app" feel with no API key, no bill, and no network. Most of
the work exists in `lab/`; it needs porting into the app.

### "Can we use other devices? I want minimal hardware."

Stay phone-only. That is the right call and it is also the PS's own framing —
it explicitly contrasts "modern high-end cars with factory-fitted INS" against
"the vast majority of vehicles ... rely solely on the driver's smartphone."
Zero-extra-hardware **is** the product thesis. Adding a device would weaken the
pitch, not strengthen it.

The one free "extra sensor" worth considering is the **barometer** (present on
the M33) for detecting floor changes in multi-level car parks — the PS names
that environment specifically. No cost, no hardware, already in the log schema.

### "Where is this actually used?"

Useful for the pitch, and it explains why *ISRO* cares rather than a maps company:

- **Spacecraft and launch vehicles** — inertial navigation is the fallback when
  star trackers or ground links are unavailable. This is ISRO's home turf.
- **NavIC strategic context** — the PS explicitly names jamming and
  "unintentional electromagnetic interference". GNSS-denied navigation is a
  sovereignty issue, not a convenience feature.
- **Submarines** — the classic case: no GNSS underwater, months on pure INS.
- **Aviation, missiles, guided munitions** — INS is standard.
- **Underground mining, firefighters, soldiers indoors** — pedestrian INS.
- **The PS's own stated use cases** — logistics, ride-hailing, quick commerce,
  ambulances.

The honest framing: *the same mathematics ISRO uses on launch vehicles, running
on a ₹15 000 phone in a delivery rider's pocket.*

---

## 5. What an ideal winning finals submission looks like

Judges score novelty, complexity, feasibility, practicability, user experience,
scale of impact — and, at the internal round, **whether you can defend any line
of code they point at**.

1. **A demo a tired stranger can run in 60 seconds**, with a result they can
   verify with their own eyes. Loop closure is the killer format: walk out of the
   room, around, back to the same floor tile, and the app says how far off it
   thinks it is. No infrastructure, unfakeable, instantly legible.
2. **One number that is unambiguously ours.** Right now that is
   **2.02x over free dead-reckoning, measured on 43 outages against CAN ground
   truth.**
3. **A negative result, volunteered.** "A perfect gyro still fails 55% of
   segments — that is why we put the map in the loop." Nobody else will bring
   this, and it is the single strongest signal that the work is real.
4. **The bug story.** We found a unit error in our own pipeline that had been
   inflating every drift figure by 3.6x. You can only find that by understanding
   the physics and the data. It is the best possible answer to "did you actually
   build this?"
5. **Working edge engine.** 200 Hz requirement met 600x over. Most teams will
   skip this deliverable entirely because it is buried in the PS text.

### Novelty we can actually defend

- Road-constrained state vector: position is *on the graph*, so lateral error
  cannot grow — non-holonomic constraint as a property of the state space rather
  than a soft penalty a bad covariance can override.
- The measured heading ceiling (perfect gyro still fails) — as far as we can
  find, nobody has characterised IO-VNBD's smartphone logs this way.
- Lean-aware two-wheeler handling (the PS names two-wheelers; the literature is
  all cars).
- Branch-decision accuracy as a user-facing metric instead of drift %.

### What NOT to claim

First phone INS. Beating Qian 2025. Discovering roll/yaw kinematics (textbook).
Map-matching (Newson & Krumm 2009 — we cite it). Any drift-reduction number for
ZUPT, which is **not yet measured end-to-end**.

---

## 6. Demo design, from a human point of view

The user's instinct here is right: *"run track 1, track 2" on a website means
nothing to a judge.* Nobody understands a replay. They understand a thing that
moves when they move.

**Act 1 — the handoff (60 s, the whole pitch).** Judge holds the phone. Walk
together out of the room. Turn location off in front of them. Keep walking. The
dot keeps moving. Return to a marked spot on the floor. Screen shows closure
error in metres. *This is the entire demo; everything else is supporting
material.*

**Act 2 — the scooter (if a bike is available).** Phone in a handlebar mount,
same app, `scooter` profile. Shows the lean-aware path.

**Act 3 — the benchmark (laptop, 60 s).** Only now show the IO-VNBD replay,
framed as "here is the same estimator scored against a car's own CAN bus on
23 real drives" — with the 2.02x table. This is evidence, not spectacle, and it
lands *after* they already believe the thing works.

**Act 4 — the ask.** 200 M two-wheelers, any phone, zero extra hardware.

Keep a **pre-recorded video** of Act 1 (the internal-round rules explicitly allow
falling back to it if the live demo fails).

---

## 7. To-do, in priority order

### Blocking / this week

1. **Merge the two branches.** Nothing else should be built on Android until
   this is resolved. Both branches have `DriveScreen.kt`, `DriveMap.kt` and
   `VehicleProfile.kt` written independently — this will conflict. Decide per
   file which version wins; the COAST `StepDetector` is a keeper.
2. **Push `main`.** Four commits of measured evidence exist only on this laptop.
   One disk failure loses all of it.
3. **Run the app on a physical phone.** Walking, location off, 2 minutes. This
   is the single largest unknown in the project and it costs one afternoon.

### High value

4. Fix the confidence signal (−0.23 correlation) before it is ever shown in the
   UI as a confidence radius.
5. Port the OSM map into the app as the visual background — this is the real
   answer to "I want Google Maps", offline and free.
6. Build the web (PWA) walking demo using `DeviceMotionEvent`, as the
   zero-friction "try it yourself" surface.
7. Retrain the speed model on CAN labels (it was trained on 3.6x-wrong units).
8. Field data collection: ≥10 scooter/bicycle logs with loop closure.

### Before the finals

9. PPT in the official SIH template + pre-recorded demo video.
10. Assign codebase ownership per teammate and rehearse hostile Q&A.
11. Alignment engine (branch accuracy currently 26%).

---

## 8. Where to look for what

| Question | File |
|---|---|
| What was wrong with our old numbers | `docs/AUDIT_AND_PLAN.md` |
| Why the architecture is what it is | `docs/ARCHITECTURE_V2.md` |
| Review of the teammate's ESKF proposal | `docs/BLUEPRINT_REVIEW.md` |
| Benchmark results, both arms | `lab/stress/results/isro_benchmark/summary.md` |
| The heading ceiling experiment | `lab/stress/results/heading_ablation/summary.md` |
| Map-in-loop validation | `lab/stress/results/mapfilter/summary.md` |
| Edge engine CLI + measured throughput | `core/cpp/apps/README.md` |
| Android build, permissions, release | `android/README.md` |
| Hostile Q&A prep | `docs/JUDGE_CROSS_EXAM.md` |
