# F1 — Innovation & Creativity
*"Novelty of idea & creative problem-solving"* · Round 1 · judged off the deck

---

## A. What this criterion actually rewards

Not "new technology." Judges see forty projects; almost all of them are a known
technology applied to a known problem. What scores here is a **non-obvious move**
— evidence that the team saw something the obvious approach misses.

There are exactly two ways to demonstrate that in ninety seconds:

1. Show the obvious approach failing.
2. Show your approach succeeding on the same input.

Everything below is in service of doing that in one picture.

## B. Our innovation, stated precisely

**The obvious approach:** GPS died, so estimate position from the phone's motion
sensors. Integrate acceleration to get velocity, integrate again to get position,
use the gyroscope for heading. Everyone who attempts this problem does this.

**Why it fails:** integration accumulates error quadratically. A small heading
bias becomes a large lateral error within a minute. The universal instinct is
then *"get a better sensor / a better filter / a better neural network."*

**Our move — and this is the whole innovation:** we tested that instinct and
found it is wrong, then changed the geometry of the problem instead of the
quality of the sensor.

- **The test:** we gave the algorithm a *perfect* gyroscope — simulated,
  zero-error, physically impossible. Free dead reckoning **still failed 55% of
  60-second segments.** So the sensor was never the binding constraint.
  → `lab/stress/results/heading_ablation/summary.md`
- **The redesign:** we changed what the filter is allowed to believe. Instead of
  estimating a free position `(x, y)` in the plane and snapping it to a road
  afterwards, the filter's state *is* `(which road edge, how far along it)`. The
  estimate lives on the road graph. It cannot leave the road, because there is no
  representation for "off the road."
- **The result:** **2.02×** better than free dead reckoning across 43 real GNSS
  outages with vehicle CAN ground truth.
  → `lab/stress/results/mapfilter/summary.md`

**The control that proves it is the *in-loop* part that matters:** we also
measured the obvious version — run free dead reckoning, then snap the answer to
the nearest road at the end. That scores **0.98×. It actively hurts.**
→ `lab/stress/results/mapmatch/`

That contrast is the innovation in one line: *the map is worthless as a
post-processing step and transformative as a constraint inside the loop.*

## C. The layered delivery

| Layer | Content |
|---|---|
| **L0** (5 s) | The money visual: red line sprays off the road, teal line hugs it. Understood without a single word. |
| **L1** (30 s) | "Everyone tries to fix this with a better sensor. We tested a *perfect* sensor — it still fails half the time. So we stopped fixing the sensor and put the road map inside the filter. Two times better on real drives." |
| **L2** (2 min) | The three-number contrast: post-hoc snapping **0.98×** (hurts) · perfect gyro **still fails 55%** · map-in-loop **2.02×**. Sources on screen. |
| **L3** (Q&A) | The state-space formulation, the particle filter, Newson & Krumm HMM map matching as prior art, why our formulation differs, the `ConstraintManifold` interface generalising it. |

## D. Tasks

### 1.1 — The money visual (also listed in Phase 1)
Owned by Phase 1 Subagent 1.1. This slide *is* F1. Everything else on the
innovation slide is caption.

### 1.2 — Put the negative result ON the slide, not in the appendix
Most teams hide failures. Ours is the proof. The innovation slide must carry the
line **"a perfect gyroscope still fails 55% of the time"** in large type, as the
setup for our answer. It reframes us from "team that built a thing" to "team that
found something out."

### 1.3 — The three-bar contrast graphic
A single small chart: `post-hoc snap 0.98× | free DR 1.00× | map-in-loop 2.02×`.
This is the most persuasive object in the entire deck for a technical judge,
because it contains its own control. Generate from the measured results files,
not by hand.

### 1.4 — Name the idea
Give the mechanism a memorable handle so a judge can repeat it in the scoring
discussion after we leave the room: **"map-in-the-loop."** Use those exact words
consistently in the deck, the app, and the pitch. A judge who can name your idea
is a judge who can advocate for it.

## E. Language discipline

**Say:**
- "We put the map inside the filter loop, not after it."
- "A perfect gyroscope still fails — so the sensor was never the problem."
- "Snapping to the road afterwards actually makes it worse. We measured that."
- "The error can't grow sideways because the state has no way to represent
  'off the road'."

**Never say:**
- "First ever" / "world's first" anything. Map-matched inertial navigation is a
  known field. Our contribution is the measured demonstration on a commodity
  phone plus the negative result, and that is enough.
- "We beat [named paper/product]." We have not run that comparison.
- Any improvement factor other than 2.02×.
- "Revolutionary", "game-changing", "cutting-edge". Judge type B discounts a
  project one full point for each of these. The numbers do this work.

## F. Prior art we cite — deliberately, not defensively

Citing prior art *raises* the innovation score with a technical judge. It signals
we know the field, and it makes our specific delta legible.

- **Newson & Krumm (2009)** — HMM map matching. The canonical map-matching work.
  We implement it and we cite it. Our difference: they match a *completed* GPS
  trace to roads; we constrain a *live* inertial estimate.
- **TLIO / RoNIN / TinyOdom** — the neural inertial odometry line. Our AI speed
  model sits in this family.
- **AI-IMU-DR (Brossard)** — invariant EKF vehicle dead reckoning.
- **EqNIO (ICLR 2025)** — mount-invariance via gravity-axis symmetry. We
  implemented the canonicalisation and measured it (see `lab/models/results/
  mount_invariant/summary.md`) — mixed on this corpus, but it measurably improved
  mount-swap stability. Report exactly that, including the mixed part.
- **Terrain-aided / map-aided INS** in aerospace and marine — see
  `SCALABILITY_BEYOND_ROADS.md`. This is our strongest framing: the idea of
  constraining an inertial estimate with a map is *proven doctrine* in
  submarines and cruise missiles; we are the ones bringing it to a ₹15,000 phone
  and a road graph.

That last point is worth its own sentence in the pitch, because it does something
rare — it makes the idea feel simultaneously **innovative** (nobody did it on a
phone) and **safe** (the principle is flight-proven). That combination is what
scores 10 rather than 8 with a conservative judge.

## G. The question that decides this criterion

> *"Isn't this just map matching? That's an old idea."*

The answer must be immediate and confident, because it is the strongest attack
available and a hesitant answer here costs the criterion:

> "Map matching is post-processing — you finish estimating, then snap to a road.
> We measured that: it scores 0.98×, it makes things *worse*, because you snap a
> badly-drifted estimate onto a confidently wrong road. What we do is different —
> the road graph is the state space itself. The filter never represents an
> off-road position, so error can't accumulate laterally in the first place.
> Same map, opposite architecture, and the measured gap between them is 0.98×
> versus 2.02×."

Every team member must be able to deliver that answer. It is question #1 in the
Q&A bank.

## H. Acceptance

- [ ] Money visual passes the five-second test on a non-technical viewer
- [ ] 55% negative result appears in large type on the innovation slide
- [ ] Three-bar contrast graphic generated from measured data
- [ ] "Map-in-the-loop" used verbatim and consistently across deck, app, pitch
- [ ] Prior art cited on the references slide
- [ ] All six members can answer §G cold
