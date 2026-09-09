# COAST — Final Demo Pitch: READ ME FIRST

**Written:** 9 Sep 2026. **Author:** Claude (decision layer, pre-build).
**For:** Cursor (executor) + the team (presenters).

---

## What this folder is

This is the **decision layer** the build runs off. It was written *before* any
new code, on purpose. Each file is a precise build/presentation spec. The
workflow is:

1. **Cursor executes** the specs in this folder, in the order given in
   `08_EXECUTION_ORDER_AND_ACCEPTANCE.md`. Cursor writes the code so we don't
   burn Claude's token budget on mechanical typing.
2. **Claude reviews** what Cursor built against the acceptance checks, fixes the
   physics/honesty-critical parts, wires the measured numbers, and hardens.
3. **The team** builds the PPT from `03_PPT_SPEC.md` and rehearses Q&A.

Read the files in numeric order. `01_DECISION_LAYER.md` is the one to read if
you read only one.

---

## The single most important fact: the clock

**The precursor is Friday, 11 September 2026 — two days from now.** This is NOT
the 30 September national deadline. The precursor schedule (from the official
PDF) is:

| Time | What | Judged on |
|---|---|---|
| 11:30–12:00 | **Round 1** | Criteria **F1–F8**, from your **PPT** (~2–3 min/team) |
| 12:30 | Round 1 results | shortlist announced |
| 1:00 PM+ | **Round 2** (shortlisted only) | **F9–F10**: live pitch, **Q&A**, teamwork |

Consequences that shape everything in this folder:

- **Round 1 is won on the slide deck.** A judge spends 2–3 minutes. The PPT
  (`03_PPT_SPEC.md`) is therefore the highest-leverage artifact in the whole
  project. It must carry the numbers, the diagram, and the negative result with
  zero handwaving.
- **Round 2 is won on a live demo + Q&A.** This is where the app, the
  blackout-injection demo, the ghost car, the ZUPT tabletop, and the live
  figure-generation module earn their place — they make the PPT's claims
  *believable in the room*.
- **We do NOT have time to "write 20,000 lines" before Friday.** We have time to
  make a small number of demo-critical slices flawless. Everything in this
  folder is tagged **P0 / P1 / P2**:
  - **P0 — must exist and work by Friday.** If it isn't done, the demo is at risk.
  - **P1 — strong upgrade, build if P0 is solid.**
  - **P2 — for the 30 Sep finals, not Friday.** Do not let P2 work endanger P0.

If Cursor only finishes the P0 set, we still walk in with a winning Round 1 deck
and a working Round 2 demo. That is the bar.

---

## The non-negotiable honesty rules (these win, they do not lose)

Every claim we put on a slide or say out loud must be defensible if a judge
points at the exact line of code or the exact measured row. This is not caution
for its own sake — at an internal round with ISRO/DRDO-adjacent judges, a
volunteered negative result and a defensible number **beats** a polished lie,
every time. Specifically:

1. **Never show a number we did not measure.** The money numbers are in
   `01_DECISION_LAYER.md` §"The numbers" with their source files. Use those
   verbatim. Do not round them up, do not invent a CDF we didn't compute.
2. **The confidence signal is BROKEN** (−0.23 correlation with error). It must
   NOT be drawn as a confidence radius anywhere in the UI. See `04_APP_UI_SPEC.md`.
3. **Nothing has run on a physical phone yet.** If that is still true on Friday,
   the demo script in `05_DEMO_MODES_SPEC.md` uses the in-app replay + tabletop
   tests, which are honest ("this is the dataset streamed through the real
   pipeline" / "this is the live sensor on the table") — never claim a live road
   drive we didn't do.
4. **Volunteer the negative result.** "A *perfect* gyro still fails 55% of
   segments — that is *why* we put the map inside the filter loop." Nobody else
   brings this. It is our strongest credibility signal.
5. **Own what is not done.** GNSS+INS fusion, on-phone latency, field scooter
   logs — these are honestly "next", not "done". Saying so is a strength.

If any spec in this folder tempts you to fake a GREEN result, stop and flag it.

---

## The thesis, in one paragraph (say this on stage)

> Most vehicles on Indian roads — trucks, older cars, 200M+ two-wheelers — have
> no built-in inertial navigation. Their only navigation device is the driver's
> phone, and the moment it enters a tunnel, underpass, metro, or a jammed area,
> the map freezes. COAST keeps the dot moving using only the phone's own
> accelerometer and gyroscope, with no internet and no extra hardware, and snaps
> the estimate onto an OpenStreetMap road graph so the error cannot grow without
> bound. We proved on real car data that the naive approach fails even with a
> perfect gyro, and that putting the map *inside* the filter loop is 2× better.
> It is the same inertial-navigation discipline ISRO flies on launch vehicles,
> running on a ₹15,000 phone.

---

## File index

| File | What it is | Primary owner |
|---|---|---|
| `00_READ_ME_FIRST.md` | This file | everyone |
| `01_DECISION_LAYER.md` | Current state → what to change, F1–F10 mapped, the numbers | everyone |
| `02_RESEARCH_FINDINGS.md` | Open-source repos/modules: adopt vs. cite | Cursor |
| `03_PPT_SPEC.md` | The Round-1 deck, slide by slide + Q&A bank | presenters |
| `04_APP_UI_SPEC.md` | Uber-black full-screen map, HUD, settings/sessions/login | Cursor |
| `05_DEMO_MODES_SPEC.md` | Blackout injection, ghost car, ZUPT/alignment, stability + sensor-injection tests | Cursor |
| `06_LIVE_TRAINING_AND_FIGURES_SPEC.md` | "Run one command → train → figures/" + 3-line plot + CDF | Cursor |
| `07_LOCALHOST_PHONE_TRACKER_SPEC.md` | Phone → laptop live tracking dashboard | Cursor |
| `08_EXECUTION_ORDER_AND_ACCEPTANCE.md` | Build order, P0/P1/P2, acceptance checks | Cursor |
