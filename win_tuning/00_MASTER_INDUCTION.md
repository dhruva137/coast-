# 00 — MASTER INDUCTION for Cursor

**Paste this entire file into Cursor. Work on branch `demo`.**

You are executing a phased plan to maximise a hackathon evaluation score across
ten criteria (F1–F10). The strategy is already decided — you are **not** to
re-plan it. Read `win_tuning/01_SCORING_MODEL_AND_DOCTRINE.md` first and treat it
as binding. Then read the specific `F*.md` file for whatever phase you are in.

---

## 0. NON-NEGOTIABLE RULES (violating any of these fails the whole task)

1. **Never fabricate a number.** Not in a slide, not in the app, not in the web
   console, not in a `summary.md`, not in a comment. If a value is not the output
   of a real computation on real data, it does not get written down as a result.
2. **Never fake a green.** No simulated progress bars, no interpolated loss
   curves, no `Math.random()` standing in for a metric, no `except: return
   <plausible value>`. If a computation fails, the UI says it failed.
3. **Do not touch the demo ground truth:**
   `android/app/src/main/assets/demo/iovnbd_demo.csv` and
   `android/app/src/main/assets/maps/demo_neighbourhood.mbtiles`.
4. **Do not change the estimator's numeric output** on the live sensor path
   except where a phase explicitly authorises a bug fix. Run the unit suite
   before and after every phase.
5. **The headline numbers are frozen.** 2.02× map-in-loop; perfect gyro still
   fails 55%; free-DR 17% short-arm / 10% tunnel-arm; median drift 28% free vs
   17% COAST; 120,305 Hz edge; 100 ms handover; 3.6× unit bug. If your work
   changes any of these, **stop and report** — do not silently update them.
6. **One feature per commit.** End every commit message with:
   `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`
7. **If a task cannot be completed honestly in the time available, ship the
   honest partial and write the limitation down.** A documented gap scores far
   better than a fabricated completion.

---

## 1. HOW TO RUN THE PHASES

Phases are **sequential**. Subagents within a phase are **parallel** — launch
them together, they own disjoint files.

**Gate between phases:** after each phase, run `python tools/verify_claims.py`,
the JVM unit suite, and a release assemble. All three green, or fix before
advancing. Report the phase table (below) before starting the next one.

**File ownership** (to keep parallel subagents from colliding):

| Domain | Paths |
|---|---|
| Android UI | `android/app/src/main/java/in/sih26168/idr/ui/**`, `res/**` |
| Android engine | `.../sensor/**`, `.../nav/**`, `.../record/**`, `IdrBus.kt` |
| C++ core | `core/cpp/**` |
| Lab / ML | `lab/**` |
| Web console | `web/**` |
| Pitch assets | `final_demo_pitch/**` |
| Tooling | `tools/**` |
| Strategy docs | `win_tuning/**` — **read-only for you.** Never edit these. |

---

# PHASE 0 — TRUTH LOCK  *(blocking; nothing else starts until this is green)*

**Why this is first:** every downstream phase writes numbers into slides and
UIs. Until there is a machine-checkable registry of what we are allowed to
claim, every later phase is a chance to introduce an unsourced number. Lock it
first. This phase is also, by itself, one of the highest-scoring artifacts we
have (see `F5_TECHNICAL_EXECUTION.md` and `F8_SECURITY_AND_PRIVACY.md`).

### Subagent 0.1 — Build the claim registry

Create `win_tuning/CLAIMS.json`. Walk the repo and extract **every** measured
number we currently rely on. For each, an entry:

```json
{
  "id": "map_in_loop_improvement",
  "value": 2.02,
  "unit": "x",
  "statement": "Map-in-loop particle filter vs free dead-reckoning",
  "source_file": "lab/stress/results/mapfilter/summary.md",
  "recompute": "python -m lab.stress.run_mapfilter",
  "dataset": "IO-VNBD, 43 real GNSS outages, vehicle CAN ground truth",
  "measured_on": "2026-09-XX",
  "confidence": "measured",
  "notes": "Full committed run. `python -m lab.demo` is a fast re-run of the method, not a replacement."
}
```

`confidence` is one of: `measured` (we ran it), `derived` (arithmetic on measured
values — show the arithmetic), `external` (a cited third-party figure — must
carry a URL), `roadmap` (not yet done — must never appear as a result).

Sweep at minimum: `lab/stress/results/**/summary.md`, `lab/models/results/**`,
`core/cpp/apps/README.md`, `figures/demo_plots.json`, `docs/AUDIT_AND_PLAN.md`.
Include the honest washes (GNSS+INS 1.07×, alignment 32%→32%, speed-model
per-window wash) — a registry that only contains wins is a registry nobody will
believe.

### Subagent 0.2 — Build the linter

Create `tools/verify_claims.py`. It must:

- Load `win_tuning/CLAIMS.json`.
- Scan a configured set of "claim surfaces": `final_demo_pitch/**/*.md`, the
  generated PPTX text, `web/**` user-visible strings, Android
  `res/values/strings.xml`, and any `summary.md` under `lab/`.
- Extract numeric claims (a number adjacent to a unit or a `×`/`%`/`Hz`/`m`
  token) and check each against the registry within a tolerance.
- **Exit non-zero** listing every unsourced number with `file:line`.
- Support an inline escape for genuinely non-claim numbers (slide numbers,
  version strings, years): a `<!-- claims:ignore -->` marker or an allowlist
  file, used sparingly and reviewed.
- Print a summary: `N claims checked, M sourced, K unsourced`.

Add a `--demo-failure` flag that injects a fake number into a temp copy and shows
the linter catching it. **This is a live demo move for the judges** — fifteen
seconds, and it proves the discipline is real rather than asserted.

### Subagent 0.3 — Wire it in

- `pytest` test that runs the linter and fails on unsourced claims.
- A short section in the repo `README.md`: *"Every number we publish is linted
  against `CLAIMS.json`. Run `python tools/verify_claims.py`."*
- Fix, or delete, every unsourced number the first run finds. **Do not fix by
  adding the number to the registry** — fix by finding its real source, or by
  removing the claim. If a number cannot be sourced, it must come off the slide.

**Phase 0 acceptance:** linter runs clean; registry has ≥15 entries including
≥3 honest negative/wash results; `--demo-failure` visibly catches a planted
number.

---

# PHASE 1 — THE FIVE-SECOND LAYER  *(F1, F3, F9)*

Target: the L0/L1 layers from the doctrine. A judge who looks for five seconds
and walks away must still have received the pitch.

### Subagent 1.1 — The money visual

The single most valuable asset in the entire project. Produce
`final_demo_pitch/ppt_assets/diagrams/money_shot.png` (and an animated GIF/MP4
version for the console and the backup video).

Requirements:
- Real trajectory data from the actual IO-VNBD run — **not** an illustration.
  Pull from the existing mapfilter results so the shape on screen is the shape we
  measured.
- Three lines: ground truth (white/grey), free dead-reckoning (red, visibly
  spraying off the road network), COAST (teal, tracking the road).
- The road network drawn underneath in dark grey so the "off the road" failure is
  *visually obvious to someone who does not know what any of it means.*
- Legible from three metres on a projector: line weight ≥4px, labels ≥28pt.
- No axis clutter, no gridlines, no title. Two words per label maximum.
- Must survive greyscale printing (differentiate by dash pattern too, not colour
  alone — this is also an accessibility requirement, see `F3`).

Acceptance: show it to someone with no background, ask "which one is broken?"
They answer correctly in under five seconds, with no explanation.

### Subagent 1.2 — App first-run and demo-mode front door

A judge will hold this phone for ninety seconds. Optimise exactly that.

- On first launch (and behind an always-visible entry point), a **Demo Mode**
  affordance that starts the blackout replay in one tap. No setup, no
  permissions, no login. It must work in airplane mode.
- A one-line explainer on the demo screen at all times, in plain language:
  *"GPS is off. Position is coming from the phone's motion sensors + the road
  map."* Not jargon. A non-technical judge reads this and understands the whole
  project.
- Label it honestly and permanently on-screen: **"REPLAY — real dataset, real
  estimator."** Never let it look like a live drive.
- The GNSS→IDR transition must be *visually loud*: the mode pill changes, and the
  moment of handover is unmissable. This is the beat the whole demo rests on.
- Zero crash paths: rotate, background/foreground, deny every permission, no
  network. All must be safe.

### Subagent 1.3 — Deck Layer-0 pass

Do not restructure the deck (it is in the official SIH IDEA format and must stay
there). Do a typography and hierarchy pass over
`final_demo_pitch/ppt_assets/COAST_SIH2026_IDEA.pptx`:

- Every slide gets **one headline** at the top stating its conclusion, in the
  largest type on the slide. Not a topic ("Technical Approach") — a conclusion
  ("One core runs on a ₹15,000 phone and a 200 Hz edge box").
- Every slide has exactly one dominant visual. If a slide currently has two
  competing graphics, cut one.
- Body text is support, not content. Nothing smaller than 18pt.
- Regenerate via the existing python-pptx build so it stays reproducible.
- Run `tools/verify_claims.py` over the output.

**Phase 1 acceptance:** the money visual passes the five-second test on a naive
viewer; demo mode runs from cold launch in airplane mode in one tap; deck slides
each have a conclusion headline and one visual.

---

# PHASE 2 — THE PROOF LAYER  *(F2, F5)*

Target: convert asserted depth into inspectable depth.

### Subagent 2.1 — The `ConstraintManifold` refactor  ← **highest technical value in this plan**

Read `win_tuning/SCALABILITY_BEYOND_ROADS.md` before starting.

Today the map constraint is hardcoded to road graphs, so every "this scales to
other domains" statement is prose. Make it structural:

- Extract an interface (C++ core, mirrored in the Kotlin/Python paths as
  appropriate): `ConstraintManifold`, exposing roughly —
  `project(state) -> state_on_manifold`, `neighbours(state, distance) ->
  [candidate states]`, `transition_cost(a, b)`, `dim()`.
- `RoadGraphManifold` — the existing behaviour, refactored behind the interface.
  **Its numeric output must be bit-identical to today's.** Prove it: run the
  mapfilter benchmark before and after and diff the results. If 2.02× moves, you
  have broken something.
- Implement **one** additional real manifold with a passing test. Recommended:
  `CorridorManifold` (a 1-D polyline with a lateral tolerance) — this is the rail
  track / shipping channel / tunnel bore case, and it is genuinely the simplest
  possible constraint, so it is quick and it is honest.
- A test that runs the *same* filter over the *same* synthetic motion against
  both manifolds and shows both bounding lateral error.

Why this matters: it converts the future-scope slide from a wish into a type
signature. A judge can read the interface and immediately see that the algorithm
is domain-general and the map is a plug-in. Report the measured before/after
mapfilter numbers in the phase report.

**Honesty constraint:** we implement the corridor manifold and we test it on
synthetic motion. We may therefore say *"the constraint is an interface; we ship
a road-graph implementation and demonstrate a corridor implementation."* We may
**not** say we have validated underwater or rail navigation. Write that
limitation into the summary file yourself.

### Subagent 2.2 — Surface the code quality that already exists

The repo is strong and invisible. Make it visible in artifacts a judge can see in
seconds.

- `docs/ENGINEERING_EVIDENCE.md`: real counts (files and LOC per language, test
  count, which suites pass), how to run everything in one command, and the
  measured performance table.
- Write up **the 3.6× unit bug we found in our own pipeline** as a short, proud
  case study — what it was, how we caught it, what we changed, what it invalidated
  and what we re-ran. This is the single strongest code-quality signal we own,
  because it proves we audit ourselves. Put it where a judge will find it.
- One command that runs everything: `make verify` or `python tools/verify_all.py`
  → unit suites + claim linter + a build. Print a clean summary table.

### Subagent 2.3 — Harden the live console

`python -m web.coast_console` is a Round-2 asset. Make it robust:
- Cold start on a laptop with no network, no phone connected: must render and
  explain what it is, not error out.
- If training subprocess fails, show the real error. Never invent a curve.
- The "why we beat the baseline" ledger must read its rows from `CLAIMS.json`
  (Phase 0), with the source file shown next to each row.
- One-command start, documented in the README.

**Phase 2 acceptance:** mapfilter benchmark numerically unchanged after the
refactor; corridor manifold test passes; `verify_all` green; console cold-starts
offline.

---

# PHASE 3 — THE BREADTH LAYER  *(F4, F6, F7)*

Read `F4_IMPACT.md`, `F6_SUSTAINABILITY.md`, `F7_BUSINESS_VIABILITY.md`. These
are largely research-and-writing tasks, not code.

### Subagent 3.1 — Sourced impact model
Build `win_tuning/IMPACT_MODEL.md`: the affected-population numbers, each with a
primary source URL, each entered into `CLAIMS.json` with `confidence: external`.
Use `win_tuning/RESEARCH_GLOBAL_CONTEXT.md` as the input. No number without a
link. Then a use-case ladder: consumer nav → emergency services → logistics →
defence/sovereignty → planetary. Each rung gets one concrete scenario.

### Subagent 3.2 — Sustainability, computed not asserted
`win_tuning/SUSTAINABILITY_MODEL.md`. The strong, true claim is **zero additional
hardware**: we run on phones people already own, so the marginal e-waste and
marginal embodied carbon of deployment are zero, versus a dedicated INS dongle.
Also: fully on-device means no server energy per query. Where you can compute a
figure, compute it and show the arithmetic (`confidence: derived`). Where you
cannot, state the qualitative claim and stop.

### Subagent 3.3 — Unit economics
`win_tuning/BUSINESS_MODEL.md`. Marginal cost per user (≈₹0 — no cloud, no
per-query cost, no map licensing because OSM). Three revenue paths: OEM/SDK
licensing, fleet/logistics B2B, insurance telematics. One realistic pricing
anchor per path, labelled as an estimate. Note the criterion says "if
applicable" — one clean slide beats three cluttered ones.

---

# PHASE 4 — THE TRUST LAYER  *(F8)*

### Subagent 4.1 — The privacy proof artifact
Do not *assert* privacy — *demonstrate* it. Build `tools/privacy_report.py` that
emits `docs/PRIVACY_REPORT.md` from the actual source:
- Every permission in every manifest, with the line, and a one-sentence
  justification for each.
- Every outbound network call site in the codebase, found by scanning, with
  file:line and purpose.
- Confirmation that the `standard` flavour contains no uploader, and that
  `LanUploader` exists only under `src/tracker/`.
- The honest statement about `INTERNET`: it is declared for public OSM/Carto
  basemap tiles only; with the basemap off, network traffic is zero. **We do not
  claim "no INTERNET permission."** Any wording that does is a bug.
Regenerate it in `verify_all` so it cannot drift from the code.

### Subagent 4.2 — Offline-only demo assurance
Ensure the whole Round-2 demo runs in airplane mode from the bundled MBTiles.
Add a test or a documented manual check. This is both an F8 artifact and demo
insurance against dead venue wifi.

---

# PHASE 5 — THE HUMAN LAYER  *(F9, F10 — the only criteria in Round 2)*

**These are documents for humans to rehearse from. No code.** Read
`F9_PRESENTATION.md` and `F10_TEAMWORK.md` and produce exactly what they specify:
the timed 3-act script with named speaking parts for all six members, the tiered
Q&A bank (type-A answer and type-B answer for every question), and the failure
drill. Cursor's job here is assembly and formatting, not invention — the content
is specified in those two files.

---

# PHASE 6 — ADVERSARIAL AUDIT

### Subagent 6.1 — Mechanical
`verify_all` green: claim linter, all unit suites, all flavours assemble,
release build, console cold-start, demo mode in airplane mode.

### Subagent 6.2 — Play the hostile judge
Go through every slide and every on-screen string and attack it:
- Which number here could I not source in ten seconds?
- Which claim is stated more strongly than the evidence supports?
- Where does the simple version contradict the detailed version?
- What is the most embarrassing question, and is it answered in the Q&A bank?
Write findings to `win_tuning/RED_TEAM_FINDINGS.md` with severity. Fix
everything critical. **Do not fix by weakening the evidence — fix by weakening
the claim** until it matches what we measured.

---

## FINAL REPORT FORMAT

One table. Every phase and subagent = `done` / `done-with-limitation` /
`not-done`, with file pointers and measured `summary.md` paths. Then explicitly
confirm each of:

- [ ] `python tools/verify_claims.py` exits 0
- [ ] Unit suites green; all flavours + release assemble
- [ ] mapfilter benchmark unchanged after the manifold refactor (paste before/after)
- [ ] Demo mode runs from cold launch, airplane mode, one tap
- [ ] `python -m web.coast_console` cold-starts with no network
- [ ] Money visual passes the five-second test
- [ ] No fabricated numbers anywhere; every claim in `CLAIMS.json`
- [ ] Demo ground-truth assets untouched
- [ ] Headline numbers unchanged (or: explicitly listed what moved and why)

Then **stop.** Claude reviews before anything ships.
