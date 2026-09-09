# F2 — Technical Feasibility
*"Complexity, feasibility, and scalability"* · Round 1 · judged off the deck

---

## A. What this criterion actually rewards

Three distinct sub-scores, and teams routinely win one and lose the others:

- **Complexity** — is this hard enough to be worth doing? (Too simple scores low.)
- **Feasibility** — can it actually be built and deployed? (Too ambitious scores
  low. This is where over-claiming teams die.)
- **Scalability** — does it grow beyond the demo?

The trap: complexity and feasibility pull in opposite directions. A project that
sounds hard sounds infeasible; a project that sounds feasible sounds trivial.

**Our resolution:** show that the hard part is *already done and measured*, and
that the deployment path requires nothing that does not already exist. Complexity
is evidenced by measurements; feasibility is evidenced by the absence of any
required new hardware, licence, or infrastructure.

## B. Our position

### Complexity — evidenced, not asserted
- A particle filter over a road-graph state space, running in real time.
- A neural speed model (CNN-GRU) exported to ONNX and running **on the phone**.
- A shared C++ core that compiles to three targets: Android (JNI), web (WASM),
  and a headless edge daemon.
- Measured throughput: **120,305 Hz** on the edge engine — 8.3 µs/sample, 7.5 MB
  footprint, against a 200 Hz requirement. **600× headroom.**
  → `core/cpp/apps/README.md`

### Feasibility — the strongest card we hold
Enumerate what we need that does not already exist: **nothing.**

| Requirement | Status |
|---|---|
| Special hardware | None. Any smartphone with an IMU. |
| Map licence / API key / billing | None. OpenStreetMap via MapLibre. |
| Network connectivity | None at runtime. Fully on-device, offline basemap. |
| Cloud/server infrastructure | None. Zero per-query cost. |
| Chipset support | Standard Android sensors + ONNX Runtime. |
| User account | None. Works with no login. |

That table is a slide. It is also the most quietly devastating thing in the deck,
because most competing projects need at least three of those rows.

### Scalability — three axes, all with evidence
1. **Device scale.** Same C++ core, 10 Hz on a phone → 200 Hz on an edge box, with
   600× measured headroom. One codebase, two deployment classes.
2. **Geographic scale.** The offline OSM road graph we ship is **3,271 km /
   35,631 edges**. OSM covers the planet; adding a city is a data step, not an
   engineering step.
3. **Domain scale.** ← the differentiator, see §C.

## C. The `ConstraintManifold` bet — turning scalability from prose into code

**This is the single highest-value technical task in the whole plan. Read
`SCALABILITY_BEYOND_ROADS.md` alongside this.**

Every team's scalability slide is a bullet list of things they might do later.
Ours will be an interface a judge can read.

**The insight:** our algorithm never actually depended on roads. It depended on
the existence of *a low-dimensional set of physically reachable states, known in
advance.* A road graph is one instance. So are: a rail track, a shipping channel,
a tunnel bore, a mine gallery, a warehouse aisle network, a planned rover
traverse.

**The refactor** (Phase 2, Subagent 2.1):

```
ConstraintManifold
  ├─ project(state)            → nearest valid state on the manifold
  ├─ neighbours(state, dist)   → reachable candidate states
  ├─ transition_cost(a, b)     → motion plausibility
  └─ dim()                     → intrinsic dimensionality

  RoadGraphManifold   — ships today; MUST stay bit-identical (2.02×)
  CorridorManifold    — 1-D polyline + lateral tolerance; tested
```

**Why this scores:** "our future scope is other domains" is worth 6/10.
"Here is the interface; the road-graph implementation ships and the corridor
implementation has a passing test; the algorithm is unchanged and only the
manifold differs" is worth 10/10 — because it is checkable.

**Hard constraint:** `RoadGraphManifold` must reproduce today's mapfilter
benchmark exactly. Diff the results before and after. If 2.02× moves, the
refactor broke something and must be fixed before anything else proceeds.

**Honesty boundary:** we may say the constraint is pluggable and demonstrate two
implementations. We may **not** say we have validated underwater, rail, or
planetary navigation. We have not. Say "the same interface admits a bathymetric
or track manifold — that is our roadmap, not our result."

## D. The layered delivery

| Layer | Content |
|---|---|
| **L0** | The architecture diagram: sensors → filter → position on road, with one core feeding both a phone and an edge box. |
| **L1** | "It needs no new hardware, no map licence, no internet, and no server. It runs on the phone you already own — and the same core does 600× the throughput a 200 Hz industrial box needs." |
| **L2** | The "what we need that doesn't exist: nothing" table + 120,305 Hz + the three scalability axes. |
| **L3** | The `ConstraintManifold` interface, the JNI/WASM/native build targets, why a particle filter over a discrete graph rather than an EKF over a continuous plane. |

## E. Tasks

### 2.1 — The manifold refactor
Phase 2, Subagent 2.1. Specified above and in the master induction.

### 2.2 — The feasibility table as a slide element
Build the "requirements that don't already exist: none" table into slide 3 or 4.
Six rows, checkmarks, no prose.

### 2.3 — Make the dual-target build visible
One diagram, one command each, showing the same `core/cpp` source producing the
Android JNI library and the edge daemon. If there is a build command a judge
could run, name it on the slide.

### 2.4 — State the honest engineering risk
On the feasibility slide, one line: **"Heading drift is the hard part. Our own
measurement says a perfect gyro isn't enough — which is why the map is in the
loop."** Naming your own hardest problem, with your mitigation, is a feasibility
*positive*, not a negative. It reads as engineering maturity.

## F. Language discipline

**Say:**
- "Zero additional hardware. Zero licence cost. Zero network at runtime."
- "The same core runs at 10 Hz on a phone and 120,305 Hz on an edge box — 600×
  the 200 Hz requirement."
- "The map is a plug-in. The algorithm doesn't know it's a road."
- "Adding a city is a data step, not an engineering step."

**Never say:**
- "Works on any device" — we have tested a limited set. Say "any Android phone
  with an IMU; we have run it on <what we actually ran it on>."
- That we have validated a non-road domain. We have implemented and tested a
  corridor manifold on synthetic motion. That is what we say.
- Any throughput number other than 120,305 Hz.

## G. The questions that decide this criterion

> *"What happens when there's no map for where you are?"*

> "Then we degrade to free inertial dead reckoning — which is exactly the 17%
> baseline we published. We don't fail closed, we fail back to the state of the
> art. And OSM coverage is the reason we chose it over a proprietary map: it
> already covers the places a licensed map doesn't."

> *"Why a particle filter and not a Kalman filter?"*

> "Because the state space is a graph, not a plane. At a junction the belief is
> genuinely multi-modal — you might be on either road — and a Kalman filter has to
> collapse that to one Gaussian, which is wrong precisely at the moment it
> matters most. Particles carry both hypotheses until the motion resolves them."

> *"600× headroom sounds like you over-engineered it."*

> "It's the same core, so the headroom is free. What it buys is that the phone
> path is never compute-bound — we can add particles or run a heavier model
> without a redesign."

## H. Acceptance

- [ ] `ConstraintManifold` interface exists; `RoadGraphManifold` bit-identical
      (before/after mapfilter numbers pasted in the phase report)
- [ ] `CorridorManifold` implemented with a passing test
- [ ] Feasibility table on a slide
- [ ] Dual-target build diagram + commands
- [ ] Honest heading-drift risk line on the feasibility slide
- [ ] Every throughput/coverage number in `CLAIMS.json`
